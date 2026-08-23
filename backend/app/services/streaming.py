import json
import redis.asyncio as aioredis
from app.config import get_settings

settings = get_settings()

def get_channel_name(incident_id: str) -> str:
    # Each incident gets its own Redis channel. 
    # Why per-incident channels?
    # if we used global channel, all browsers watching different
    # incidents would receive each other's updates

    return f"incident:{incident_id}:updates"

def get_history_key(incident_id: str) -> str:
    # redis list key for storing event history
    # events appended here and published to channel
    # late subscribers can replay history before listening live
    return f"incident:{incident_id}:history"

def _get_redis_client():
    # create a fresh redis client each time bcoz
    # celery uses prefork- each worker process needs its own connection
    # not one shared before forking. 
    return aioredis.from_url(
        settings.redis_url,
        decode_responses=True, # returns str not bytes
    )

async def publish_agent_event(
    incident_id: str,
    agent_name: str,
    event_type: str,
    data: dict,
):
    client = _get_redis_client()
    try:
        # publishes one agent event to incident's redis channel
        # called by each agent as it produces findings
        # SSE endpoint receives this and forwards to browser
        channel = get_channel_name(incident_id)
        history_key = get_history_key(incident_id)

        message = json.dumps({
            "agent": agent_name,
            "event_type": event_type,
            "data": data,
        })

        # store in history list so that it persists even if nobody is subscribed
        # expire after 1hr to prevent mem leak
        await client.rpush(history_key, message)
        await client.expire(history_key, 3600)

        await client.publish(channel, message)
    finally:
        await client.aclose()


async def get_event_history(incident_id: str) -> list[str]:
    client = _get_redis_client()
    try:
        # returns all events stored so far for this incident
        history_key = get_history_key(incident_id)
        return await client.lrange(history_key, 0, -1) # all ele from start to end
    finally:
        await client.aclose()

async def subscribe_to_incident(incident_id: str):

    # creates a redis pub/sub subscription for 1 endpt
    # returns a pubsub obj that SSE endpt listens on
    # SSE endpt calls this once when browser connects, then 
    # keeps connection open, forwarding evey msg that arrives on channel

    # SSE endpt uses a persistent connection. hence, caller is responsible
    # for closing this client
    client = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    pubsub = client.pubsub()
    channel = get_channel_name(incident_id)
    await pubsub.subscribe(channel)
    return pubsub