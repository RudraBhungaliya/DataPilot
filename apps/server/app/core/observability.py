"""
Production observability: request metrics and timing middleware.

Collects request counters and latency summaries and renders them in Prometheus
text exposition format. Intentionally dependency-free.
"""

import re
import time
from collections import defaultdict
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings
from app.core.logger import logger

# Collapse high-cardinality identifiers in paths for metric stability.
_ID_SEGMENT = re.compile(
    r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|"
    r"(?:ds|dp|job|rec|key|src|colreq|wf|doc)_[0-9a-f]+)$",
    re.IGNORECASE,
)


def normalize_path(path: str) -> str:
    """Replaces ID-like path segments with {id} to keep metric cardinality low."""
    return "/".join("{id}" if _ID_SEGMENT.match(part) else part for part in path.split("/"))


class MetricsRegistry:
    """A minimal in-process Prometheus-style metrics registry."""

    def __init__(self) -> None:
        self.started_at = time.time()
        self._requests: Dict[Tuple[str, str, int], int] = defaultdict(int)
        self._latency_sum_ms: Dict[Tuple[str, str], float] = defaultdict(float)
        self._latency_count: Dict[Tuple[str, str], int] = defaultdict(int)

    def record_request(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        self._requests[(method, path, status_code)] += 1
        self._latency_sum_ms[(method, path)] += duration_ms
        self._latency_count[(method, path)] += 1

    def render(self) -> str:
        lines = [
            "# HELP datapilot_requests_total Total HTTP requests processed.",
            "# TYPE datapilot_requests_total counter",
        ]
        for (method, path, status_code), count in sorted(self._requests.items()):
            lines.append(
                f'datapilot_requests_total{{method="{method}",path="{path}",status="{status_code}"}} {count}'
            )

        lines += [
            "# HELP datapilot_request_duration_ms_sum Total request duration in milliseconds.",
            "# TYPE datapilot_request_duration_ms_sum counter",
        ]
        for (method, path), total in sorted(self._latency_sum_ms.items()):
            lines.append(
                f'datapilot_request_duration_ms_sum{{method="{method}",path="{path}"}} {total:.3f}'
            )

        lines += [
            "# HELP datapilot_request_duration_ms_count Number of timed requests.",
            "# TYPE datapilot_request_duration_ms_count counter",
        ]
        for (method, path), count in sorted(self._latency_count.items()):
            lines.append(
                f'datapilot_request_duration_ms_count{{method="{method}",path="{path}"}} {count}'
            )

        lines.append(f"# process_uptime_seconds {time.time() - self.started_at:.0f}")
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        self._requests.clear()
        self._latency_sum_ms.clear()
        self._latency_count.clear()


metrics = MetricsRegistry()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Records per-route request metrics, timing header, and slow-request logging."""

    SLOW_REQUEST_MS = 1500.0

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            path = normalize_path(request.url.path)
            status_code = response.status_code if response is not None else 500

            if settings.METRICS_ENABLED:
                metrics.record_request(request.method, path, status_code, duration_ms)

            if response is not None:
                response.headers["X-Process-Time-Ms"] = f"{duration_ms:.1f}"

            if duration_ms >= self.SLOW_REQUEST_MS:
                logger.warning(
                    f"Slow request: {request.method} {path} -> {status_code} in {duration_ms:.0f}ms"
                )
