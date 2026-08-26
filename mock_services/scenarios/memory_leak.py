from datetime import datetime, timedelta, UTC
from mock_services.log_generator import create_log, new_trace_id
from mock_services.services import get_service, get_all_service_names


def generate_logs(primary_service: str, start_time: datetime = None) -> list[dict]:
    # Generates logs for a memory leak scenario.
    # memory climbs gradually over ~25 minutes,
    # service crashes with OOM, restarts, cycle begins again.

    if start_time is None:
        start_time = datetime.now(UTC)

    logs = []

    # T+0 to T+10min — normal operation with routine INFO logs
    for i in range(3):
        logs.append(create_log(
            service=primary_service,
            level="INFO",
            message="Request processed successfully",
            trace_id=new_trace_id(),
            timestamp=start_time + timedelta(minutes=i * 3),
            metadata={
                "response_time_ms": 45 + i * 2,
                "memory_mb": 200 + i * 50,
            },
        ))

    # T+10min — memory warning threshold crossed
    logs.append(create_log(
        service=primary_service,
        level="WARN",
        message="Memory usage high — approaching warning threshold",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=10),
        metadata={
            "memory_mb": 720,
            "memory_limit_mb": 1024,
            "memory_pct": 70,
            "gc_pause_ms": 180,
        },
    ))

    # T+15min — GC pauses causing latency spikes
    for i in range(2):
        trace_id = new_trace_id()
        logs.append(create_log(
            service=primary_service,
            level="WARN",
            message="Request latency spike detected — GC pause",
            trace_id=trace_id,
            timestamp=start_time + timedelta(minutes=15 + i * 2),
            metadata={
                "request_latency_ms": 450 + i * 150,
                "baseline_latency_ms": 45,
                "gc_pause_ms": 380 + i * 100,
                "memory_mb": 820 + i * 40,
            },
        ))

    # T+20min — critical memory threshold
    logs.append(create_log(
        service=primary_service,
        level="ERROR",
        message="Memory usage critical — OOM imminent",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=20),
        metadata={
            "memory_mb": 991,
            "memory_limit_mb": 1024,
            "memory_pct": 97,
            "gc_pause_ms": 820,
        },
    ))

    # T+22min — requests failing due to severe GC pauses
    for i in range(3):
        trace_id = new_trace_id()
        logs.append(create_log(
            service=primary_service,
            level="ERROR",
            message="Request failed — service unresponsive during GC pause",
            trace_id=trace_id,
            timestamp=start_time + timedelta(minutes=22, seconds=i * 20),
            metadata={
                "request_latency_ms": 9000 + i * 500,
                "gc_pause_ms": 1200,
                "timeout": True,
            },
        ))

    # T+25min — OOM crash
    logs.append(create_log(
        service=primary_service,
        level="ERROR",
        message="Process killed by OOM killer — out of memory",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=25),
        metadata={
            "memory_mb": 1024,
            "memory_limit_mb": 1024,
            "signal": "SIGKILL",
            "reason": "OOM",
        },
    ))

    # T+25min30s — service restarting
    logs.append(create_log(
        service=primary_service,
        level="INFO",
        message="Service restarting after OOM crash",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=25, seconds=30),
        metadata={"restart_reason": "OOM", "restart_count": 1},
    ))

    # T+26min — service back up, memory reset
    logs.append(create_log(
        service=primary_service,
        level="INFO",
        message="Service started successfully after restart",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=26),
        metadata={
            "memory_mb": 198,
            "status": "healthy",
        },
    ))

    # T+27min — memory already climbing again (leak persists)
    logs.append(create_log(
        service=primary_service,
        level="WARN",
        message="Memory usage climbing again after restart — possible leak",
        trace_id="system",
        timestamp=start_time + timedelta(minutes=27),
        metadata={
            "memory_mb": 310,
            "rate_mb_per_minute": 45,
            "estimated_time_to_oom_minutes": 16,
        },
    ))

    logs.sort(key=lambda log: log["timestamp"])
    return logs


def generate_metrics(primary_service: str, start_time: datetime = None) -> dict:
    # Generates time-series metrics for a memory leak.

    if start_time is None:
        start_time = datetime.now(UTC)

    total_samples = 30
    sample_interval = 60  # 1 sample per minute for this slower scenario
    crash_sample = 25     # OOM crash at minute 25

    timestamps = [
        start_time + timedelta(seconds=i * sample_interval)
        for i in range(total_samples)
    ]

    # Memory usage — climbs to limit, crashes, resets, climbs again
    memory_usage = []
    for i in range(total_samples):
        if i < crash_sample:
            # Climbing phase: 200MB → 1024MB over 25 minutes
            value = min(200 + i * 33, 1024)
        elif i == crash_sample:
            value = 1024  # peak before crash
        else:
            # After restart: starts at 198, climbs again
            value = 198 + (i - crash_sample - 1) * 33
        memory_usage.append({
            "timestamp": timestamps[i].isoformat(),
            "value": round(value),
        })

    # GC pause duration — increases with memory pressure
    gc_pause = []
    for i in range(total_samples):
        if i < crash_sample:
            # Grows as memory fills: 20ms → 1200ms
            value = min(20 + i * 48, 1200)
        else:
            # After restart: back to normal
            value = 20 + (i - crash_sample) * 48
        gc_pause.append({
            "timestamp": timestamps[i].isoformat(),
            "value": round(value),
        })

    # Request latency p99 — spikes during GC pauses
    latency = []
    for i in range(total_samples):
        if i < 10:
            value = 45 + i * 2      # baseline: ~45ms
        elif i < crash_sample:
            value = min(45 + (i - 10) * 60, 9000)  # climbs with GC
        else:
            value = 45 + (i - crash_sample) * 60   # after restart
        latency.append({
            "timestamp": timestamps[i].isoformat(),
            "value": round(value),
        })

    return {
        "window_start": start_time.isoformat(),
        "window_end": timestamps[-1].isoformat(),
        "sample_interval_seconds": sample_interval,
        "metrics": {
            f"{primary_service}_memory_usage_mb": memory_usage,
            f"{primary_service}_gc_pause_duration_ms": gc_pause,
            f"{primary_service}_request_latency_p99_ms": latency,
        },
    }


def get_alert_payload(primary_service: str) -> dict:
    return {
        "affected_service": primary_service,
        "severity": "P1",
        "raw_alert": {
            "alert_name": "ServiceOOMRestart",
            "metric": "restart_count",
            "threshold": 1,
            "current_value": 1,
            "message": f"{primary_service} restarted due to OOM — memory leak suspected",
            "memory_mb_at_crash": 1024,
        },
    }