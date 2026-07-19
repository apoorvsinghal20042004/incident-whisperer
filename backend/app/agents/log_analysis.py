from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.agents.state import IncidentState
from app.config import get_settings
from app.services.embeddings import search_logs
from app.db.database import AsyncSessionLocal
import json
import uuid

settings = get_settings()

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=settings.openai_api_key,
)

async def log_analysis_agent(state: IncidentState) -> dict:
    # semantic search over embedded logs to find relevant evidence
    # llm reasoning over those logs to identify patterns and root service

    print(f"[Log Analysis Agent] Searching logs for incident {state['incident_id']}...")
    # multiple targeted searches to find different aspects of the failure
    triage = state.get('triage_findings') or {}
    initial_hypothesis = triage.get('initial_hypothesis', 'service failure')
    investigation_focus = triage.get('investigation_focus', 'check all errors')
    
    # run semantic searches with different queries
    search_queries = [
        "database connection pool exhausted timeout",
        "service dependency failure error",
        initial_hypothesis,
        investigation_focus,
    ]

    relevant_logs = {}

    async with AsyncSessionLocal() as db:
        for query in search_queries:
            results = await search_logs(
                incident_id=uuid.UUID(state['incident_id']),
                query=query,
                db=db,
                top_k=3,
                level_filter=["ERROR", "WARN"],
            )
            for log in results:
                # deduplicate by msg
                if log.message not in relevant_logs:
                    relevant_logs[log.message] = {
                        "service": log.service,
                        "level": log.level,
                        "message": log.message,
                        "trace_id": log.trace_id,
                        "metadata": log.metadata_,
                        "timestamp": log.log_timestamp.isoformat(),
                    }
    
    unique_logs = list(relevant_logs.values())
    print(f"[Log Analysis Agent] Found {len(unique_logs)} unique relevant logs")

    # llm reasoning
    system_prompt = """You're a senior SRE analysing log evidence from a production incident.
    You'll be given a set of relevant log lines retrieved via semantic search. Your job is to identify patterns, trace the failure chain, and determine which
    service is the root cause of the incident.

    Always respond with valid JSON in exactly this format:
    {
        "key_patterns": ["list of key patterns observed in the logs"],
        "failure_chain": "description of how the failure propagated",
        "root_service": "which service is the actual root cause",
        "root_cause_evidence": "specific log evidence supporting the root cause",
        "confidence": 0.0-1.0
    }"""

    user_prompt = f"""Analyse these log lines from a production incident:
    
    Affected Service (from alert): {state['affected_service']}
    Initial Hypothesis: {initial_hypothesis}

    Relevant log lines:
    {json.dumps(unique_logs, indent=2)}
    
    Identify the failure chain and root cause service."""
    # dumps means dump to string

    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])

    try:
        log_findings = json.loads(response.content)
        log_findings['relevant_logs'] = unique_logs
    except json.JSONDecodeError:
        log_findings = {
            "key_patterns": ["Couldn't parse llm response"],
            "failure_chain": "Unknown",
            "root_service": state['affected_service'],
            "root_cause_evidence": "Log analysis failed",
            "confidence": 0.0,
            "relevant_logs": unique_logs,
        }
    
    print(f"[Log Analysis Agent] Root service identified: {log_findings.get('root_service')}")
    print(f"[Log Analysis Agent] Confidence: {log_findings.get('confidence')}")

    return {
        "log_findings": log_findings,
        "messages": [response],
    }