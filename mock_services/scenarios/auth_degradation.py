from datetime import datetime, timedelta, UTC
from mock_services.log_generator import create_log, new_trace_id
from mock_services.services import get_dependents


def generate_logs(primary_service: str = "auth-service", start_time: datetime = None) -> list[dict]:
    # Generates logs for auth service degradation.
    if start_time is None:
        start_time = datetime.now(UTC)

    logs = []

    # T-1min — normal auth validations
    for i in range(3):
        logs.append(create_log(
            service=primary_service,
            level="INFO",
            message="Token validation successful",
            trace_id=new_trace_id(),
            timestamp=start_time - timedelta(seconds=60 - i * 20),
            metadata={
                "validation_ms": 48 + i,
                "token_type": "JWT",
                "cache_hit": True,
            },
        ))

    # T+0 — auth starts slowing
    logs.append(create_log(
        service=primary_service,
        level="WARN",
        message="Token validation latency spike detected",
        trace_id="system",
        timestamp=start_time,
        metadata={
            "validation_ms": 1840,
            "baseline_ms": 50,
            "deviation_factor": 36.8,
        },
    ))

    # T+0:30 to T+2min — slow validations on real requests
    for i in range(5):
        trace_id = new_trace_id()
        logs.append(create_log(
            service=primary_service,
            level="WARN",
            message="Token validation slow — degraded auth performance",
            trace_id=trace_id,
            timestamp=start_time + timedelta(seconds=30 + i * 20),
            metadata={
                "validation_ms": 1900 + i * 20,
                "baseline_ms": 50,
                "token_type": "JWT",
            },
        ))

    # T+1min — downstream services reporting elevated latency
    dependents = get_dependents(primary_service)
    for dep in dependents:
        logs.append(create_log(
            service=dep,
            level="WARN",
            message=f"Request latency elevated — auth-service token validation slow",
            trace_id=new_trace_id(),
            timestamp=start_time + timedelta(minutes=1),
            metadata={
                "total_request_ms": 2050,
                "auth_validation_ms": 1950,
                "baseline_total_ms": 100,
                "bottleneck": "auth-service",
            },
        ))

    # T+2min — timeouts begin
    for i in range(3):
        trace_id = new_trace_id()
        logs.append(create_log(
            service=primary_service,
            level="ERROR",
            message="Token validation timeout — request rejected",
            trace_id=trace_id,
            timestamp=start_time + timedelta(minutes=2, seconds=i * 15),
            metadata={
                "timeout_ms": 2000,
                "token_type": "JWT",
                "rejected": True,
            },
        ))

    # T+2:30 — alert correlation
    logs.append(create_log(
        service="api-gateway",
        level="WARN",
        message="Multiple services reporting elevated latency — auth-service degradation suspected",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=2, seconds=30),
        metadata={
            "affected_services": dependents,
            "suspected_root": "auth-service",
            "p99_latency_ms": 2100,
        },
    ))

    # T+3min — some validations timing out completely
    for i in range(2):
        logs.append(create_log(
            service="api-gateway",
            level="ERROR",
            message="Request rejected — auth validation timeout exceeded",
            trace_id=new_trace_id(),
            timestamp=start_time + timedelta(minutes=3, seconds=i * 20),
            metadata={
                "auth_timeout_ms": 2000,
                "status_code": 401,
                "reason": "auth_service_degraded",
            },
        ))

    logs.sort(key=lambda log: log["timestamp"])
    return logs


def generate_metrics(primary_service: str = "auth-service", start_time: datetime = None) -> dict:

    if start_time is None:
        start_time = datetime.now(UTC)

    total_samples = 30
    sample_interval = 20
    degradation_start = 3

    timestamps = [
        start_time + timedelta(seconds=i * sample_interval)
        for i in range(total_samples)
    ]

    # Auth service token validation latency
    auth_latency = []
    for i in range(total_samples):
        if i < degradation_start:
            value = 50
        else:
            value = min(50 + (i - degradation_start) * 80, 2000)
        auth_latency.append({
            "timestamp": timestamps[i].isoformat(),
            "value": round(value),
        })

    # API gateway p99 latency — follows auth latency with slight lag
    gateway_latency = []
    for i in range(total_samples):
        if i < degradation_start + 2:
            value = 100
        else:
            value = min(100 + (i - degradation_start - 2) * 80, 2100)
        gateway_latency.append({
            "timestamp": timestamps[i].isoformat(),
            "value": round(value),
        })

    # Payment service p99 latency — also elevated
    payment_latency = []
    for i in range(total_samples):
        if i < degradation_start + 2:
            value = 80
        else:
            value = min(80 + (i - degradation_start - 2) * 75, 2080)
        payment_latency.append({
            "timestamp": timestamps[i].isoformat(),
            "value": round(value),
        })

    return {
        "window_start": start_time.isoformat(),
        "window_end": timestamps[-1].isoformat(),
        "sample_interval_seconds": sample_interval,
        "metrics": {
            f"{primary_service}_token_validation_ms": auth_latency,
            "api-gateway_request_latency_p99_ms": gateway_latency,
            "payment-service_request_latency_p99_ms": payment_latency,
        },
    }


def get_alert_payload(primary_service: str = "auth-service") -> dict:

    return {
        "affected_service": "api-gateway",
        "severity": "P1",
        "raw_alert": {
            "alert_name": "HighLatency",
            "metric": "request_latency_p99_ms",
            "threshold": 500,
            "current_value": 2100,
            "message": "api-gateway p99 latency at 2100ms — auth-service degradation suspected",
            "suspected_root_cause": primary_service,
        },
    }