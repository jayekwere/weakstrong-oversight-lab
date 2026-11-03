"""Opt-in bounded JSON model adapters. No model-generated code is executed."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Literal, Protocol
from urllib.parse import urlparse

import httpx
from pydantic import Field

from .core import StrictModel


class ProviderError(RuntimeError):
    """Sanitized provider failure; never contains remote response bodies."""


class BudgetError(ProviderError):
    """A request was rejected before transmission."""


class ProviderConfig(StrictModel):
    kind: Literal["openai", "anthropic", "local"] = "local"
    model: str = Field(default="local-model", min_length=1, max_length=160)
    endpoint: str = "http://127.0.0.1:11434/v1/chat/completions"
    enabled: bool = False
    max_requests: int = Field(default=10, ge=1, le=1000)
    max_tokens: int = Field(default=100000, ge=1, le=10000000)
    max_output_tokens: int = Field(default=512, ge=32, le=4096)
    max_spend_usd: float = Field(default=0.0, ge=0.0, le=100.0)
    # Conservative operator-supplied upper tariff, not a claimed provider price.
    usd_per_million_tokens: float = Field(default=1000.0, gt=0.0, le=10000.0)
    timeout_seconds: float = Field(default=15.0, ge=0.1, le=30.0)
    retries: int = Field(default=1, ge=0, le=2)


class Usage(StrictModel):
    requests: int = 0
    reserved_tokens: int = 0
    reserved_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


class Model(Protocol):
    name: str
    usage: Usage

    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...


def strict_schema(value: dict[str, Any]) -> dict[str, Any]:
    """Convert Pydantic defaults into the strict structured-output provider contract."""
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key == "default":
            continue
        if isinstance(item, dict):
            result[key] = strict_schema(item)
        elif isinstance(item, list):
            result[key] = [strict_schema(v) if isinstance(v, dict) else v for v in item]
        else:
            result[key] = item
    if result.get("type") == "object" and "properties" in result:
        result["required"] = list(result["properties"])
        result["additionalProperties"] = False
    return result


class HTTPModel:
    def __init__(self, config: ProviderConfig, transport: httpx.BaseTransport | None = None):
        self.config = config
        self.name = f"{config.kind}:{config.model}"
        self.usage = Usage()
        parsed = urlparse(config.endpoint)
        allowed = (
            (
                parsed.scheme == "https"
                and parsed.hostname
                == {"openai": "api.openai.com", "anthropic": "api.anthropic.com"}.get(config.kind)
            )
            if config.kind != "local"
            else (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"})
        )
        if not allowed or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ProviderError("endpoint is not an approved provider or loopback address")
        self.transport = transport

    def _reserve(self, tokens: int) -> None:
        cfg = self.config
        cost = 0.0 if cfg.kind == "local" else tokens * cfg.usd_per_million_tokens / 1e6
        if not cfg.enabled:
            raise BudgetError("external model calls require explicit opt-in")
        if (
            self.usage.requests >= cfg.max_requests
            or self.usage.reserved_tokens + tokens > cfg.max_tokens
            or self.usage.reserved_usd + cost > cfg.max_spend_usd
        ):
            raise BudgetError("request, token or spending ceiling reached")
        self.usage.requests += 1
        self.usage.reserved_tokens += tokens
        self.usage.reserved_usd += cost

    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if len(prompt.encode()) > 1048576:
            raise ProviderError("input exceeds adapter limit")
        cfg = self.config
        schema = strict_schema(schema)
        headers = {"content-type": "application/json", "accept-encoding": "identity"}
        if cfg.kind == "anthropic":
            key = os.getenv("ANTHROPIC_API_KEY", "")
            headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
            payload = {
                "model": cfg.model,
                "max_tokens": cfg.max_output_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "tools": [
                    {
                        "name": "decision",
                        "description": "Return a structured research decision",
                        "input_schema": schema,
                    }
                ],
                "tool_choice": {"type": "tool", "name": "decision"},
            }
        else:
            key = os.getenv("OPENAI_API_KEY", "") if cfg.kind == "openai" else ""
            if key:
                headers["authorization"] = f"Bearer {key}"
            payload = {
                "model": cfg.model,
                "max_tokens": cfg.max_output_tokens,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "decision", "strict": True, "schema": schema},
                },
            }
        if cfg.kind != "local" and not key:
            raise ProviderError("provider credential is absent")
        # Reserve the entire serialized request byte count as a conservative input-token bound.
        bound = len(json.dumps(payload, ensure_ascii=True).encode()) + cfg.max_output_tokens
        deadline = time.monotonic() + cfg.timeout_seconds
        for attempt in range(cfg.retries + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProviderError("provider deadline exceeded")
            self._reserve(bound)
            try:
                with (
                    httpx.Client(
                        timeout=remaining, follow_redirects=False, trust_env=False, transport=self.transport
                    ) as client,
                    client.stream("POST", cfg.endpoint, json=payload, headers=headers) as response,
                ):
                    if response.status_code == 429 or response.status_code >= 500:
                        raise httpx.TransportError("transient upstream status")
                    if response.status_code != 200:
                        raise ProviderError("provider rejected the request")
                    if response.headers.get("content-encoding", "identity") != "identity":
                        raise ProviderError("compressed provider responses are not accepted")
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 262144 or time.monotonic() > deadline:
                            raise ProviderError("provider response limit exceeded")
                    body = json.loads(raw)
                usage = body.get("usage", {})
                n_in = usage.get("input_tokens", usage.get("prompt_tokens", 0))
                n_out = usage.get("output_tokens", usage.get("completion_tokens", 0))
                if (
                    type(n_in) is not int
                    or type(n_out) is not int
                    or n_in < 0
                    or n_out < 0
                    or n_in + n_out > bound
                ):
                    raise ProviderError("invalid provider usage")
                self.usage.input_tokens += n_in
                self.usage.output_tokens += n_out
                self.usage.estimated_cost_usd += (
                    0.0 if cfg.kind == "local" else (n_in + n_out) * cfg.usd_per_million_tokens / 1e6
                )
                if cfg.kind == "anthropic":
                    blocks = [
                        b
                        for b in body["content"]
                        if b.get("type") == "tool_use" and b.get("name") == "decision"
                    ]
                    answer = blocks[0]["input"]
                else:
                    answer = json.loads(body["choices"][0]["message"]["content"])
                if not isinstance(answer, dict):
                    raise ProviderError("expected structured object")
                return answer
            except httpx.TransportError:
                if attempt == cfg.retries:
                    raise ProviderError("provider unavailable after bounded retries") from None
            except (KeyError, IndexError, TypeError, ValueError, AttributeError, RecursionError):
                raise ProviderError("invalid structured provider response") from None
        raise ProviderError("unreachable provider state")
