"""OpenAI Responses API adapter for simple text generation."""

from typing import Protocol, cast

from openai import AsyncOpenAI, OpenAIError

from valor.runtime_gateway.application.ports import (
    ModelProviderPort,
    ProviderInvocationResult,
    ProviderTransportError,
)
from valor.runtime_gateway.domain.invocation import MAX_PROVIDER_RESPONSE_ID_LENGTH
from valor.runtime_gateway.domain.usage import InvocationUsage


class ResponseUsageValue(Protocol):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class ResponseValue(Protocol):
    id: str
    output_text: str
    usage: ResponseUsageValue | None


class ResponsesResource(Protocol):
    async def create(self, *, model: str, input: str, store: bool) -> ResponseValue: ...


class OpenAIClient(Protocol):
    responses: ResponsesResource


class OpenAIResponsesProvider(ModelProviderPort):
    def __init__(
        self,
        api_key: str | None,
        *,
        timeout_seconds: float = 30.0,
        client: OpenAIClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def invoke(self, *, model_reference: str, input_text: str) -> ProviderInvocationResult:
        try:
            if self._client is None:
                if not self._api_key:
                    raise ProviderTransportError("OpenAI runtime credentials are not configured.")
                self._client = cast(
                    OpenAIClient,
                    AsyncOpenAI(
                        api_key=self._api_key,
                        timeout=self._timeout_seconds,
                    ),
                )
            client = self._client
            response = await client.responses.create(
                model=model_reference,
                input=input_text,
                store=False,
            )
        except OpenAIError as error:
            raise ProviderTransportError("OpenAI Responses API request failed.") from error
        if not response.output_text.strip():
            raise ProviderTransportError("OpenAI Responses API returned no text output.")
        return ProviderInvocationResult(
            response.output_text,
            _normalized_usage(response.usage),
            _provider_response_id(response.id),
        )


def _normalized_usage(value: ResponseUsageValue | None) -> InvocationUsage | None:
    if value is None:
        return None
    try:
        return InvocationUsage(value.input_tokens, value.output_tokens, value.total_tokens)
    except (TypeError, ValueError):
        return None


def _provider_response_id(value: str) -> str | None:
    canonical = value.strip()
    if not canonical or len(canonical) > MAX_PROVIDER_RESPONSE_ID_LENGTH:
        return None
    return canonical
