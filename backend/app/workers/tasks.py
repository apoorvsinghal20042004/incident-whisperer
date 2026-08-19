import asyncio
import uuid
from app.workers.celery_app import celery_app
from app.config import get_settings
import sys
from pathlib import Path

# add proj root to path so mock_services is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

settings = get_settings()

@celery_app.task(
    name="process_incident",
    max_retries=3,
    default_retry_delay=60,
)
def process_incident_task(incident_id: str, logs: list, metrics: dict):
    # bg celery task- runs full agent pipeline
    # called by fastapi immediately after creating an incident record
    # runs in a sep worker proc, indep from the API server

    # celery only runs sync funcs. our pipeline is async.
    # asyncio.run() bridges 2 worlds by creating a temp event loop,
    # running async code inside it, then destroying it

    # _ prefix is a python convention meaning "this is an internal func, not meant to be called directly from outside this module"
    asyncio.run(_process_incident_async(incident_id, logs, metrics))

async def _process_incident_async(
    incident_id: str,
    logs: list,
    metrics: dict,
):
    # imports are inside this func to prevent circular import issues when
    # celery loads the module at startup
    from app.models import incident, log_embedding
    from app.agents.graph import incident_graph
    from app.services.embeddings import ingest_logs
    from app.services.incident_service import update_incident_with_diagnosis
    from app.db.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.incident import Incident

    print(f"[Worker] Starting pipeline for incident {incident_id}")

    # step 1- generate mock logs and metrics
    from mock_services.incident_simulator import generate_connection_pool_incident
    from mock_services.metrics_generator import generate_metrics
    from datetime import datetime, UTC

    now = datetime.now(UTC)
    logs = generate_connection_pool_incident(start_time=now)
    metrics = generate_metrics(start_time=now)
    print(f"[Worker] Generated {len(logs)} logs and {len(metrics['metrics'])} metric series")

    # step 2- embed and store logs in pgvector
    print(f"[Worker] Ingesting {len(logs)} logs...")
    async with AsyncSessionLocal() as db:
        await ingest_logs(
            incident_id=uuid.UUID(incident_id),
            logs=logs,
            db=db,
        )
        await db.commit()
    print(f"[Worker] Logs ingested")

    # step 3- fetch incident details from postgres
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Incident).where(Incident.id == uuid.UUID(incident_id))
        )
        inc = result.scalar_one()
        affected_service = inc.affected_service
        severity = inc.severity
        raw_alert = inc.raw_alert

    # step 4- build initial state and run langgraph graph
    print(f"[Worker] Running agent pipeline...")
    initial_state = {
        "incident_id": incident_id,
        "affected_service": affected_service,
        "severity": severity,
        "raw_alert": raw_alert or {},
        "logs": logs,
        "metrics": metrics,
        "triage_findings": None,
        "log_findings": None,
        "metrics_findings": None,
        "root_cause": None,
        "confidence_score": None,
        "remediation_steps": None,
        "agent_report": None,
        "messages": [],
    }

    final_state = await incident_graph.ainvoke(initial_state)
    print(f"[Worker] Root cause: {final_state.get('root_cause')}")

    # step 5- save complete diagnosis back to postgres
    print(f"[Worker] Saving diagnosis to Postgres...")
    async with AsyncSessionLocal() as db:
        await update_incident_with_diagnosis(
            incident_id=incident_id,
            final_state=final_state,
            db=db,
        )   
        await db.commit()
    print(f"[Worker] Pipeline complete for incident {incident_id}")