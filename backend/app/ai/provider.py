from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import quote

import httpx

from ..config import Settings


@dataclass
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated: bool = False


@dataclass
class ProviderResult:
    content: str
    usage: Usage = field(default_factory=Usage)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    latency_ms: int | None = None


@dataclass
class StreamEvent:
    kind: str
    content: str | None = None
    usage: Usage | None = None


class ProviderError(RuntimeError):
    def __init__(self, code: str, friendly_message: str, status_code: int = 503):
        super().__init__(friendly_message)
        self.code = code
        self.friendly_message = friendly_message
        self.status_code = status_code


class ModelProvider(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict[str, Any]], *, max_tokens: int | None = None) -> ProviderResult:
        raise NotImplementedError

    @abstractmethod
    def stream_generate(
        self, messages: list[dict[str, Any]], *, max_tokens: int | None = None
    ) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError

    @abstractmethod
    async def vision_generate(self, messages: list[dict[str, Any]]) -> ProviderResult:
        raise NotImplementedError

    @abstractmethod
    async def embed(
        self, texts: list[str], *, input_type: Literal["query", "passage"] = "query"
    ) -> list[list[float]]:
        raise NotImplementedError


class NvidiaNimProvider(ModelProvider):
    def __init__(self, settings: Settings):
        self.settings = settings

    def _headers(self, *, stream: bool = False) -> dict[str, str]:
        if not self.settings.ai_api_key:
            raise ProviderError("not_configured", "尚未設定 NVIDIA NIM API Key，請先完成 .env 設定。", 503)
        return {
            "Authorization": f"Bearer {self.settings.ai_api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        }

    def _chat_payload(
        self,
        messages: list[dict[str, Any]],
        *,
        stream: bool,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        resolved_model = model or self._model_for_messages(messages)
        is_ministral = resolved_model.startswith("mistralai/ministral-")
        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": messages,
            "temperature": 0.15 if is_ministral else 0.25,
            "top_p": 1.0 if is_ministral else 0.85,
            "max_tokens": max_tokens or self.settings.ai_max_output_tokens,
            "stream": stream,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        if resolved_model.startswith("nvidia/nemotron-3"):
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        return payload

    def _model_for_messages(self, messages: list[dict[str, Any]]) -> str:
        for message in messages:
            content = message.get("content")
            if isinstance(content, list) and any(item.get("type") == "image_url" for item in content):
                return self.settings.ai_vision_model
        return self.settings.ai_model

    @staticmethod
    def _map_error(response: httpx.Response) -> ProviderError:
        status = response.status_code
        if status in (401, 403):
            return ProviderError("invalid_api_key", "NVIDIA API 驗證失敗，請檢查 API Key。", 503)
        if status == 402:
            return ProviderError("quota_exceeded", "NVIDIA API 額度不足，請檢查帳戶方案。", 503)
        if status == 429:
            return ProviderError("provider_rate_limited", "NVIDIA API 目前請求較多，請稍後再試。", 429)
        if status in (404, 410):
            return ProviderError("model_unavailable", "設定的 NVIDIA 模型目前無法使用，請檢查模型設定與帳戶權限。", 503)
        if status in (408, 504):
            return ProviderError("provider_timeout", "AI 回應逾時，請稍後再試。", 504)
        return ProviderError("provider_unavailable", "NVIDIA AI 服務暫時無法使用，請稍後再試。", 503)

    @staticmethod
    def _usage(data: dict[str, Any] | None) -> Usage:
        if not isinstance(data, dict):
            return Usage()
        def count(primary: str, alternate: str) -> int | None:
            value = data.get(primary, data.get(alternate))
            return value if type(value) is int and value >= 0 else None
        return Usage(
            input_tokens=count("prompt_tokens", "input_tokens"),
            output_tokens=count("completion_tokens", "output_tokens"),
        )

    async def _generate_with_model(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> ProviderResult:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.settings.ai_timeout_seconds) as client:
                response = await client.post(
                    f"{self.settings.ai_base_url.rstrip('/')}/chat/completions",
                    headers=self._headers(),
                    json=self._chat_payload(messages, stream=False, max_tokens=max_tokens, model=model),
                )
            if response.is_error:
                raise self._map_error(response)
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Invalid response content")
            if not content.strip():
                raise ProviderError("empty_response", "AI 沒有產生內容，請再試一次。", 503)
            return ProviderResult(
                content=content,
                usage=self._usage(data.get("usage")),
                request_id=data.get("id") or str(uuid.uuid4()),
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError("provider_timeout", "AI 回應逾時，請稍後再試。", 504) from exc
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("provider_unavailable", "NVIDIA AI 服務回應異常，請稍後再試。", 503) from exc

    async def generate(self, messages: list[dict[str, Any]], *, max_tokens: int | None = None) -> ProviderResult:
        return await self._generate_with_model(messages, max_tokens=max_tokens)

    async def _stream_with_model(
        self, messages: list[dict[str, Any]], *, model: str, max_tokens: int | None = None
    ) -> AsyncIterator[StreamEvent]:
        try:
            completed = False
            timeout = httpx.Timeout(self.settings.ai_timeout_seconds, read=self.settings.ai_timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.settings.ai_base_url.rstrip('/')}/chat/completions",
                    headers=self._headers(stream=True),
                    json=self._chat_payload(messages, stream=True, max_tokens=max_tokens, model=model),
                ) as response:
                    if response.is_error:
                        await response.aread()
                        raise self._map_error(response)
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            completed = True
                            break
                        if not raw:
                            continue
                        data = json.loads(raw)
                        if not isinstance(data, dict):
                            raise ValueError("Invalid stream event")
                        if data.get("usage"):
                            yield StreamEvent(kind="usage", usage=self._usage(data["usage"]))
                        for choice in data.get("choices", []):
                            delta = choice.get("delta", {}).get("content")
                            if delta is not None and not isinstance(delta, str):
                                raise ValueError("Invalid stream content")
                            if delta:
                                yield StreamEvent(kind="token", content=delta)
                            finish = choice.get("finish_reason")
                            if finish == "length":
                                raise ProviderError("response_truncated", "回答達到長度限制，已保留收到的內容；請縮小問題範圍後再試。", 503)
                            if finish == "content_filter":
                                raise ProviderError("response_filtered", "模型無法完成這個請求，請調整問題後再試。", 422)
                            if finish == "stop":
                                completed = True
                    if not completed:
                        raise ProviderError("provider_interrupted", "AI 連線在回答完成前中斷，已保留收到的內容，請稍後再試。", 503)
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError("provider_timeout", "AI 回應逾時，請稍後再試。", 504) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("provider_unavailable", "NVIDIA AI 服務暫時無法使用，請稍後再試。", 503) from exc
        except (AttributeError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("provider_unavailable", "NVIDIA AI 服務回應異常，請稍後再試。", 503) from exc

    async def stream_generate(
        self, messages: list[dict[str, Any]], *, max_tokens: int | None = None
    ) -> AsyncIterator[StreamEvent]:
        primary_model = self._model_for_messages(messages)
        models = [primary_model]
        fallback_model = self.settings.ai_fallback_model
        if (
            primary_model == self.settings.ai_model
            and fallback_model
            and fallback_model != primary_model
        ):
            models.append(fallback_model)
        else:
            # A hosted vision endpoint may complete without any answer tokens.
            # Retry once before exposing content, retaining the image-capable model.
            models.append(primary_model)

        retriable_codes = {"model_unavailable", "provider_timeout", "provider_unavailable", "provider_interrupted", "empty_response"}
        last_error: ProviderError | None = None
        for index, model in enumerate(models):
            emitted_token = False
            leading_whitespace = ""
            yield StreamEvent(kind="model", content=model)
            try:
                async for event in self._stream_with_model(messages, model=model, max_tokens=max_tokens):
                    if event.kind == "token" and event.content:
                        if not emitted_token and not event.content.strip():
                            leading_whitespace += event.content
                            continue
                        if leading_whitespace:
                            event = StreamEvent(kind="token", content=leading_whitespace + event.content)
                            leading_whitespace = ""
                        emitted_token = True
                    yield event
                if not emitted_token:
                    raise ProviderError("empty_response", "AI 沒有產生內容，請再試一次。", 503)
                yield StreamEvent(kind="done")
                return
            except ProviderError as exc:
                last_error = exc
                can_retry = (
                    not emitted_token and index + 1 < len(models) and exc.code in retriable_codes
                    and (models[index + 1] != model or exc.code == "empty_response")
                )
                if not can_retry:
                    raise
        if last_error:
            raise last_error

    async def vision_generate(self, messages: list[dict[str, Any]]) -> ProviderResult:
        return await self._generate_with_model(messages, model=self.settings.ai_vision_model)

    async def embed(
        self, texts: list[str], *, input_type: Literal["query", "passage"] = "query"
    ) -> list[list[float]]:
        if not texts:
            return []
        payload = {
            "model": self.settings.ai_embedding_model,
            "input": texts,
            "input_type": input_type,
            "encoding_format": "float",
            "truncate": "END",
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.ai_timeout_seconds) as client:
                response = await client.post(
                    f"{self.settings.ai_base_url.rstrip('/')}/embeddings",
                    headers=self._headers(),
                    json=payload,
                )
                if response.status_code == 202:
                    request_id = response.json().get("requestId")
                    if not isinstance(request_id, str) or not request_id:
                        raise ValueError("Missing embedding request ID")
                    for _ in range(30):
                        await asyncio.sleep(0.5)
                        response = await client.get(
                            f"{self.settings.ai_base_url.rstrip('/')}/status/{quote(request_id, safe='')}",
                            headers=self._headers(),
                        )
                        if response.status_code != 202:
                            break
                    if response.status_code == 202:
                        raise ProviderError("provider_timeout", "知識庫向量服務尚未完成，請稍後再試。", 504)
            if response.is_error:
                raise self._map_error(response)
            data = response.json().get("data", [])
            if not isinstance(data, list) or len(data) != len(texts):
                raise ValueError("Invalid embedding count")
            indexes = [item["index"] for item in data]
            if any(type(index) is not int for index in indexes) or sorted(indexes) != list(range(len(texts))):
                raise ValueError("Invalid embedding indexes")
            data.sort(key=lambda item: item["index"])
            vectors = [item["embedding"] for item in data]
            dimension = None
            for vector in vectors:
                if not isinstance(vector, list) or not vector:
                    raise ValueError("Empty embedding")
                if any(type(value) not in (int, float) or not math.isfinite(value) for value in vector):
                    raise ValueError("Invalid embedding values")
                if not any(value != 0 for value in vector):
                    raise ValueError("Zero embedding")
                if dimension is not None and len(vector) != dimension:
                    raise ValueError("Inconsistent embedding dimensions")
                dimension = len(vector)
            return vectors
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError("provider_timeout", "知識庫向量服務逾時，請稍後再試。", 504) from exc
        except (httpx.HTTPError, AttributeError, KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
            raise ProviderError("provider_unavailable", "知識庫向量服務暫時無法使用。", 503) from exc


def get_provider(settings: Settings) -> ModelProvider:
    if settings.ai_provider != "nvidia-nim":
        raise ProviderError("unsupported_provider", f"不支援的 AI Provider：{settings.ai_provider}", 503)
    return NvidiaNimProvider(settings)
