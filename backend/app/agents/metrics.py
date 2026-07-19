from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.agents.state import IncidentState
from app.config import get_settings
import json

settings = get_settings()

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=settings.openai_api_key,
)

async def metrics_agent(state: IncidentState) -> dict:
    print(f"[Metrics Agent] Analyzing metrics for incident {state['incident_id']}...")
    metrics = state.get('metrics', {})

    if not metrics:
        print("[Metrics Agent] No metrics data available")
        return {
            "metrics_findings": {
                "anomalies": [],
                "incident_start_time": None,
                "affected_metrics": [],
                "baseline_comparison": {},
                "confidence": 0.0,
            },
            "messages": [],
        }
    metric_summaries = {}

    for metric_name, samples in metrics.get('metrics', {}).items():
        values = [s['value'] for s in samples]
        timestamps = [s['timestamp'] for s in samples]

        # find inflection point where metric starts deviating
        # first sample that is twice the baseline avg
        baseline_values = values[:12]
        incident_values = values[12:]

        baseline_avg = sum(baseline_values) / len(baseline_values)
        peak_value = max(values)

        inflection_idx = None
        for i, v in enumerate(values):
            if v > baseline_avg * 2:
                inflection_idx = i
                break
        
        metric_summaries[metric_name] = {
            "baseline_average": round(baseline_avg, 2),
            "peak_value": peak_value,
            "final_value": values[-1],
            "inflection_timestamp": timestamps[inflection_idx] if inflection_idx else None,
            "deviation_factor": round(peak_value / baseline_avg, 2) if baseline_avg > 0 else 0,
        }
    system_prompt = """You are a senior SRE analyzing time-series metrics 
    from a production incident.

    Your job is to identify anomalies, determine when the incident started,
    and describe what the metrics tell us about the root cause.

    Always respond with valid JSON in exactly this format:
    {
        "anomalies": [
            {
                "metric": "metric_name",
                "description": "what happened",
                "severity": "high|medium|low"
            }
        ],
        "incident_start_time": "ISO timestamp when incident began",
        "affected_metrics": ["list of metric names that showed anomalies"],
        "baseline_comparison": "description of how metrics deviated from baseline",
        "root_cause_signal": "what these metrics suggest about the root cause",
        "confidence": 0.0-1.0
    }"""

    user_prompt = f"""Analyze these metric summaries from a production incident:

    Affected Service: {state['affected_service']}
    Metrics Window: {metrics.get('window_start')} to {metrics.get('window_end')}
    Sample Interval: {metrics.get('sample_interval_seconds')} seconds

    Metric Summaries:
    {json.dumps(metric_summaries, indent=2)}

    Identify anomalies and what they indicate about the root cause."""
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])

    try:
        metrics_findings = json.loads(response.content)
    except json.JSONDecodeError:
        metrics_findings = {
            "anomalies": [],
            "incident_start_time": None,
            "affected_metrics": [],
            "baseline_comparison": "Could not parse LLM response",
            "root_cause_signal": "Unknown",
            "confidence": 0.0,
        }

    print(f"[Metrics Agent] Anomalies found: {len(metrics_findings.get('anomalies', []))}")
    print(f"[Metrics Agent] Confidence: {metrics_findings.get('confidence')}")

    return {
        "metrics_findings": metrics_findings,
        "messages": [response],
    }
