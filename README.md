## Tech stack

- **Agent orchestration** — LangGraph (multi-agent StateGraph)
- **LLM** — GPT-4o (hypothesis), GPT-4o-mini (triage, analysis)
- **Semantic search** — pgvector + OpenAI text-embedding-3-small
- **Backend** — FastAPI (async), SQLAlchemy, PostgreSQL
- **Task queue** — Celery + Redis
- **Real-time streaming** — Redis pub/sub + Server-Sent Events
- **Frontend** — Next.js 14 (in progress)
- **Infrastructure** — Docker, Kubernetes-ready

## Run locally

```bash
# Start infrastructure
docker compose up -d

# Terminal 1 — API server
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Celery worker
cd backend
celery -A app.workers.celery_app worker --loglevel=info

# Trigger an incident
curl -X POST http://localhost:8000/incidents/ \
  -H "Content-Type: application/json" \
  -d '{
    "affected_service": "payment-service",
    "severity": "P1",
    "raw_alert": {"alert_name": "HighErrorRate", "current_value": 8.2}
  }'

# Stream agent events in real time
curl -N http://localhost:8000/stream/incidents/{incident_id}
```

## Status

Backend complete. Frontend in progress.

- ✅ LangGraph multi-agent pipeline
- ✅ pgvector semantic log search  
- ✅ Celery async task processing
- ✅ Redis pub/sub + SSE streaming
- 🚧 Next.js real-time dashboard