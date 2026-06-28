import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.db.database import Base

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    affected_service = Column(String(100), nullable=False)

    severity = Column(String(10), nullable=False)
    # detected->investigating->resolved
    status = Column(String(50), nullable=False, default="detected")
    raw_alert = Column(JSON, nullable=True)

    # AI generated fields that start empty and get filled by agents
    root_cause = Column(Text, nullable=True)

    confidence_score = Column(Float, nullable=True)

    # full structured agent report 
    agent_report = Column(JSON, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self):
        # controls what to print on print(incident)
        return f"<Incident {self.id} | {self.affected_service} | {self.severity}>"