"""
Tests for prompt builders.
"""

from __future__ import annotations

# local repo modules
from local_llm_wrapper.llm_prompts import (
	KeepRequest,
	RenameRequest,
	SortItem,
	SortRequest,
	build_format_fix_prompt,
	build_keep_prompt,
	build_rename_prompt,
	build_sort_prompt,
)

#============================================


def test_build_format_fix_prompt_includes_example() -> None:
	result = build_format_fix_prompt("<tag>ok</tag>")
	lines = result.splitlines()
	assert lines[0] == "Reply with tags only."
	assert lines[1] == "<tag>ok</tag>"


def test_build_rename_prompt_includes_fields() -> None:
	metadata = {
		"title": "Annual Report",
		"keywords": ["alpha", "beta"],
		"summary": "A short summary.",
		"extension": "pdf",
	}
	req = RenameRequest(metadata=metadata, current_name="old.pdf", context=None)
	prompt = build_rename_prompt(req)
	assert "current_name: old.pdf" in prompt
	assert "title: Annual Report" in prompt
	assert "keywords: ['alpha', 'beta']" in prompt
	assert "extension: pdf" in prompt


def test_build_keep_prompt_includes_features() -> None:
	features = {"has_letter": True, "length": 5}
	req = KeepRequest(
		original_stem="file",
		suggested_name="file.pdf",
		extension="pdf",
		features=features,
	)
	prompt = build_keep_prompt(req)
	assert "features:" in prompt
	assert "- has_letter: True" in prompt


def test_build_sort_prompt_includes_categories_and_file() -> None:
	item = SortItem(path="notes.txt", name="notes", ext="txt", description="meeting")
	req = SortRequest(files=[item], context=None)
	prompt = build_sort_prompt(req)
	assert "Allowed categories:" in prompt
	assert "- Document" in prompt
	assert "path=notes.txt" in prompt
