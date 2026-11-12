"""Log redaction uses synthetic secrets only and never sends network requests."""

import io
import logging

import pytest
from app.core.logging import SensitiveFilter


@pytest.mark.parametrize(
    "query_key",
    ["X-Tos-Signature", "X-Tos-Credential", "token", "access_token", "X-Amz-Security-Token"],
)
def test_httpx_formatted_url_query_is_redacted_before_handler_output(query_key):
    secret = "fake-sensitive-value%2F20261107%2Fscope"
    url = f"https://example.invalid/image.png?{query_key}={secret}&width=512"
    record = logging.LogRecord(
        "httpx",
        logging.INFO,
        __file__,
        1,
        'HTTP Request: %s %s "%s %d %s"',
        ("GET", url, "HTTP/1.1", 200, "OK"),
        None,
    )
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(logging.Formatter("[%(request_id)s] %(message)s"))
    handler.addFilter(SensitiveFilter())
    handler.handle(record)
    rendered = output.getvalue()
    assert secret not in rendered
    assert f"{query_key}=***REDACTED***&width=512" in rendered
    assert rendered.startswith("[-] HTTP Request: GET https://example.invalid/")
    assert '"HTTP/1.1 200 OK"' in rendered
    assert record.args == ()


def test_mapping_args_all_signed_query_fields_and_request_context_survive_repeat_filter():
    record = logging.LogRecord(
        "httpx",
        logging.INFO,
        __file__,
        1,
        "download %(url)s",
        (
            {
                "url": (
                    "https://example.invalid/image?X-Tos-Signature=fake-signature"
                    "&X-Tos-Credential=fake-credential&token=fake-token&width=64"
                )
            },
        ),
        None,
    )
    record.request_id = "request-test-123"
    sensitive_filter = SensitiveFilter()
    assert sensitive_filter.filter(record)
    first = record.getMessage()
    assert sensitive_filter.filter(record)
    assert record.getMessage() == first
    assert record.request_id == "request-test-123"
    for secret in ("fake-signature", "fake-credential", "fake-token"):
        assert secret not in first
    assert first.count("***REDACTED***") == 3
    assert first.endswith("&width=64")


@pytest.mark.parametrize(
    "key", ["password", "api_key", "apikey", "token", "secret", "code", "auth"]
)
def test_plain_key_value_and_formatted_value_keep_existing_redaction(key):
    record = logging.LogRecord(
        "app", logging.INFO, __file__, 1, f"{key}=%s, action=save", ("fake-secret",), None
    )
    assert SensitiveFilter().filter(record)
    assert record.getMessage() == f"{key}=***REDACTED***, action=save"


def test_non_string_message_remains_loggable():
    record = logging.LogRecord("app", logging.INFO, __file__, 1, {"status": "ready"}, (), None)
    assert SensitiveFilter().filter(record)
    assert record.getMessage() == "{'status': 'ready'}"
