from dataclasses import dataclass

import pytest
from openai import OpenAIError

from valor.runtime_gateway.application.ports import ProviderTransportError
from valor.runtime_gateway.infrastructure.openai_provider import (
    OpenAIResponsesProvider,
    ResponsesResource,
)


@dataclass
class FakeResponse:
    output_text: str


class FakeResponses:
    def __init__(self, output_text: str = "provider output", *, fails: bool = False) -> None:
        self.output_text = output_text
        self.fails = fails
        self.calls: list[tuple[str, str, bool]] = []

    async def create(self, *, model: str, input: str, store: bool) -> FakeResponse:
        self.calls.append((model, input, store))
        if self.fails:
            raise OpenAIError("sensitive upstream detail")
        return FakeResponse(self.output_text)


class FakeOpenAIClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses: ResponsesResource = responses


@pytest.mark.asyncio
async def test_adapter_uses_responses_api_without_openai_storage() -> None:
    responses = FakeResponses()
    provider = OpenAIResponsesProvider(None, client=FakeOpenAIClient(responses))
    result = await provider.invoke(model_reference="gpt-test", input_text="hello")
    assert result.output_text == "provider output"
    assert responses.calls == [("gpt-test", "hello", False)]


@pytest.mark.asyncio
async def test_adapter_translates_openai_sdk_failure() -> None:
    provider = OpenAIResponsesProvider(None, client=FakeOpenAIClient(FakeResponses(fails=True)))
    with pytest.raises(ProviderTransportError) as error:
        await provider.invoke(model_reference="gpt-test", input_text="secret input")
    assert "sensitive upstream detail" not in str(error.value)


@pytest.mark.asyncio
async def test_adapter_rejects_missing_credentials_before_network_call() -> None:
    with pytest.raises(ProviderTransportError, match="credentials are not configured"):
        await OpenAIResponsesProvider(None).invoke(model_reference="gpt-test", input_text="hello")


@pytest.mark.asyncio
async def test_adapter_rejects_empty_provider_output() -> None:
    provider = OpenAIResponsesProvider(None, client=FakeOpenAIClient(FakeResponses("  ")))
    with pytest.raises(ProviderTransportError, match="no text output"):
        await provider.invoke(model_reference="gpt-test", input_text="hello")
