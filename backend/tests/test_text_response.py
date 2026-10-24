"""Real-provider failures must be visible instead of becoming successful empty replies."""
import logging

import httpx
import pytest
from app.core.logging import SensitiveFilter
from app.providers.text.base import TextProviderError
from app.providers.text.openai_compatible import OpenAICompatibleTextProvider, _parse_structured


def test_external_logger_has_request_context_and_preserves_existing_context():
    record = logging.LogRecord("httpx", logging.INFO, "", 0, "HTTP Request", (), None)
    SensitiveFilter().filter(record)
    assert logging.Formatter("[%(request_id)s] %(message)s").format(record) == "[-] HTTP Request"
    record.request_id = "existing"
    SensitiveFilter().filter(record)
    assert record.request_id == "existing"


def test_structured_response_rejects_non_object_json():
    with pytest.raises(TextProviderError, match="JSON 对象"):
        _parse_structured('["unexpected"]')


@pytest.mark.parametrize("payload", [{"choices": []}, {"choices": [{"message": {"content": ""}}]}, []])
async def test_empty_or_malformed_response_is_visible(monkeypatch, payload):
    async def post(self, *args, **kwargs):
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    with pytest.raises(TextProviderError) as failure:
        await OpenAICompatibleTextProvider().generate([{"role": "user", "content": "test"}], structured=True)
    assert failure.value.code == "AGENT_OUTPUT_INVALID"
