import httpx
import json
from datetime import datetime, UTC
from mock_services.incident_simulator import generate_connection_pool_incident
from mock_services.metrics_generator import generate_metrics

async def trigger_incident(api_url: str = "http://localhost:8000") -> dict:
    """
    Simulates a real monitoring system firing an alert.
    
    1. Generates the correlated log timeline and metrics
    2. Calls POST /incidents with a realistic alert payload
    3. Returns the created incident + all data for agent analysis
    """
    now = datetime.now(UTC)

    # generate correlated data
    logs = generate_connection_pool_incident(start_time=now)
    metrics = generate_metrics(start_time=now)

    # alert payload - what a real monitoring system would send
    # this is what triggered the alert: payment-service error rate > 5%
    alert_payload = {
        "affected_service": "payment-service",
        "severity": "P1",
        "raw_alert": {
            "alert_name": "HighErrorRate",
            "triggered_at": now.isoformat(),
            "metric": "error_rate_pct",
            "threshold": 5.0,
            "current_value": 8.2,
            "message": "payment-service error rate exceeded 5% threshold",
        },
    }

    # call our own api to create the incident
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}/incidents/",
            json=alert_payload,
        )
        response.raise_for_status()
        incident = response.json()

    return{
        "incident": incident,
        "logs": logs,
        "metrics": metrics,
    }