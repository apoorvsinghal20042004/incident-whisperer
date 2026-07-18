from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from app.config import get_settings
from app.models.log_embedding import LogEmbedding
import uuid

settings = get_settings()

# create OpenAI async client once - reused for all embedding calls
client = AsyncOpenAI(api_key=settings.openai_api_key)

EMBEDDING_MODEL = "text-embedding-3-small"

async def embed_text(text: str) -> list[float]:
    # converts a single string into 1536-dim vector
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    # response.data is a list of embedding objects
    # [0] gets the first and only one
    # .embedding is the actual list of floats
    return response.data[0].embedding

async def embed_text_batch(texts: list[str]) -> list[list[float]]:
    # converts multiple strings into vectors in a single API call
    # batching is faster and cheaper instead of calling API 25 times
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    # sort by index to guarantee order matches input order
    sorted_data = sorted(response.data, key=lambda x: x.index)
    return [item.embedding for item in sorted_data]

# taking 25 log dictionaries from incident_simulator, embeds them all, and stores them in the log_embeddings table.
# Returns how many logs were stored
async def ingest_logs(
    incident_id: uuid.UUID,
    logs: list[dict],
    db: AsyncSession,
) -> int: 
    if not logs: 
        return 0
    
    # step 1:
    # extract just the text we want to embed
    # we embed: "service level: message"
    texts_to_embed = [
        f"{log['service']} {log['level']}: {log['message']}"
        for log in logs
    ]

    # step 2:
    # embed all 25 logs in 1 api call
    print(f"Embedding {len(texts_to_embed)} log lines...")
    embeddings = await embed_text_batch(texts_to_embed)
    print(f"Embeddings generated successfully")

    # step 3:
    # create LogEmbedding objects and add to database
    for log, embedding in zip(logs, embeddings):
        # parse timestamp string back into datetime object
        # logs store timestamps as ISO format strings
        log_time = datetime.fromisoformat(log["timestamp"])

        log_embedding = LogEmbedding(
            incident_id=incident_id,
            service=log["service"],
            level=log["level"],
            trace_id=log["trace_id"],
            message=log["message"],
            metadata_=log.get("metadata", {}),
            log_timestamp=log_time,
            embedding=embedding,
        )
        db.add(log_embedding)

    # flush all inserts in one database round trip
    await db.flush()
    return len(logs)

async def search_logs(
    incident_id: uuid.UUID,
    query: str,
    db: AsyncSession,
    top_k: int = 5,
    service_filter: str = None,
    level_filter: list[str] = None,
) -> list[LogEmbedding]:
    # semantic search over logs for a specific incident
    # 1) embeds query text into a vector
    # 2) finds top_k log lines whose vectors are closest to query vector using cosine dist
    # 3) optionally filter by service or severity level

    # embed search query using same model
    # critical: query and docs must use same model of embedding
    query_embedding = await embed_text(query)

    # build the base query
    stmt = (
        select(LogEmbedding).where(LogEmbedding.incident_id == incident_id)
    )

    # apply optional filter before search to reduce search space
    if service_filter:
        stmt = stmt.where(LogEmbedding.service == service_filter)
    if level_filter:
        stmt = stmt.where(LogEmbedding.level.in_(level_filter))

    # order by cosine dist to query vector
    # <=> is pgvector's cosine dist operator
    # .cosine_distance() is the pgvector Python library's way of generating the <=> sql operator
    stmt = stmt.order_by(
        LogEmbedding.embedding.cosine_distance(query_embedding)
    ).limit(top_k)

    result = await db.execute(stmt)
    return result.scalars().all()