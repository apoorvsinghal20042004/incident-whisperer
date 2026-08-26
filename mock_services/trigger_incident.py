import httpx
from datetime import datetime, UTC
from mock_services.simulator import generate_incident_data


async def trigger_incident(
    api_url: str = "http://localhost:8000",
    scenario_name: str = None,
    service_name: str = None,
) -> dict:
    """
    Triggers a random (or specified) incident scenario.
    Generates correlated logs and metrics, fires alert to API.
    """
    now = datetime.now(UTC)

    # Generate all incident data
    incident_data = generate_incident_data(
        scenario_name=scenario_name,
        service_name=service_name,
        start_time=now,
    )

    print(f"[Trigger] Scenario: {incident_data['scenario']}")
    print(f"[Trigger] Service:  {incident_data['service']}")
    print(f"[Trigger] {incident_data['description']}")

    # Fire the alert to our API
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}/incidents/",
            json=incident_data["alert_payload"],
        )
        response.raise_for_status()
        incident = response.json()

    return {
        "incident": incident,
        "logs": incident_data["logs"],
        "metrics": incident_data["metrics"],
        "scenario": incident_data["scenario"],
        "service": incident_data["service"],
    }