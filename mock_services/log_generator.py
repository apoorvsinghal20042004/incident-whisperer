import json
import uuid
from datetime import datetime, UTC

now = datetime.now(UTC)

def create_log(
    service: str,
    level: str,
    message: str,
    trace_id: str,
    timestamp: datetime,
    metadata: dict = None,
) -> dict:
    return {
        "timestamp": timestamp.isoformat(),
        "service": service,
        "level": level,
        "trace_id": trace_id,
        "message": message,
        "metadata": metadata or {},
    }

def new_trace_id() -> str:
    return f"req-{uuid.uuid4().hex[:8]}"