from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.workers.tasks import process_incident_task
import uuid

from app.db.database import get_db
from app.models.incident import Incident
from app.schemas.incident import IncidentCreate, IncidentResponse, IncidentUpdate

# router
# /incidents is the prefix- all routes in this file start with it
# tags=["incidents"] groups them together in /docs

router = APIRouter(prefix="/incidents", tags=["incidents"])

# create
# POST /incidents accepts an IncidentCreate body and sends IncidentResponse
@router.post(
    # this automatically gets appended with the prefix
    "/",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident(
    incident_data: IncidentCreate, #Pydantic validates req body
    db: AsyncSession = Depends(get_db),
):
    # creating new incident model instance from validated request data
    # model_dump() converts pydantic schema to python dict
    new_incident = Incident(**incident_data.model_dump())

    # stage the insert but dont execute
    db.add(new_incident)

    await db.flush()
    await db.refresh(new_incident)

    # queue the bg task- runs in a sep celery worker proc
    # .delay() is celery's shorthand for "send this task to queue now"
    # we pass incident_id as a str bcoz celery serializes
    # args as json. uuid obj aren't json serializable, strings are
    process_incident_task.delay(
        incident_id=str(new_incident.id),
        logs=[],
        metrics={},
    )

    return new_incident

# read all- returns list of incidents, newest first
@router.get(
    "/",
    response_model=list[IncidentResponse],
)
async def get_incidents(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
):
    result = await db.execute(
        select(Incident)
        .order_by(Incident.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    # scalars() extracts incident obj from result
    # all() fetches them into a list
    incidents = result.scalars().all()
    return incidents

# read one
@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
)
async def get_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )
    return incident

# update
@router.patch(
    "/{incident_id}",
    response_model=IncidentResponse,
)
async def update_incident(
    incident_id: uuid.UUID,
    update_data: IncidentUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id}  not found"
        )
    
    # exclude_unset=True only includes fields that were explicitly sent in request
    update_fields = update_data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(incident, field, value)

    db.add(incident)
    await db.flush()
    await db.refresh(incident)

    return incident