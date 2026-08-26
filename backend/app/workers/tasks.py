import asyncio
import uuid
import sys
from pathlib import Path

# Add project root to path so mock_services is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.workers.celery_app import celery_app
from app.config import get_settings

settings = get_settings()


@celery_app.task(
    name="process_incident",
    max_retries=3,
    default_retry_delay=60,
)
def process_incident_task(incident_id: str, logs: list, metrics: dict):
    """
    Background Celery task — runs the full agent pipeline.
    Synchronous wrapper around async pipeline.
    asyncio.run() bridges Celery's sync world and our async code.
    """
    asyncio.run(_process_incident_async(incident_id, logs, metrics))


async def _process_incident_async(
    incident_id: str,
    logs: list,
    metrics: dict,
):
    from app.models import incident, log_embedding
    from app.agents.graph import incident_graph
    from app.services.embeddings import ingest_logs
    from app.services.incident_service import update_incident_with_diagnosis
    from app.db.database import get_engine, get_session_factory
    from sqlalchemy import select
    from app.models.incident import Incident

    print(f"[Worker] Starting pipeline for incident {incident_id}")

    # Create fresh engine for this worker process
    # Avoids event loop conflicts from Celery prefork model
    worker_engine = get_engine()
    WorkerSession = get_session_factory(worker_engine)

    try:
        # Step 1 — Generate mock logs and metrics
        from mock_services.simulator import generate_incident_data
        from datetime import datetime, UTC

        now = datetime.now(UTC)
        incident_data = generate_incident_data(start_time=now)
        logs = incident_data["logs"]
        metrics = incident_data["metrics"]
        scenario = incident_data["scenario"]
        print(f"[Worker] Scenario: {scenario} on {incident_data['service']}")
        print(f"[Worker] Generated {len(logs)} logs and {len(metrics['metrics'])} metric series")

        # Step 2 — Ingest logs into pgvector
        print(f"[Worker] Ingesting {len(logs)} logs...")
        async with WorkerSession() as db:
            await ingest_logs(
                incident_id=uuid.UUID(incident_id),
                logs=logs,
                db=db,
            )
            await db.commit()
        print(f"[Worker] Logs ingested")

        # Step 3 — Fetch incident details from Postgres
        async with WorkerSession() as db:
            result = await db.execute(
                select(Incident).where(Incident.id == uuid.UUID(incident_id))
            )
            inc = result.scalar_one()
            affected_service = inc.affected_service
            severity = inc.severity
            raw_alert = inc.raw_alert

        # Step 4 — Run agent pipeline
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

        # Step 5 — Save diagnosis to Postgres
        print(f"[Worker] Saving diagnosis...")
        async with WorkerSession() as db:
            await update_incident_with_diagnosis(
                incident_id=incident_id,
                final_state=final_state,
                db=db,
            )
            await db.commit()

        print(f"[Worker] Pipeline complete for incident {incident_id}")

    finally:
        await worker_engine.dispose()