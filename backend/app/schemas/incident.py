from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any
import uuid

# request schema
# defines what the caller must send in req body
class IncidentCreate(BaseModel):
    # Field() lets us add extra metadata
    # description and example show up in the /docs page
    affected_service: str = Field(
        description="Name of service that triggered the incident",
        example="order-service"
    )

    severity: str = Field(
        ...,
        description="Incident severity: PO, P1, P2, or P3",
        example="P1"
    )

    # Any means it can be any valid JSON structure
    raw_alert: Optional[Any] = Field(
        None, # default is none if not provided
        description="Original alert payload from the monitoring system",
        example={"error": "Connection timeout", "service": "order-service"}
    )

# response schema
class IncidentResponse(BaseModel):
    id: uuid.UUID
    affected_service: str
    severity: str
    status: str
    raw_alert: Optional[Any]
    root_cause: Optional[str]
    confidence_score: Optional[float]
    agent_report: Optional[Any]
    created_at: datetime
    updated_at: datetime
    remediation_steps: Optional[list[str]] = None

    # this inner class tells pydantic
    # "this schema will be used with SQLAlchemy model objects, not just plain python dictionaries"
    # without this, pydantic can't read SQLAlchemy model attributes
    model_config = {"from_attributes": True}

# update schema
class IncidentUpdate(BaseModel):
    status: Optional[str] = Field(
        None,
        description="Updated status: investigating, resolved, or false_alarm",
        example="investigating"
    )
    root_cause: Optional[str] = None
    confidence_score: Optional[float] = None
    agent_report: Optional[Any] = None
    remediation_steps: Optional[list[str]] = None