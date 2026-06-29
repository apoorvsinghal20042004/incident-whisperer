# Incident Whisperer

Autonomous on-call agent system that diagnoses production failures in real time — 
before your engineer opens a terminal.

## What it does

When a production incident fires, Incident Whisperer runs a LangGraph multi-agent 
pipeline that simultaneously analyzes logs, traces, and metrics to produce a 
structured root cause hypothesis with confidence scores and ranked remediation steps.

## Architecture

- **LangGraph** — multi-agent supervisor graph (Triage → Log Analysis + Metrics → Hypothesis)
- **FastAPI** — async REST API with Server-Sent Events for real-time agent streaming
- **PostgreSQL + pgvector** — incident storage and semantic log search
- **Redis + Celery** — async task queue so agent runs never block the API
- **Next.js** — real-time dashboard showing agent reasoning traces live

## Status

🚧 Active development — Phase 1 (backend foundation) complete, Phase 2 (AI core) in progress.