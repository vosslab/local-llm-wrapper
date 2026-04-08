"""
Tests for LLM utility helpers.
"""

from __future__ import annotations

# Third-Party
import pytest

# local repo modules
import local_llm_wrapper.llm_utils as llm_utils

#============================================


def test_sanitize_filename_basic() -> None:
	result = llm_utils.sanitize_filename("My File!.pdf")
	assert result == "My-File-.pdf"


def test_sanitize_filename_trims_noise() -> None:
	result = llm_utils.sanitize_filename("--__Report__--")
	assert result == "Report"


def test_normalize_reason_strips_placeholders() -> None:
	assert llm_utils.normalize_reason("short reason") == ""
	assert llm_utils.normalize_reason("N/A") == ""


def test_extract_xml_tag_content_uses_last_tag() -> None:
	text = "<response>old</response>\n<response>new</response>"
	assert llm_utils.extract_xml_tag_content(text, "response") == "new"


def test_sanitize_prompt_text_removes_code_fences() -> None:
	text = "```code```\nline"
	result = llm_utils._sanitize_prompt_text(text)
	assert "```" not in result
	assert "code" in result


def test_sanitize_prompt_list_from_scalar() -> None:
	result = llm_utils._sanitize_prompt_list("hello")
	assert result == ["hello"]


def test_prompt_excerpt_prefers_summary() -> None:
	metadata = {"summary": "short text", "description": "long text"}
	assert llm_utils._prompt_excerpt(metadata) == "short text"


def test_compute_stem_features_basic() -> None:
	features = llm_utils.compute_stem_features("IMG_1234", "photo")
	assert features["has_letter"] is True
	assert features["is_numeric_only"] is False


def test_choose_model_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(llm_utils, "get_vram_size_in_gb", lambda: 0)
	monkeypatch.setattr(llm_utils, "total_ram_bytes_in_gb", lambda: 0)
	assert llm_utils.choose_model("custom") == "custom"


def test_choose_model_prefers_vram(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(llm_utils, "get_vram_size_in_gb", lambda: 64)
	monkeypatch.setattr(llm_utils, "total_ram_bytes_in_gb", lambda: 0)
	assert llm_utils.choose_model(None) == "qwen3.5:27b-q4_K_M"
