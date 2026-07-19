from typing import TypedDict, Annotated, Optional, Any
import operator

class IncidentState(TypedDict):
    # input fields- set once at the start, never modified
    incident_id: str
    affected_service: str
    severity: str
    raw_alert: dict
    logs: list[dict] # 25 structured log lines from incident_simulator
    metrics: dict

    # Triage agent output
    # confirmed severity, list of all impacted services, initial context
    triage_findings: Optional[dict]

    # Log Analysis agent output
    # relevant logs, key patterns, which service is the root
    log_findings: Optional[dict]

    # Metrics agent output
    # anomalies, when they started, which metrics spiked
    metrics_findings: Optional[dict]

    # Hypothesis agent output
    # final diagnosis
    root_cause: Optional[str]
    confidence_score: Optional[float]
    remediation_steps: Optional[list[str]]
    agent_report: Optional[dict]

    # Msg for llm calls
    messages: Annotated[list, operator.add]