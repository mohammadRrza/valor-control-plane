"""OpenAI Responses API adapter for simple text generation."""

from typing import Protocol, cast

from openai import AsyncOpenAI, OpenAIError

from valor.runtime_gateway.application.ports import (
    ModelProviderPort,
    ProviderInvocationResult,
    ProviderTransportError,
)


class ResponseValue(Protocol):
    output_text: str


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
        return ProviderInvocationResult(response.output_text)
