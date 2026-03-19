"""Tests for shared agent utilities in _common.py."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from darwin.agents._common import parse_json_response


def _mock_message(text: str, stop_reason: str = "end_turn") -> MagicMock:
    """Create a mock Anthropic message for testing."""
    msg = MagicMock()
    msg.stop_reason = stop_reason
    msg.content = [MagicMock(type="text", text=text)]
    return msg


class TestParseJsonResponse:
    def test_valid_json_parsed(self) -> None:
        """Valid JSON should parse successfully."""
        payload = '{"key": "value"}'
        message = _mock_message(payload)
        result = parse_json_response(message)
        assert result == {"key": "value"}

    def test_json_with_extra_data_parsed(self) -> None:
        """Valid JSON followed by extra text should parse successfully."""
        payload = '{"clusters": [["a"], ["b"]]} This is extra text after JSON.'
        message = _mock_message(payload)
        result = parse_json_response(message)
        assert result == {"clusters": [["a"], ["b"]]}

    def test_array_with_extra_data_parsed(self) -> None:
        """Valid JSON array followed by extra text should parse successfully."""
        payload = '[["a", "b"], ["c", "d"]] Additional text here.'
        message = _mock_message(payload)
        result = parse_json_response(message)
        assert result == [["a", "b"], ["c", "d"]]

    def test_malformed_json_raises(self) -> None:
        """Malformed JSON should still raise JSONDecodeError."""
        payload = '{"invalid": json}'
        message = _mock_message(payload)
        with pytest.raises(json.JSONDecodeError):
            parse_json_response(message)

    def test_markdown_fences_stripped(self) -> None:
        """Markdown fences should be stripped before parsing."""
        payload = '```json\n{"key": "value"}\n```'
        message = _mock_message(payload)
        result = parse_json_response(message)
        assert result == {"key": "value"}

    def test_markdown_fences_with_extra_data(self) -> None:
        """Markdown fences stripped and extra data ignored."""
        payload = '```json\n[["a"], ["b"]]\n``` Some explanation text here.'
        message = _mock_message(payload)
        result = parse_json_response(message)
        assert result == [["a"], ["b"]]

    def test_empty_content_raises(self) -> None:
        """Empty content should raise ValueError."""
        msg = MagicMock()
        msg.content = []
        with pytest.raises(ValueError, match="empty content list"):
            parse_json_response(msg)

    def test_non_text_content_raises(self) -> None:
        """Non-text content should raise ValueError."""
        msg = MagicMock()
        msg.content = [MagicMock(type="image")]
        with pytest.raises(ValueError, match="Expected text content"):
            parse_json_response(msg)

    def test_max_tokens_truncation_raises(self) -> None:
        """Truncated response should raise ValueError."""
        payload = '{"incomplete":'
        message = _mock_message(payload, stop_reason="max_tokens")
        with pytest.raises(ValueError, match="truncated"):
            parse_json_response(message)