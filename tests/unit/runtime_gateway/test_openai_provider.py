from dataclasses import dataclass

import pytest
from openai import OpenAIError

from valor.runtime_gateway.application.ports import ProviderTransportError
from valor.runtime_gateway.domain.usage import InvocationUsage
from valor.runtime_gateway.infrastructure.openai_provider import (
    OpenAIResponsesProvider,
    ResponsesResource,
    ResponseUsageValue,
)


@dataclass
class FakeResponse:
    output_text: str
    id: str = "resp_test_123"
    usage: ResponseUsageValue | None = None


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int


class FakeResponses:
    def __init__(
        self,
        output_text: str = "provider output",
        *,
        fails: bool = False,
        usage: ResponseUsageValue | None = None,
        response_id: str = "resp_test_123",
    ) -> None:
        self.output_text = output_text
        self.fails = fails
        self.calls: list[tuple[str, str, bool]] = []
        self.usage = usage
        self.response_id = response_id

    async def create(self, *, model: str, input: str, store: bool) -> FakeResponse:
        self.calls.append((model, input, store))
        if self.fails:
            raise OpenAIError("sensitive upstream detail")
        return FakeResponse(self.output_text, self.response_id, self.usage)


class FakeOpenAIClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses: ResponsesResource = responses


@pytest.mark.asyncio
async def test_adapter_uses_responses_api_without_openai_storage() -> None:
    responses = FakeResponses()
    provider = OpenAIResponsesProvider(None, client=FakeOpenAIClient(responses))
    result = await provider.invoke(model_reference="gpt-test", input_text="hello")
    assert result.output_text == "provider output"
    assert result.provider_response_id == "resp_test_123"
    assert result.usage is None
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


@pytest.mark.asyncio
async def test_adapter_normalizes_openai_usage_and_response_identity() -> None:
    responses = FakeResponses(
        usage=FakeUsage(input_tokens=11, output_tokens=7, total_tokens=18),
        response_id=" resp_456 ",
    )
    result = await OpenAIResponsesProvider(None, client=FakeOpenAIClient(responses)).invoke(
        model_reference="gpt-test", input_text="hello"
    )
    assert result.usage == InvocationUsage(11, 7, 18)
    assert result.provider_response_id == "resp_456"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("usage", "response_id"),
    [
        (FakeUsage(-1, 2, 1), "resp_valid"),
        (FakeUsage(10, 2, 3), "resp_valid"),
        (None, " "),
        (None, "x" * 256),
    ],
)
async def test_adapter_discards_malformed_optional_metadata(
    usage: ResponseUsageValue | None, response_id: str
) -> None:
    result = await OpenAIResponsesProvider(
        None,
        client=FakeOpenAIClient(FakeResponses(usage=usage, response_id=response_id)),
    ).invoke(model_reference="gpt-test", input_text="hello")
    if usage is not None:
        assert result.usage is None
    assert result.provider_response_id == ("resp_valid" if response_id == "resp_valid" else None)
