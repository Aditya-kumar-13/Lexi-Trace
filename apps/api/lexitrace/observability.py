from __future__ import annotations

from collections import defaultdict
from threading import Lock


class RequestMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests = 0
        self._errors = 0
        self._latency_ms = 0.0
        self._routes: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {"requests": 0, "errors": 0, "latency_ms": 0.0}
        )

    def record(self, route: str, status_code: int, latency_ms: float) -> None:
        with self._lock:
            self._requests += 1
            self._errors += status_code >= 400
            self._latency_ms += latency_ms
            item = self._routes[route]
            item["requests"] += 1
            item["errors"] += status_code >= 400
            item["latency_ms"] += latency_ms

    def snapshot(self) -> dict:
        with self._lock:
            routes = {
                route: {
                    "requests": int(item["requests"]),
                    "errors": int(item["errors"]),
                    "mean_latency_ms": round(float(item["latency_ms"]) / int(item["requests"]), 3),
                }
                for route, item in sorted(self._routes.items())
            }
            return {
                "requests": self._requests,
                "errors": self._errors,
                "mean_latency_ms": round(
                    self._latency_ms / self._requests if self._requests else 0.0,
                    3,
                ),
                "routes": routes,
            }
