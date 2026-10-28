from prometheus_client import Histogram, Counter
LLM_latency=Histogram("http_request_duration_seconds","Total duration http request",
                      ["method", "endpoint", "status"])
Total_request=Counter("http_request_total","Total http request",
                      "endpoint")
LLM_LATENCY = Histogram(
    "llm_request_duration_seconds",
    "LLM request latency",
    ["operation"]
)

LLM_REQUESTS = Counter(
    "llm_requests_total",
    "Total LLM requests",
    ["operation", "status"]
)