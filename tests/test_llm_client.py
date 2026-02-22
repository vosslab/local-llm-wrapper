"""
Tests for the public LLM client wrapper.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass

# local repo modules
from local_llm_wrapper.llm_client import LLMClient

#============================================


@dataclass(slots=True)
class StubTransport:
	name: str = "Stub"
	response: str = "ok"

	def generate(self, prompt: str, *, purpose: str, max_tokens: int) -> str:
		return self.response


def test_client_generate_returns_text() -> None:
	client = LLMClient(transports=[StubTransport()])
	assert client.generate("hello") == "ok"


def test_client_sort_accepts_dict_items() -> None:
	transport = StubTransport(
		response="<category>Document</category>\n<reason>manual</reason>"
	)
	client = LLMClient(transports=[transport], quiet=True)
	item = {
		"path": "notes.txt",
		"name": "notes",
		"ext": "txt",
		"description": "meeting notes",
	}
	result = client.sort([item])
	assert result.assignments["notes.txt"] == "Document"
