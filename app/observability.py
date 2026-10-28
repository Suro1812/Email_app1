"""
Observability helpers for system metrics and Langfuse event export.
"""

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

logger = logging.getLogger(__name__)

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
except ImportError:  # pragma: no cover
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    Counter = None
    Gauge = None
    Histogram = None
    generate_latest = None

# Gmail API calls and LLM-backed tools routinely run longer than the
# prometheus_client default bucket ceiling of 10s, which would pin every
# latency quantile at +Inf. Hooks are pure local sanitization and need the
# opposite treatment: resolution in the sub-millisecond range.
TOOL_DURATION_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, float("inf"))
HOOK_DURATION_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, float("inf"))
HTTP_DURATION_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float("inf"),
)


def _env_flag(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


if Counter and Histogram:
    TOOL_CALLS = Counter(
        "email_reminders_tool_calls_total",
        "Tool calls by name and status.",
        ["tool_name", "status"],
    )
    TOOL_CALL_DURATION = Histogram(
        "email_reminders_tool_call_duration_seconds",
        "Tool call duration by name.",
        ["tool_name"],
        buckets=TOOL_DURATION_BUCKETS,
    )
    HOOK_CALLS = Counter(
        "email_reminders_hook_calls_total",
        "Security/sanitization hook calls by name and status.",
        ["hook_name", "status"],
    )
    HOOK_CALL_DURATION = Histogram(
        "email_reminders_hook_call_duration_seconds",
        "Security/sanitization hook duration by name.",
        ["hook_name"],
        buckets=HOOK_DURATION_BUCKETS,
    )
    HTTP_REQUESTS = Counter(
        "email_reminders_http_requests_total",
        "HTTP requests by route template, method and status code.",
        ["method", "route", "status"],
    )
    HTTP_REQUEST_DURATION = Histogram(
        "email_reminders_http_request_duration_seconds",
        "HTTP request duration by route template and method.",
        ["method", "route"],
        buckets=HTTP_DURATION_BUCKETS,
    )
    # Pushgateway serves whatever it last received forever, even after the
    # process that pushed it has died — there is no equivalent of a scrape's
    # `up` metric for a push. This gauge is the substitute: a dashboard panel
    # comparing time() against it (time() - this > threshold) is how a dead
    # pusher is told apart from a merely-idle one.
    LAST_PUSH_TIMESTAMP = Gauge(
        "email_reminders_last_push_timestamp_seconds",
        "Unix time of this process's last successful push to the gateway.",
    )
else:  # pragma: no cover
    TOOL_CALLS = None
    TOOL_CALL_DURATION = None
    HOOK_CALLS = None
    HOOK_CALL_DURATION = None
    HTTP_REQUESTS = None
    HTTP_REQUEST_DURATION = None
    LAST_PUSH_TIMESTAMP = None


def _multiproc_dir() -> Optional[str]:
    """Return PROMETHEUS_MULTIPROC_DIR when multiprocess collection is enabled."""
    value = os.getenv("PROMETHEUS_MULTIPROC_DIR", "").strip()
    return value or None


def _metrics_registry() -> Optional[Any]:
    """Registry to render.

    Under uvicorn --workers > 1 or a Celery prefork pool, each process keeps its
    own in-memory registry and would report only the fraction of work it did.
    With PROMETHEUS_MULTIPROC_DIR set, every process writes to shared mmap files
    and the exporting process aggregates them into one view.
    """
    multiproc_dir = _multiproc_dir()
    if not multiproc_dir:
        return None

    try:
        from prometheus_client import CollectorRegistry, multiprocess
    except ImportError:  # pragma: no cover
        return None

    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry, path=multiproc_dir)
    return registry


def prepare_multiprocess_dir() -> None:
    """Create PROMETHEUS_MULTIPROC_DIR and drop stale mmap files from prior runs.

    prometheus_client requires the directory to exist, and leftover files from a
    previous run would otherwise be re-counted as live series.
    """
    multiproc_dir = _multiproc_dir()
    if not multiproc_dir:
        return

    try:
        os.makedirs(multiproc_dir, exist_ok=True)
        for entry in os.listdir(multiproc_dir):
            if entry.endswith(".db"):
                os.remove(os.path.join(multiproc_dir, entry))
    except OSError as exc:
        logger.warning("Could not prepare PROMETHEUS_MULTIPROC_DIR %s: %s", multiproc_dir, exc)


def prometheus_metrics() -> bytes:
    if not generate_latest:
        return b""
    registry = _metrics_registry()
    if registry is not None:
        return generate_latest(registry)
    return generate_latest()


def start_worker_metrics_server(port: Optional[int] = None) -> bool:
    """Expose /metrics from a Celery worker so Prometheus can scrape it.

    Celery is a task consumer with no HTTP server of its own, so the background
    pipeline's tool and hook activity is unreachable without a dedicated
    listener here. The API's own /metrics covers only the interactive endpoints.
    Returns True when a server was started.
    """
    if not _env_flag("ENABLE_WORKER_METRICS_SERVER", default=True):
        return False

    try:
        from prometheus_client import start_http_server
    except ImportError:  # pragma: no cover
        return False

    resolved_port = port if port is not None else int(os.getenv("WORKER_METRICS_PORT", "9100"))
    registry = _metrics_registry()
    # start_http_server defaults registry to the global REGISTRY; passing None
    # explicitly would break it, so only override when aggregating.
    kwargs = {"registry": registry} if registry is not None else {}
    try:
        start_http_server(resolved_port, **kwargs)
    except OSError as exc:
        logger.warning("Worker metrics server could not bind port %s: %s", resolved_port, exc)
        return False

    logger.info("Worker metrics server listening on port %s", resolved_port)
    return True


def _bearer_auth_handler(token: str):
    """Build a push_to_gateway handler that attaches a bearer token.

    prometheus_client's push_to_gateway() takes a `handler` for exactly this
    case — it ships a basic_auth_handler but nothing for bearer tokens, so
    this mirrors that helper's shape by hand.
    """
    import urllib.request

    def handler(url, method, timeout, headers, data):
        headers = list(headers or []) + [("Authorization", f"Bearer {token}")]
        request = urllib.request.Request(url, data=data, headers=dict(headers), method=method)

        def do_request():
            resp = urllib.request.urlopen(request, timeout=timeout)
            resp.close()

        return do_request

    return handler


def push_metrics_once(component: str) -> bool:
    """Push this process's current metrics to PUSHGATEWAY_URL, once.

    For a process Prometheus cannot reach directly — an ACA container app
    with no public ingress on its metrics port, scraped instead through an
    ngrok tunnel in front of a Pushgateway. Grouped by `component` (api /
    worker) and `instance` so replicas and processes don't overwrite each
    other's series in the gateway. No-ops entirely when PUSHGATEWAY_URL is
    unset, so this never affects the existing pull-based /metrics path.
    """
    gateway_url = os.getenv("PUSHGATEWAY_URL", "").strip()
    if not gateway_url:
        return False

    try:
        from prometheus_client import REGISTRY, pushadd_to_gateway
    except ImportError:  # pragma: no cover
        return False

    # pushadd_to_gateway requires a registry; fall back to the global default
    # (what every Counter/Histogram/Gauge above auto-registers into) outside
    # multiprocess mode, same fallback prometheus_metrics() uses for /metrics.
    registry = _metrics_registry() or REGISTRY
    instance = os.getenv("HOSTNAME") or os.getenv("CONTAINER_APP_REPLICA_NAME") or "local"
    grouping_key = {"component": component, "instance": instance}

    token = os.getenv("PUSHGATEWAY_AUTH_TOKEN", "").strip()
    kwargs: Dict[str, Any] = {"registry": registry}
    if token:
        kwargs["handler"] = _bearer_auth_handler(token)

    try:
        if LAST_PUSH_TIMESTAMP:
            # Set before pushing, not after: this is what makes the gauge
            # itself part of the payload being pushed in the same call.
            LAST_PUSH_TIMESTAMP.set_to_current_time()
        pushadd_to_gateway(
            gateway_url,
            job="email_reminders",
            grouping_key=grouping_key,
            **kwargs,
        )
    except Exception as exc:
        logger.warning("Push to gateway %s failed: %s", gateway_url, exc)
        return False
    return True


def start_metrics_pusher(component: str) -> bool:
    """Start a background thread that pushes metrics every PUSHGATEWAY_PUSH_INTERVAL_SECONDS.

    A thread rather than an asyncio task or a Celery beat entry so the same
    function works unchanged from both the FastAPI process and the Celery
    worker. Entirely inert unless PUSHGATEWAY_URL is set.
    """
    if not os.getenv("PUSHGATEWAY_URL", "").strip():
        return False

    import threading

    interval = max(5, int(os.getenv("PUSHGATEWAY_PUSH_INTERVAL_SECONDS", "30")))

    def loop() -> None:
        while True:
            push_metrics_once(component)
            time.sleep(interval)

    thread = threading.Thread(
        target=loop,
        name=f"metrics-pusher-{component}",
        daemon=True,
    )
    thread.start()
    logger.info(
        "Metrics pusher started for component=%s, pushing every %ss",
        component,
        interval,
    )
    return True


def _route_label(request: Any) -> Optional[str]:
    """Resolve a request to its route template, e.g. /gmail/message.

    Never the raw URL path. Raw paths carry message ids and query-bearing
    values, so each distinct one would create its own metric series and a
    scanner hitting random URLs could exhaust Prometheus's memory. Requests
    that matched no route collapse to a single bucket for the same reason.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return path
    if request.scope.get("path", "").startswith("/assets"):
        return "/assets/*"
    return "unmatched"


def install_http_metrics(app: Any) -> bool:
    """Record request count and duration for every HTTP route on `app`.

    Complements the per-tool instrumentation: this catches failures that happen
    before a tool is ever reached, such as auth rejections and validation
    errors. Returns True when the middleware was installed.
    """
    if not _env_flag("ENABLE_HTTP_METRICS", default=True):
        return False
    if not (HTTP_REQUESTS and HTTP_REQUEST_DURATION):  # pragma: no cover
        return False

    @app.middleware("http")
    async def _http_metrics_middleware(request: Any, call_next: Any) -> Any:
        # Scraping /metrics would otherwise count itself on every scrape.
        if request.scope.get("path") == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # An unhandled exception still becomes a 500 for the client, so
            # record it rather than letting the request vanish from the metrics.
            duration = time.perf_counter() - start
            route = _route_label(request)
            HTTP_REQUESTS.labels(method=request.method, route=route, status="500").inc()
            HTTP_REQUEST_DURATION.labels(method=request.method, route=route).observe(duration)
            raise

        duration = time.perf_counter() - start
        route = _route_label(request)
        HTTP_REQUESTS.labels(
            method=request.method,
            route=route,
            status=str(response.status_code),
        ).inc()
        HTTP_REQUEST_DURATION.labels(method=request.method, route=route).observe(duration)
        return response

    return True


def _langfuse_client() -> Optional[Any]:
    if not _env_flag("ENABLE_LANGFUSE_EVENTS", default=True):
        return None

    try:
        from langfuse import get_client
    except ImportError:
        return None

    try:
        return get_client()
    except Exception as exc:
        logger.debug("Langfuse client could not be initialized: %s", exc)
        return None


def export_langfuse_event(
    name: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    client = _langfuse_client()
    if not client:
        return

    event_metadata = metadata or {}
    try:
        if hasattr(client, "create_event"):
            client.create_event(name=name, metadata=event_metadata)
        elif hasattr(client, "event"):
            client.event(name=name, metadata=event_metadata)
        elif hasattr(client, "score"):
            client.score(name=name, value=1, metadata=event_metadata)
    except Exception as exc:
        logger.debug("Langfuse event export failed for %s: %s", name, exc)


@contextmanager
def observe_tool_call(tool_name: str, metadata: Optional[Dict[str, Any]] = None) -> Iterator[None]:
    start = time.perf_counter()
    status = "success"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.perf_counter() - start
        if TOOL_CALLS and TOOL_CALL_DURATION:
            TOOL_CALLS.labels(tool_name=tool_name, status=status).inc()
            TOOL_CALL_DURATION.labels(tool_name=tool_name).observe(duration)
        export_langfuse_event(
            f"tool.{tool_name}",
            {
                **(metadata or {}),
                "status": status,
                "duration_seconds": duration,
            },
        )


@contextmanager
def observe_hook_call(hook_name: str, metadata: Optional[Dict[str, Any]] = None) -> Iterator[None]:
    start = time.perf_counter()
    status = "success"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.perf_counter() - start
        if HOOK_CALLS and HOOK_CALL_DURATION:
            HOOK_CALLS.labels(hook_name=hook_name, status=status).inc()
            HOOK_CALL_DURATION.labels(hook_name=hook_name).observe(duration)
        export_langfuse_event(
            f"hook.{hook_name}",
            {
                **(metadata or {}),
                "status": status,
                "duration_seconds": duration,
            },
        )
