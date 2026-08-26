from datetime import datetime, timedelta, UTC
from mock_services.log_generator import create_log, new_trace_id
from mock_services.services import get_service


def generate_logs(primary_service: str, start_time: datetime = None) -> list[dict]:

    # Generates logs for a bad deployment scenario.

    if start_time is None:
        start_time = datetime.now(UTC)

    logs = []

    # T-2min — normal operation before deployment
    for i in range(2):
        logs.append(create_log(
            service=primary_service,
            level="INFO",
            message="Request processed successfully",
            trace_id=new_trace_id(),
            timestamp=start_time - timedelta(minutes=2 - i),
            metadata={
                "response_time_ms": 42,
                "version": "2.4.1",
            },
        ))

    # T+0 — deployment starts
    logs.append(create_log(
        service=primary_service,
        level="INFO",
        message="Deployment started: version 2.4.1 to 2.4.2",
        trace_id="system",
        timestamp=start_time,
        metadata={
            "old_version": "2.4.1",
            "new_version": "2.4.2",
            "deployed_by": "ci-cd-pipeline",
            "commit": "a3f9c12",
        },
    ))

    # T+0:15 — health check passes (too simple to catch the bug)
    logs.append(create_log(
        service=primary_service,
        level="INFO",
        message="Health check passed — new version marked healthy",
        trace_id="system",
        timestamp=start_time + timedelta(seconds=15),
        metadata={
            "version": "2.4.2",
            "health_check": "GET /health → 200 OK",
            "note": "health check does not exercise full request path",
        },
    ))

    # T+0:20 — real traffic hits the new version, errors begin immediately
    error_message = "TypeError: cannot read property 'id' of undefined"
    for i in range(8):
        trace_id = new_trace_id()
        error_time = start_time + timedelta(seconds=20 + i * 5)

        logs.append(create_log(
            service=primary_service,
            level="ERROR",
            message=f"Unhandled exception: {error_message}",
            trace_id=trace_id,
            timestamp=error_time,
            metadata={
                "version": "2.4.2",
                "exception": error_message,
                "stack_trace": "at processRequest (handler.js:142)",
                "request_path": "/api/process",
                "status_code": 500,
            },
        ))

    # T+1:30 — alert fires, engineer notified
    logs.append(create_log(
        service=primary_service,
        level="WARN",
        message="Error rate critical — possible bad deployment detected",
        trace_id="system",
        timestamp=start_time + timedelta(seconds=90),
        metadata={
            "error_rate_pct": 95,
            "version": "2.4.2",
            "deployed_at": start_time.isoformat(),
        },
    ))

    # T+3min — rollback initiated
    logs.append(create_log(
        service=primary_service,
        level="INFO",
        message="Rollback initiated: version 2.4.2 to 2.4.1",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=3),
        metadata={
            "from_version": "2.4.2",
            "to_version": "2.4.1",
            "reason": "high_error_rate",
            "initiated_by": "on-call-engineer",
        },
    ))

    # T+3:30 — rollback complete, errors stop
    logs.append(create_log(
        service=primary_service,
        level="INFO",
        message="Rollback complete — version 2.4.1 running",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=3, seconds=30),
        metadata={
            "version": "2.4.1",
            "error_rate_pct": 0.1,
            "status": "healthy",
        },
    ))

    logs.sort(key=lambda log: log["timestamp"])
    return logs


def generate_metrics(primary_service: str, start_time: datetime = None) -> dict:
    """
    Generates time-series metrics for a bad deployment.

    Window: 10 minutes, sampled every 20 seconds (30 samples).
    Error rate: 0% → 95% at T+0, stays high until T+3min rollback,
    then immediately drops back to 0%.
    Classic step function shape.
    """
    if start_time is None:
        start_time = datetime.now(UTC)

    total_samples = 30
    sample_interval = 20  # 20 seconds per sample
    deploy_sample = 6     # deployment at T+2min (sample 6)
    rollback_sample = 24  # rollback at T+8min (sample 24)

    timestamps = [
        start_time + timedelta(seconds=i * sample_interval)
        for i in range(total_samples)
    ]

    # Error rate — step function
    error_rate = []
    for i in range(total_samples):
        if i < deploy_sample:
            value = 0.1          # baseline: near-zero errors
        elif i < rollback_sample:
            value = 95.0         # post-deploy: 95% errors
        else:
            value = 0.1          # post-rollback: back to normal
        error_rate.append({
            "timestamp": timestamps[i].isoformat(),
            "value": value,
        })

    # Request success rate — inverse of error rate
    success_rate = []
    for i in range(total_samples):
        if i < deploy_sample:
            value = 99.9
        elif i < rollback_sample:
            value = 5.0
        else:
            value = 99.9
        success_rate.append({
            "timestamp": timestamps[i].isoformat(),
            "value": value,
        })

    # Deployment marker — binary: 1 at deploy time, 0 otherwise
    # This is what shows as a vertical line on monitoring dashboards
    deployment_marker = []
    for i in range(total_samples):
        value = 1 if i == deploy_sample else 0
        deployment_marker.append({
            "timestamp": timestamps[i].isoformat(),
            "value": value,
        })

    return {
        "window_start": start_time.isoformat(),
        "window_end": timestamps[-1].isoformat(),
        "sample_interval_seconds": sample_interval,
        "metrics": {
            f"{primary_service}_error_rate_pct": error_rate,
            f"{primary_service}_request_success_rate_pct": success_rate,
            f"{primary_service}_deployment_marker": deployment_marker,
        },
    }


def get_alert_payload(primary_service: str) -> dict:

    return {
        "affected_service": primary_service,
        "severity": "P1",
        "raw_alert": {
            "alert_name": "HighErrorRate",
            "metric": "error_rate_pct",
            "threshold": 5.0,
            "current_value": 95.0,
            "message": f"{primary_service} error rate at 95% — possible bad deployment",
            "deployment_detected": True,
            "deployed_version": "2.4.2",
        },
    }