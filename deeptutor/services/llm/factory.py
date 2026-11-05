"""Unified services-layer LLM factory."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Mapping
import contextlib
from types import SimpleNamespace
from typing import Any, TypedDict

from deeptutor.config.settings import settings
from deeptutor.services.provider_registry import (
    PROVIDERS,
    canonical_provider_name,
    find_by_model,
    find_by_name,
    find_gateway,
)

from .capabilities import supports_response_format
from .config import LLMConfig, get_llm_config
from .error_mapping import map_error
from .multimodal import prepare_multimodal_messages
from .provider_factory import get_runtime_provider
from .utils import is_local_llm_server

DEFAULT_MAX_RETRIES = settings.retry.max_retries
DEFAULT_RETRY_DELAY = settings.retry.base_delay
DEFAULT_EXPONENTIAL_BACKOFF = settings.retry.exponential_backoff

CallKwargs = dict[str, Any]


class ApiProviderPreset(TypedDict, total=False):
    """Typed representation of API provider presets."""

    name: str
    base_url: str
    requires_key: bool
    models: list[str]
    binding: str


class LocalProviderPreset(TypedDict, total=False):
    """Typed representation of local provider presets."""

    name: str
    base_url: str
    requires_key: bool
    default_key: str
    binding: str


ProviderPreset = ApiProviderPreset | LocalProviderPreset
ProviderPresetMap = Mapping[str, ProviderPreset]
ProviderPresetBundle = Mapping[str, ProviderPresetMap]


def _build_retry_delays(
    max_retries: int,
    retry_delay: float,
    exponential_backoff: bool,
) -> tuple[float, ...]:
    if max_retries <= 0:
        return ()
    delays: list[float] = []
    base = max(float(retry_delay), 0.0)
    for attempt in range(max_retries):
        delay = base * (2**attempt) if exponential_backoff else base
        delays.append(min(delay, 120.0))
    return tuple(delays)


def _resolve_provider_spec(
    *,
    binding: str | None,
    model: str,
    api_key: str,
    base_url: str | None,
    fallback: str | None,
):
    explicit = find_by_name(binding)
    gateway = find_gateway(
        provider_name=explicit.name if explicit else None,
        api_key=api_key or None,
        api_base=base_url or None,
    )
    if explicit and gateway and explicit.name == "openai":
        return gateway
    if explicit:
        return explicit
    if gateway:
        return gateway

    model_spec = find_by_model(model)
    if model_spec:
        return model_spec

    if is_local_llm_server(base_url):
        if base_url and "11434" in base_url:
            return find_by_name("ollama")
        return find_by_name("local")
    return None


def _resolve_call_config(
    model: str | None,
    api_key: str | None,
    base_url: str | None,
    api_version: str | None,
    binding: str | None,
    extra_headers: dict[str, str] | None = None,
    reasoning_effort: str | None = None,
):
    provider_spec = _resolve_provider_spec(
        binding=binding,
        model=model or "",
        api_key=api_key or "",
        base_url=base_url or None,
        fallback=None,
    )
    if provider_spec and provider_spec.name in {"openai", "deepseek", "dashscope"}:
        api_key = api_key or ""
    else:
        api_key = api_key or ""

    config = LLMConfig(
        model=model or "",
        api_key=api_key or "",
        base_url=base_url or "",
        api_version=api_version or "",
        provider_name=provider_spec.name if provider_spec else "",
        binding=binding or "",
        extra_headers=extra_headers or {},
    )
    config.reasoning_effort = reasoning_effort

    global_config = get_llm_config()
    if not config.model:
        config.model = global_config.model
    if not config.base_url:
        config.base_url = global_config.base_url
    if not config.api_key:
        config.api_key = global_config.api_key
    if not config.binding:
        config.binding = global_config.binding
    return config, provider_spec


def _build_messages(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    messages: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    request_messages = list(messages) if messages else []
    if not request_messages:
        request_messages = [{"role": "system", "content": system_prompt}] if system_prompt else []
        request_messages.append({"role": "user", "content": prompt})
    elif system_prompt:
        if request_messages[0].get("role") != "system":
            request_messages.insert(0, {"role": "system", "content": system_prompt})
    return request_messages


def _capability_binding(config: LLMConfig, provider_spec: Any) -> str:
    if provider_spec:
        return provider_spec.name
    return config.binding or "openai"


def _sanitize_call_kwargs(
    binding: str,
    model: str,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    allowed = {"response_format", "extra_headers", "max_tokens", "temperature"}
    sanitized: dict[str, Any] = {}
    for key in list(kwargs.keys()):
        if key in allowed:
            sanitized[key] = kwargs.pop(key)
    # pop known noise keys that should not reach the provider
    kwargs.pop("on_usage", None)
    kwargs.pop("verbose", None)
    return sanitized


def _apply_inline_image_data(
    request_messages: list[dict[str, Any]],
    *,
    binding: str,
    model: str,
    image_data: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not image_data:
        return request_messages
    return prepare_multimodal_messages(
        messages=request_messages,
        binding=binding,
        model=model,
        image_data=image_data,
    )


async def complete(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    api_version: str | None = None,
    binding: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    exponential_backoff: bool = DEFAULT_EXPONENTIAL_BACKOFF,
    **kwargs: Any,
) -> str:
    """Send a completion request and return just the response text.

    Returns:
        The response content as a string.

    Raises:
        RuntimeError: If the LLM returns an error.
    """
    content, _usage = await complete_with_response(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        api_key=api_key,
        base_url=base_url,
        api_version=api_version,
        binding=binding,
        messages=messages,
        max_retries=max_retries,
        retry_delay=retry_delay,
        exponential_backoff=exponential_backoff,
        **kwargs,
    )
    return content


async def complete_with_response(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    api_version: str | None = None,
    binding: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    exponential_backoff: bool = DEFAULT_EXPONENTIAL_BACKOFF,
    **kwargs: Any,
) -> tuple[str, dict[str, int]]:
    """Send a completion request and return (response_text, usage_dict).

    Usage dict includes prompt_tokens, completion_tokens, total_tokens,
    and optionally prompt_cache_hit_tokens / prompt_cache_miss_tokens.

    Raises:
        RuntimeError: If the LLM returns an error.
    """
    caller_extra_headers = kwargs.pop("extra_headers", None)
    reasoning_effort = kwargs.pop("reasoning_effort", None)
    image_data = kwargs.pop("image_data", None)

    config, provider_spec = _resolve_call_config(
        model=model,
        api_key=api_key,
        base_url=base_url,
        api_version=api_version,
        binding=binding,
        extra_headers=caller_extra_headers,
        reasoning_effort=reasoning_effort,
    )
    provider = get_runtime_provider(config)
    capability_binding = _capability_binding(config, provider_spec)
    request_messages = _build_messages(prompt, system_prompt, messages)
    request_messages = _apply_inline_image_data(
        request_messages,
        binding=capability_binding,
        model=config.model,
        image_data=image_data,
    )
    retry_delays = _build_retry_delays(max_retries, retry_delay, exponential_backoff)
    extra_kwargs = _sanitize_call_kwargs(
        binding=capability_binding, model=config.model, kwargs=kwargs
    )

    try:
        response = await provider.chat_with_retry(
            messages=request_messages,
            model=config.model,
            reasoning_effort=config.reasoning_effort,
            retry_delays=retry_delays,
            **extra_kwargs,
        )
    except Exception as exc:
        raise map_error(exc, provider=config.provider_name) from exc

    if response.finish_reason == "error":
        raise map_error(
            RuntimeError(response.content or "LLM request failed"), provider=config.provider_name
        )
    return (response.content or "", response.usage)


async def stream(
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    api_version: str | None = None,
    binding: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    exponential_backoff: bool = DEFAULT_EXPONENTIAL_BACKOFF,
    on_usage: Callable[[dict[str, int]], None] | None = None,
    **kwargs: Any,
) -> AsyncGenerator[str, None]:
    """Stream a completion response, yielding text chunks.

    When the stream completes, calls ``on_usage(response.usage)`` if provided,
    allowing callers to capture token usage (including prompt cache fields).

    Args:
        prompt: The user prompt.
        system_prompt: System prompt.
        model: Override model name.
        api_key: Override API key.
        base_url: Override API base URL.
        api_version: API version (for Azure, etc.).
        binding: Provider binding name.
        messages: Full message list (overrides prompt/system_prompt building).
        max_retries: Max retries on transient errors.
        retry_delay: Base delay between retries.
        exponential_backoff: Use exponential backoff.
        on_usage: Optional callback invoked with usage dict after stream finishes.
        **kwargs: Additional arguments passed to the provider.

    Yields:
        Text chunks from the LLM response.
    """
    caller_extra_headers = kwargs.pop("extra_headers", None)
    reasoning_effort = kwargs.pop("reasoning_effort", None)
    image_data = kwargs.pop("image_data", None)

    config, provider_spec = _resolve_call_config(
        model=model,
        api_key=api_key,
        base_url=base_url,
        api_version=api_version,
        binding=binding,
        extra_headers=caller_extra_headers,
        reasoning_effort=reasoning_effort,
    )
    provider = get_runtime_provider(config)
    capability_binding = _capability_binding(config, provider_spec)
    request_messages = _build_messages(prompt, system_prompt, messages)
    request_messages = _apply_inline_image_data(
        request_messages,
        binding=capability_binding,
        model=config.model,
        image_data=image_data,
    )
    retry_delays = _build_retry_delays(max_retries, retry_delay, exponential_backoff)
    extra_kwargs = _sanitize_call_kwargs(
        binding=capability_binding, model=config.model, kwargs=kwargs
    )

    queue: asyncio.Queue[str | BaseException | None] = asyncio.Queue()
    saw_output = False
    saw_content = False
    in_think_block = False
    response_usage: dict[str, int] = {}

    async def _on_reasoning_delta(chunk: str) -> None:
        nonlocal saw_output, in_think_block
        if not chunk:
            return
        saw_output = True
        if not in_think_block:
            in_think_block = True
            await queue.put("<think>")
        await queue.put(chunk)

    async def _on_content_delta(chunk: str) -> None:
        nonlocal saw_output, saw_content, in_think_block
        if not chunk:
            return
        saw_output = True
        saw_content = True
        if in_think_block:
            in_think_block = False
            await queue.put("</think>")
        await queue.put(chunk)

    async def _runner() -> None:
        nonlocal in_think_block, response_usage
        try:
            response = await provider.chat_stream_with_retry(
                messages=request_messages,
                model=config.model,
                reasoning_effort=config.reasoning_effort,
                on_content_delta=_on_content_delta,
                on_reasoning_delta=_on_reasoning_delta,
                retry_delays=retry_delays,
                **extra_kwargs,
            )
            response_usage = response.usage or {}
            if in_think_block:
                in_think_block = False
                await queue.put("</think>")
            # Some providers synthesize a final response only after the stream.
            # Do not replay reasoning_content as user-visible answer text.
            if (
                not saw_content
                and response.content
                and response.content != response.reasoning_content
            ):
                saw_output = True
                await queue.put(response.content)
            if response.finish_reason == "error" and not saw_output:
                await queue.put(
                    map_error(
                        RuntimeError(response.content or "LLM request failed"),
                        provider=config.provider_name,
                    )
                )
        except Exception as exc:
            await queue.put(map_error(exc, provider=config.provider_name))
        finally:
            await queue.put(None)

    task = asyncio.create_task(_runner())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, BaseException):
                raise item
            yield item
        await task
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    # Surface usage data after stream completes
    if on_usage is not None and response_usage:
        on_usage(response_usage)


async def fetch_models(
    binding: str,
    base_url: str,
    api_key: str | None = None,
) -> list[str]:
    if is_local_llm_server(base_url):
        from . import local_provider

        return await local_provider.fetch_models(base_url, api_key)

    from . import cloud_provider

    return await cloud_provider.fetch_models(base_url, api_key, binding)


def _build_api_provider_presets() -> dict[str, ApiProviderPreset]:
    presets: dict[str, ApiProviderPreset] = {}
    for spec in PROVIDERS:
        if spec.is_local:
            continue
        presets[spec.name] = {
            "name": spec.label,
            "base_url": spec.default_api_base,
            "requires_key": not spec.is_oauth,
            "models": [],
            "binding": spec.name,
        }
    return presets


def _build_local_provider_presets() -> dict[str, LocalProviderPreset]:
    presets: dict[str, LocalProviderPreset] = {}
    for spec in PROVIDERS:
        if not spec.is_local:
            continue
        presets[spec.name] = {
            "name": spec.label,
            "base_url": spec.default_api_base,
            "requires_key": False,
            "default_key": "sk-no-key-required",
            "binding": spec.name,
        }
    return presets


API_PROVIDER_PRESETS: dict[str, ApiProviderPreset] = _build_api_provider_presets()
LOCAL_PROVIDER_PRESETS: dict[str, LocalProviderPreset] = _build_local_provider_presets()


def get_provider_presets() -> ProviderPresetBundle:
    return {
        "api": API_PROVIDER_PRESETS,
        "local": LOCAL_PROVIDER_PRESETS,
    }


__all__ = [
    "complete",
    "complete_with_response",
    "stream",
    "fetch_models",
    "get_provider_presets",
    "API_PROVIDER_PRESETS",
    "LOCAL_PROVIDER_PRESETS",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_DELAY",
    "DEFAULT_EXPONENTIAL_BACKOFF",
    "LLMFactory",
]


class LLMFactory:
    """Compatibility factory for legacy integrations."""

    @staticmethod
    def get_provider(config: LLMConfig):
        return get_runtime_provider(config)