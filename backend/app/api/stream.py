import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.services.streaming import (
    subscribe_to_incident,
    get_event_history,
)

router = APIRouter(prefix="/stream", tags=["stream"])

@router.get("/incidents/{incident_id}")
async def stream_incident_updates(incident_id: str):
    # browser calls SSE endpt once and keeps connection open
    # SSE format (reqd by browser's EventSource API):
    #   data: {json string}\n\n

    async def event_generator():
        pubsub = await subscribe_to_incident(incident_id)
        try:
            # Send an initial "connected" event so the browser
            # knows the connection is established
            yield f"data: {json.dumps({'event_type': 'connected', 'incident_id': incident_id})}\n\n"

            # replay stored history. if pipeline already finished, browser gets all events immediately
            history = await get_event_history(incident_id)
            pipeline_done = False
            for stored_event in history:
                yield f"data: {stored_event}\n\n"
                event = json.loads(stored_event)
                if event.get("event_type") == "pipeline_complete":
                    pipeline_done = True
                    break

            if pipeline_done:
                return
            
            # Listen for messages- this loop runs until browser disconnects
            async for message in pubsub.listen():
                # pubsub.listen() yields diff msg types
                # we only care abt actual published msgs, not subscription confirmations
                if message["type"] == "message":
                    # forward the msg directly to browser
                    # its already JSON
                    yield f"data: {message['data']}\n\n"

                    # if pipeline complete, close connection
                    # no more event will come after this
                    event = json.loads(message["data"])
                    if event.get("event_type") == "pipeline_complete":
                        break
        
        finally:
            # always unsubscribe and close
            await pubsub.unsubscribe()
            await pubsub.close()
        
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream", # reqd for SSE
        headers={
            # Prevent buffering
            "Cache-Control": "no-cache",
            # Keep connection alive
            "Connection": "keep-alive",
            # Allow browser to receive SSE from our API
            "X-Accel-Buffering": "no",
        },
    )