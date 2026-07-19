from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.agents.state import IncidentState
from app.config import get_settings
import json

settings = get_settings()

# llm initialisation
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=settings.openai_api_key,
)

async def triage_agent(state: IncidentState) -> dict:
    print(f"[Triage Agent] Analysing alert for {state['affected_service']}...")
    system_prompt = """You are a senior Site Reliability Engineer (SRE) performing initial
    triage on a production incident.
    
    Your job is to analyse the alert and produce a structured initial assessment. Be concise and precise. Focus on facts from the 
    alert, not speculation.
    Always respond with valid JSON in exactly this format:
    {
    "confirmed_severity": "P0|P1|P2|P3",
    "severity_reasoning": "why this severity",
    "impacted_services": ["list", "of", "services"],
    "initial_hypothesis": "one sentence describing what likely went wrong",
    "investigation_focus": "what the other agents should look for"
    }"""

    user_prompt = f"""Analyse this production incident alert:
    Affected Service: {state['affected_service']}
    Reported Severity: {state['severity']}
    Raw Alert: {json.dumps(state['raw_alert'], indent=2)}
    Based on this alert, provide your initial triage assessment."""

    # calling llm
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])

    # parse JSON response
    try:
        triage_findings = json.loads(response.content)
    except json.JSONDecodeError:
        # fallback if llm didn't return valid json
        triage_findings = {
            "confirmed_severity": state['severity'],
            "severity_reasoning": "Could not parse LLM response",
            "impacted_services": [state['affected_service']],
            "initial_hypothesis": "Unknown - triage parsing failed",
            "investigation_focus": "Check all services for errors",
        }
    
    print(f"[Triage Agent] Complete. Hypothesis: {triage_findings.get('initial_hypothesis')}")

    # return only the fields we want to update in state
    return{
        "triage_findings": triage_findings,
        "messages": [response],
    }