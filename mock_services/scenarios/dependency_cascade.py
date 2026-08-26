from datetime import datetime, timedelta, UTC
from mock_services.log_generator import create_log, new_trace_id


def generate_logs(primary_service: str = "notification-service", start_time: datetime = None) -> list[dict]:

    # Generates logs for an external API dependency cascade.
    if start_time is None:
        start_time = datetime.now(UTC)

    logs = []

    # T-1min — normal operation
    for i in range(2):
        logs.append(create_log(
            service=primary_service,
            level="INFO",
            message="Email notification sent successfully via SendGrid",
            trace_id=new_trace_id(),
            timestamp=start_time - timedelta(minutes=1 - i * 30 / 60),
            metadata={
                "external_service": "sendgrid",
                "endpoint": "https://api.sendgrid.com/v3/mail/send",
                "response_time_ms": 210,
                "status_code": 202,
            },
        ))

    # T+0 — SendGrid starts failing
    for i in range(5):
        logs.append(create_log(
            service=primary_service,
            level="ERROR",
            message="HTTP timeout calling external API",
            trace_id=new_trace_id(),
            timestamp=start_time + timedelta(seconds=i * 30),
            metadata={
                "external_service": "sendgrid",
                "endpoint": "https://api.sendgrid.com/v3/mail/send",
                "timeout_ms": 30000,
                "status_code": 503,
                "response_body": "Service temporarily unavailable",
            },
        ))

    # T+2:30 — circuit breaker opens
    logs.append(create_log(
        service=primary_service,
        level="WARN",
        message="SendGrid API failure rate 100% — circuit breaker opening",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=2, seconds=30),
        metadata={
            "external_service": "sendgrid",
            "failure_rate_pct": 100,
            "circuit_breaker": "open",
            "queuing_notifications": True,
        },
    ))

    # T+3 — queue backing up
    logs.append(create_log(
        service=primary_service,
        level="WARN",
        message="Email notification queue backing up — SendGrid unavailable",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=3),
        metadata={
            "queue_depth": 847,
            "external_service": "sendgrid",
            "circuit_breaker": "open",
        },
    ))

    # T+4 — memory climbing due to queued notifications
    logs.append(create_log(
        service=primary_service,
        level="WARN",
        message="Memory usage climbing — queued notifications accumulating in memory",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=4),
        metadata={
            "memory_mb": 680,
            "queue_depth": 2100,
            "external_service": "sendgrid",
        },
    ))

    # T+5 — queue full, dropping notifications
    logs.append(create_log(
        service=primary_service,
        level="ERROR",
        message="Notification queue full — dropping oldest notifications",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=5),
        metadata={
            "queue_depth": 5000,
            "queue_limit": 5000,
            "dropped_count": 124,
            "external_service": "sendgrid",
        },
    ))

    # T+6 — retry attempt
    logs.append(create_log(
        service=primary_service,
        level="INFO",
        message="Circuit breaker half-open — attempting SendGrid retry",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=6),
        metadata={
            "external_service": "sendgrid",
            "circuit_breaker": "half-open",
        },
    ))

    # T+6:30 — still failing
    logs.append(create_log(
        service=primary_service,
        level="ERROR",
        message="SendGrid retry failed — circuit breaker reopening",
        trace_id=new_trace_id(),
        timestamp=start_time + timedelta(minutes=6, seconds=30),
        metadata={
            "external_service": "sendgrid",
            "endpoint": "https://api.sendgrid.com/v3/mail/send",
            "status_code": 503,
            "circuit_breaker": "open",
        },
    ))

    logs.sort(key=lambda log: log["timestamp"])
    return logs


def generate_metrics(primary_service: str = "notification-service", start_time: datetime = None) -> dict:

    if start_time is None:
        start_time = datetime.now(UTC)

    total_samples = 30
    sample_interval = 20
    failure_start = 3  # SendGrid fails at sample 3

    timestamps = [
        start_time + timedelta(seconds=i * sample_interval)
        for i in range(total_samples)
    ]

    # External API success rate — drops to 0% when SendGrid fails
    api_success_rate = []
    for i in range(total_samples):
        value = 99.9 if i < failure_start else 0.0
        api_success_rate.append({
            "timestamp": timestamps[i].isoformat(),
            "value": value,
        })

    # Notification queue depth — climbs as notifications back up
    queue_depth = []
    for i in range(total_samples):
        if i < failure_start:
            value = 10
        else:
            value = min(10 + (i - failure_start) * 180, 5000)
        queue_depth.append({
            "timestamp": timestamps[i].isoformat(),
            "value": round(value),
        })

    # Memory usage — climbs with queue
    memory_usage = []
    for i in range(total_samples):
        if i < failure_start:
            value = 210
        else:
            value = min(210 + (i - failure_start) * 25, 950)
        memory_usage.append({
            "timestamp": timestamps[i].isoformat(),
            "value": round(value),
        })

    return {
        "window_start": start_time.isoformat(),
        "window_end": timestamps[-1].isoformat(),
        "sample_interval_seconds": sample_interval,
        "metrics": {
            f"{primary_service}_external_api_success_rate_pct": api_success_rate,
            f"{primary_service}_notification_queue_depth": queue_depth,
            f"{primary_service}_memory_mb": memory_usage,
        },
    }


def get_alert_payload(primary_service: str = "notification-service") -> dict:
    return {
        "affected_service": primary_service,
        "severity": "P2",
        "raw_alert": {
            "alert_name": "ExternalAPIFailure",
            "metric": "external_api_success_rate_pct",
            "threshold": 95.0,
            "current_value": 0.0,
            "message": f"{primary_service} external API (SendGrid) unreachable — notification queue backing up",
            "external_service": "sendgrid",
            "queue_depth": 2100,
        },
    }