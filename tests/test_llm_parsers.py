"""
Tests for structured response parsing.
"""

from __future__ import annotations

# Third-Party
import pytest

# local repo modules
from local_llm_wrapper.llm_parsers import (
	ParseError,
	parse_keep_response,
	parse_rename_response,
	parse_sort_response,
	parse_tag_response,
)

#============================================


def test_parse_rename_response_ok() -> None:
	text = "<new_name>Report.pdf</new_name>\n<reason>short</reason>"
	result = parse_rename_response(text)
	assert result.new_name == "Report.pdf"
	assert result.reason == "short"


def test_parse_rename_response_missing_new_name() -> None:
	with pytest.raises(ParseError):
		parse_rename_response("<reason>short</reason>")


def test_parse_keep_response_with_keep_original() -> None:
	text = "<keep_original>true</keep_original>\n<reason>stem has a model</reason>"
	result = parse_keep_response(text, "abc")
	assert result.stem_action == "keep"
	assert result.reason == "stem has a model"


def test_parse_keep_response_invalid_action() -> None:
	text = "<stem_action>maybe</stem_action>\n<reason>no</reason>"
	with pytest.raises(ParseError):
		parse_keep_response(text, "abc")


def test_parse_sort_response_expected_path_only() -> None:
	text = "<category>Document</category>"
	with pytest.raises(ParseError):
		parse_sort_response(text, ["a.txt", "b.txt"])


def test_parse_sort_response_reason_optional() -> None:
	text = "<category>Document</category>"
	result = parse_sort_response(text, ["a.txt"])
	assert result.assignments["a.txt"] == "Document"
	assert result.reasons == {}


def test_parse_tag_response_ok() -> None:
	text = "<answer>Hello there.</answer>"
	result = parse_tag_response(text, "answer")
	assert result == "Hello there."


def test_parse_tag_response_missing_tag() -> None:
	with pytest.raises(ParseError):
		parse_tag_response("<reason>nope</reason>", "answer")
