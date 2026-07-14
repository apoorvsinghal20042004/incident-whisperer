import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.db.database import Base

class LogEmbedding(Base):
    __tablename__ = "log_embeddings"
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # foreign key
    # ondelete="CASCADE" : if incident is deleted, automatically delete all its logs
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    service = Column(String(100), nullable=False, index=True)
    level = Column(String(10), nullable=False, index=True)
    trace_id = Column(String(50), nullable=False, index=True)

    # actual log content
    message = Column(Text, nullable=False)

    metadata_ = Column(
        "metadata", # actual col name in postgres
        JSON, 
        nullable=True,
    )

    log_timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    embedding = Column(
        Vector(1536),
        nullable=True, # bcoz we generate it asynchronously
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<LogEmbedding {self.service} | {self.level} | {self.message[:50]}>"