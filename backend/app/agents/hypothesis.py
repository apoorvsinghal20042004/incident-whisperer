from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.agents.state import IncidentState
from app.config import get_settings
from app.services.streaming import publish_agent_event
import json

settings = get_settings()

# Using gpt-4o here — this is the most complex reasoning task
# Worth the extra cost for accuracy on the final diagnosis
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    api_key=settings.openai_api_key,
)


async def hypothesis_agent(state: IncidentState) -> dict:
    """
    Final agent — runs after all others complete.

    Synthesizes findings from Triage, Log Analysis, and Metrics agents
    into a structured root cause report with confidence score and
    ranked remediation steps.

    This is the agent that produces the final output shown to engineers.
    """
    print(f"[Hypothesis Agent] Synthesizing findings for incident {state['incident_id']}...")

    await publish_agent_event(
        incident_id=state["incident_id"],
        agent_name="hypothesis",
        event_type="agent_started",
        data={"message": "Synthesizing all findings into root cause analysis"},
    )

    triage = state.get('triage_findings') or {}
    log_findings = state.get('log_findings') or {}
    metrics_findings = state.get('metrics_findings') or {}

    system_prompt = """You are a principal SRE synthesizing findings from 
    multiple investigation agents to produce a definitive root cause analysis.

    You have access to:
    1. Initial triage assessment
    2. Log analysis findings
    3. Metrics anomaly analysis

    Your job is to synthesize ALL evidence into a confident, actionable diagnosis.

    Be specific — name the exact service, the exact failure mode, and provide
    concrete remediation steps an engineer can execute immediately.

    Always respond with valid JSON in exactly this format:
    {
        "root_cause": "precise one-sentence root cause statement",
        "root_cause_detail": "detailed explanation of the full failure chain",
        "confidence_score": 0.0-1.0,
        "confidence_reasoning": "why you are or aren't confident",
        "affected_services": ["list of all affected services"],
        "remediation_steps": [
            "immediate step 1 — what to do RIGHT NOW",
            "immediate step 2",
            "follow-up step 1 — what to do after stabilizing",
            "follow-up step 2 — how to prevent recurrence"
        ],
        "severity_assessment": "P0|P1|P2|P3 with reasoning",
        "timeline": "brief description of how the incident unfolded"
    }"""

    user_prompt = f"""Synthesize these investigation findings into a root cause analysis:

    == INCIDENT CONTEXT ==
    Affected Service (from alert): {state['affected_service']}
    Reported Severity: {state['severity']}
    Raw Alert: {json.dumps(state.get('raw_alert', {}), indent=2)}

    == TRIAGE FINDINGS ==
    {json.dumps(triage, indent=2)}

    == LOG ANALYSIS FINDINGS ==
    {json.dumps({k: v for k, v in log_findings.items() if k != 'relevant_logs'}, indent=2)}

    == METRICS FINDINGS ==
    {json.dumps(metrics_findings, indent=2)}

    Produce a definitive root cause analysis with actionable remediation steps."""

    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    content = response.content.strip()
    
    # Remove markdown code block if present
    if content.startswith("```"):
        # Find the first newline after the opening ```
        # and the last ``` closing tag
        content = content.split("\n", 1)[1]  # remove first line (```json)
        content = content.rsplit("```", 1)[0]  # remove closing ```
        content = content.strip()
    try:
        hypothesis = json.loads(content)
    except json.JSONDecodeError:
        hypothesis = {
            "root_cause": "Could not synthesize findings",
            "root_cause_detail": "Hypothesis agent parsing failed",
            "confidence_score": 0.0,
            "confidence_reasoning": "Parse error",
            "affected_services": [state['affected_service']],
            "remediation_steps": ["Manual investigation required"],
            "severity_assessment": state['severity'],
            "timeline": "Unknown",
        }

    print(f"[Hypothesis Agent] Root cause: {hypothesis.get('root_cause')}")
    print(f"[Hypothesis Agent] Confidence: {hypothesis.get('confidence_score')}")

    # Build the full agent report — everything stored in the database
    agent_report = {
        "triage": triage,
        "log_analysis": {k: v for k, v in log_findings.items() if k != 'relevant_logs'},
        "metrics": metrics_findings,
        "hypothesis": hypothesis,
    }

    await publish_agent_event(
        incident_id=state["incident_id"],
        agent_name="hypothesis",
        event_type="agent_complete",
        data={
            "root_cause": hypothesis.get("root_cause"),
            "confidence_score": hypothesis.get("confidence_score"),
            "message": f"Root cause identified with {hypothesis.get('confidence_score')} confidence",
        },
    )

    # Signal that the entire pipeline is done
    await publish_agent_event(
        incident_id=state["incident_id"],
        agent_name="system",
        event_type="pipeline_complete",
        data={
            "root_cause": hypothesis.get("root_cause"),
            "confidence_score": hypothesis.get("confidence_score"),
            "remediation_steps": hypothesis.get("remediation_steps"),
        },
    )

    return {
        "root_cause": hypothesis.get('root_cause'),
        "confidence_score": hypothesis.get('confidence_score'),
        "remediation_steps": hypothesis.get('remediation_steps'),
        "agent_report": agent_report,
        "messages": [response],
    }