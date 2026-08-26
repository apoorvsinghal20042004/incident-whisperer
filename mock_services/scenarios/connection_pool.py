from datetime import datetime, timedelta, UTC
from mock_services.log_generator import create_log, new_trace_id
from mock_services.services import get_service, get_dependents


def generate_logs(primary_service: str, start_time: datetime = None) -> list[dict]:

    # Generates logs for a database connection pool exhaustion scenario.
    # Works with any service that has a database.
    # The cascade automatically uses real service dependencies from services.py
    
    if start_time is None:
        start_time = datetime.now(UTC)
    service_cfg = get_service(primary_service)
    db_name = service_cfg.get("database_name", "database")
    dependents = get_dependents(primary_service)
    logs = []

    # T+0 — slow query detected (system-level, no trace_id)
    logs.append(create_log(
        service=primary_service,
        level="WARN",
        message=f"Slow query detected on {db_name}",
        trace_id="system",
        timestamp=start_time,
        metadata={
            "query_duration_ms": 412,
            "baseline_duration_ms": 10,
            "database": db_name,
        },
    ))

    # T+3 to T+15 — 8 failing requests
    num_requests = 8
    for i in range(num_requests):
        trace_id = new_trace_id()
        request_time = start_time + timedelta(seconds=3 + i * 1.5)

        # Primary service: pool exhausted
        logs.append(create_log(
            service=primary_service,
            level="WARN",
            message="Connection pool exhausted, request waiting",
            trace_id=trace_id,
            timestamp=request_time,
            metadata={
                "pool_size": 5,
                "active_connections": 5,
                "waiting_requests": i + 1,
                "database": db_name,
            },
        ))

        # Primary service: timeout
        timeout_time = request_time + timedelta(seconds=2)
        logs.append(create_log(
            service=primary_service,
            level="ERROR",
            message="Request timeout waiting for database connection",
            trace_id=trace_id,
            timestamp=timeout_time,
            metadata={
                "timeout_seconds": 30,
                "database": db_name,
            },
        ))

        # Each dependent service: dependency failure
        for dependent in dependents:
            logs.append(create_log(
                service=dependent,
                level="ERROR",
                message=f"Dependency call to {primary_service} failed",
                trace_id=trace_id,
                timestamp=timeout_time + timedelta(seconds=0.5),
                metadata={
                    "target_service": primary_service,
                    "retry_count": 3,
                    "status_code": 503,
                },
            ))

    logs.sort(key=lambda log: log["timestamp"])
    return logs


def generate_metrics(primary_service: str, start_time: datetime = None) -> dict:
    # Generates time-series metrics for connection pool exhaustion.
    # Works with any service that has a database.
    
    if start_time is None:
        start_time = datetime.now(UTC)

    dependents = get_dependents(primary_service)
    total_samples = 30
    sample_interval = 10
    incident_start = 12

    from datetime import timedelta
    timestamps = [
        start_time + timedelta(seconds=i * sample_interval)
        for i in range(total_samples)
    ]

    # Pool utilization
    pool_utilization = []
    for i in range(total_samples):
        value = 20 + (i % 3) if i < incident_start else min(20 + (i - incident_start) * 10, 100)
        pool_utilization.append({"timestamp": timestamps[i].isoformat(), "value": value})

    # Query duration
    query_duration = []
    for i in range(total_samples):
        value = 10 + (i % 5) if i < incident_start else min(400 + (i - incident_start) * 15, 500)
        query_duration.append({"timestamp": timestamps[i].isoformat(), "value": value})

    # Error rates for each dependent service
    error_rates = {}
    for dep in dependents:
        rates = []
        for i in range(total_samples):
            value = 0 if i < incident_start + 3 else round(min((i - incident_start - 3) * 1.2, 10.0), 1)
            rates.append({"timestamp": timestamps[i].isoformat(), "value": value})
        error_rates[f"{dep}_error_rate_pct"] = rates

    metrics = {
        f"{primary_service}_db_pool_utilization_pct": pool_utilization,
        f"{primary_service}_query_duration_ms": query_duration,
        **error_rates,
    }

    return {
        "window_start": start_time.isoformat(),
        "window_end": timestamps[-1].isoformat(),
        "sample_interval_seconds": sample_interval,
        "metrics": metrics,
    }


def get_alert_payload(primary_service: str) -> dict:
    
    dependents = get_dependents(primary_service)
    alerting_service = dependents[0] if dependents else primary_service

    return {
        "affected_service": alerting_service,
        "severity": "P1",
        "raw_alert": {
            "alert_name": "HighErrorRate",
            "metric": "error_rate_pct",
            "threshold": 5.0,
            "current_value": 8.2,
            "message": f"{alerting_service} error rate exceeded 5% threshold",
            "root_service_hint": primary_service,
        },
    }