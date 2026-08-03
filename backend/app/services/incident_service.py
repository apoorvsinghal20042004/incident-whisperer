from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.incident import Incident
import uuid

async def update_incident_with_diagnosis(
    incident_id: str,
    final_state: dict,
    db: AsyncSession,
) -> Incident:
    # this func takes final state and saves diagnosis back to incidents table
    # after langgraph pipeline completes.

    # fetch existing incident
    result = await db.execute(
        select(Incident).where(Incident.id == uuid.UUID(incident_id))
    )
    incident = result.scalar_one_or_none()

    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")
    
    # updating with agent findings
    incident.status = "investigating"
    incident.root_cause = final_state.get("root_cause")
    incident.confidence_score = final_state.get("confidence_score")
    incident.remediation_steps = final_state.get("remediation_steps")
    incident.agent_report = final_state.get("agent_report")

    db.add(incident) # tells SQLAlchemy: this obj has changes to write
    await db.flush() # execute the UPDATE in Postgresql (within transaction)
    await db.refresh(incident) # sync Python obj with postgresql's final state

    print(f"[Incident Service] Updated incident {incident_id}")
    print(f"[Incident Service] Status: {incident.status}")
    print(f"[Incident Service] Root cause: {incident.root_cause}")

    return incident