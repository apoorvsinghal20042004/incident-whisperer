from datetime import datetime, timedelta, UTC
from mock_services.log_generator import create_log, new_trace_id
from mock_services.services import get_service, get_dependents


def generate_logs(primary_service: str, start_time: datetime = None) -> list[dict]:
    # Generates logs for a cache stampede scenario.
    if start_time is None:
        start_time = datetime.now(UTC)

    logs = []

    # T-1min — normal operation, cache working well
    logs.append(create_log(
        service=primary_service,
        level="INFO",
        message="Cache warmed — keys loaded into Redis",
        trace_id="system",
        timestamp=start_time - timedelta(minutes=1),
        metadata={
            "cache_keys": 45231,
            "cache_hit_rate_pct": 95.2,
            "redis_memory_mb": 312,
        },
    ))

    # T+0 — Redis cache lost
    logs.append(create_log(
        service=primary_service,
        level="ERROR",
        message="Redis connection lost — cache unavailable",
        trace_id="system",
        timestamp=start_time,
        metadata={
            "redis_host": "redis://localhost:6379",
            "error": "Connection refused",
            "cache_keys_lost": 45231,
        },
    ))

    # T+0:05 — stampede begins, cache miss rate spikes
    logs.append(create_log(
        service=primary_service,
        level="WARN",
        message="Cache miss rate spike — all requests hitting database directly",
        trace_id="system",
        timestamp=start_time + timedelta(seconds=5),
        metadata={
            "cache_hit_rate_pct": 0.0,
            "requests_per_second": 520,
            "db_requests_per_second": 520,
            "baseline_db_rps": 26,
        },
    ))

    # T+0:10 to T+1:00 — requests timing out due to DB overload
    for i in range(6):
        trace_id = new_trace_id()
        logs.append(create_log(
            service=primary_service,
            level="ERROR",
            message="Database query timeout — pool exhausted under cache miss load",
            trace_id=trace_id,
            timestamp=start_time + timedelta(seconds=10 + i * 10),
            metadata={
                "query_duration_ms": 8000 + i * 500,
                "pool_size": 5,
                "active_connections": 5,
                "waiting_requests": 40 + i * 10,
                "cache_available": False,
            },
        ))

    # T+1:30 — connection pool fully exhausted
    logs.append(create_log(
        service=primary_service,
        level="ERROR",
        message="Connection pool fully exhausted — requests failing immediately",
        trace_id="system",
        timestamp=start_time + timedelta(seconds=90),
        metadata={
            "pool_size": 5,
            "active_connections": 5,
            "waiting_requests": 312,
            "cache_available": False,
        },
    ))

    # T+2min — implementing cache warming
    logs.append(create_log(
        service=primary_service,
        level="WARN",
        message="Implementing cache warming strategy — serving degraded traffic",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=2),
        metadata={
            "strategy": "lazy_warming",
            "cache_hit_rate_pct": 12.0,
            "db_load_reducing": True,
        },
    ))

    # T+3min — dependent services affected
    dependents = get_dependents(primary_service)
    for dep in dependents:
        logs.append(create_log(
            service=dep,
            level="ERROR",
            message=f"Dependency {primary_service} returning timeouts — cache stampede impact",
            trace_id=new_trace_id(),
            timestamp=start_time + timedelta(minutes=3),
            metadata={
                "target_service": primary_service,
                "status_code": 503,
                "cache_stampede": True,
            },
        ))

    # T+5min — cache recovering
    logs.append(create_log(
        service=primary_service,
        level="INFO",
        message="Cache hit rate recovering as warm-up progresses",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=5),
        metadata={
            "cache_hit_rate_pct": 67.0,
            "db_query_duration_ms": 45,
            "status": "recovering",
        },
    ))

    # T+7min — fully recovered
    logs.append(create_log(
        service=primary_service,
        level="INFO",
        message="Cache fully restored — normal operation resumed",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=7),
        metadata={
            "cache_hit_rate_pct": 94.8,
            "cache_keys": 44901,
            "db_query_duration_ms": 12,
        },
    ))

    logs.sort(key=lambda log: log["timestamp"])
    return logs


def generate_metrics(primary_service: str, start_time: datetime = None) -> dict:

    if start_time is None:
        start_time = datetime.now(UTC)

    total_samples = 30
    sample_interval = 20
    stampede_start = 3    # cache dies at sample 3
    recovery_start = 18   # cache warming at sample 18

    timestamps = [
        start_time + timedelta(seconds=i * sample_interval)
        for i in range(total_samples)
    ]

    # Cache hit rate — drops to 0%, gradually recovers
    cache_hit_rate = []
    for i in range(total_samples):
        if i < stampede_start:
            value = 95.0
        elif i < recovery_start:
            value = max(0, (i - stampede_start) * 0.5)
        else:
            value = min(95.0, (i - recovery_start) * 8.0)
        cache_hit_rate.append({
            "timestamp": timestamps[i].isoformat(),
            "value": round(value, 1),
        })

    # DB query duration — spikes when cache disappears
    db_query_duration = []
    for i in range(total_samples):
        if i < stampede_start:
            value = 12
        elif i < recovery_start:
            value = min(12 + (i - stampede_start) * 400, 8000)
        else:
            value = max(12, 8000 - (i - recovery_start) * 500)
        db_query_duration.append({
            "timestamp": timestamps[i].isoformat(),
            "value": round(value),
        })

    # DB connection pool utilization
    pool_utilization = []
    for i in range(total_samples):
        if i < stampede_start:
            value = 20
        elif i < recovery_start:
            value = min(20 + (i - stampede_start) * 13, 100)
        else:
            value = max(20, 100 - (i - recovery_start) * 8)
        pool_utilization.append({
            "timestamp": timestamps[i].isoformat(),
            "value": round(value),
        })

    return {
        "window_start": start_time.isoformat(),
        "window_end": timestamps[-1].isoformat(),
        "sample_interval_seconds": sample_interval,
        "metrics": {
            f"{primary_service}_cache_hit_rate_pct": cache_hit_rate,
            f"{primary_service}_db_query_duration_ms": db_query_duration,
            f"{primary_service}_db_pool_utilization_pct": pool_utilization,
        },
    }


def get_alert_payload(primary_service: str) -> dict:
    return {
        "affected_service": primary_service,
        "severity": "P1",
        "raw_alert": {
            "alert_name": "CacheStampede",
            "metric": "cache_hit_rate_pct",
            "threshold": 80.0,
            "current_value": 0.0,
            "message": f"{primary_service} cache hit rate dropped to 0% — database under stampede load",
            "redis_available": False,
            "db_query_duration_ms": 8000,
        },
    }