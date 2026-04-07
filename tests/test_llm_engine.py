"""
Tests for the LLM engine behavior.
"""

from __future__ import annotations

# Standard Library
from dataclasses import dataclass, field
import pathlib

# Third-Party
import pytest

# local repo modules
import local_llm_wrapper.llm_engine as llm_engine_module
from local_llm_wrapper.errors import GuardrailRefusalError, TransportUnavailableError
from local_llm_wrapper.llm_engine import LLMEngine
from local_llm_wrapper.llm_prompts import (
	RenameRequest,
	SortItem,
	RENAME_EXAMPLE_OUTPUT,
	build_format_fix_prompt,
	build_rename_prompt_minimal,
)
from local_llm_wrapper.llm_utils import format_chat_prompt

#============================================


@dataclass(slots=True)
class ScriptedTransport:
	name: str
	responses: dict[str, str] = field(default_factory=dict)
	errors: dict[str, Exception] = field(default_factory=dict)
	default_response: str | None = None
	default_error: Exception | None = None
	calls: list[str] = field(default_factory=list)

	def generate(self, prompt: str, *, purpose: str, max_tokens: int) -> str:
		self.calls.append(prompt)
		if prompt in self.errors:
			raise self.errors[prompt]
		if prompt in self.responses:
			return self.responses[prompt]
		if self.default_error:
			raise self.default_error
		if self.default_response is None:
			raise RuntimeError("No scripted response for prompt.")
		return self.default_response


@dataclass(slots=True)
class ChatOnlyTransport:
	name: str
	calls: list[list[dict[str, str]]] = field(default_factory=list)

	def generate(self, prompt: str, *, purpose: str, max_tokens: int) -> str:
		raise RuntimeError("Chat-only transport should not use text prompts.")

	def generate_chat(
		self,
		messages: list[dict[str, str]],
		*,
		purpose: str,
		max_tokens: int,
	) -> str:
		self.calls.append(messages)
		return "chat-ok"


def _noop_log_parse_failure(
	*,
	purpose: str,
	error: Exception,
	raw_text: str,
	prompt: str | None = None,
	stage: str | None = None,
	log_path: str = "XML_PARSE_FAILURES.log",
	max_chars: int = 8000,
) -> None:
	return None


#============================================


def test_generate_requires_text_prompt() -> None:
	transport = ScriptedTransport(name="T1", default_response="ok")
	engine = LLMEngine(transports=[transport], quiet=True)
	with pytest.raises(ValueError):
		engine.generate()
	with pytest.raises(TypeError):
		engine.generate(b"bytes")
	with pytest.raises(TypeError):
		engine.generate(pathlib.Path("prompt.txt"))
	with pytest.raises(TypeError):
		engine.generate(messages="nope")


def test_generate_chat_uses_chat_transport() -> None:
	transport = ChatOnlyTransport(name="Chat")
	engine = LLMEngine(transports=[transport], quiet=True)
	messages = [
		{"role": "system", "content": "Be brief."},
		{"role": "user", "content": "Hello"},
	]
	response = engine.generate(messages=messages, max_tokens=32)
	assert response == "chat-ok"
	assert transport.calls == [messages]


def test_generate_chat_falls_back_to_text_prompt() -> None:
	messages = [
		{"role": "system", "content": "Be brief."},
		{"role": "user", "content": "Hello"},
	]
	transport = ScriptedTransport(name="TextOnly", default_response="ok")
	engine = LLMEngine(transports=[transport], quiet=True)
	response = engine.generate(messages=messages, max_tokens=32)
	assert response == "ok"
	assert transport.calls == [format_chat_prompt(messages)]


def test_generate_skips_unavailable_transport() -> None:
	transport_a = ScriptedTransport(
		name="Unavailable",
		default_error=TransportUnavailableError("missing"),
	)
	transport_b = ScriptedTransport(name="OK", default_response="ready")
	engine = LLMEngine(transports=[transport_a, transport_b], quiet=True)
	response = engine.generate("ping")
	assert response == "ready"
	assert len(transport_a.calls) == 1
	assert len(transport_b.calls) == 1


def test_rename_retries_minimal_prompt_on_guardrail() -> None:
	metadata = {"extension": "pdf"}
	req = RenameRequest(metadata=metadata, current_name="input.pdf", context=None)
	minimal_prompt = build_rename_prompt_minimal(req)
	response = "<new_name>My File.pdf</new_name>\n<reason>ok</reason>"
	transport = ScriptedTransport(
		name="Guardrail",
		responses={minimal_prompt: response},
		default_error=GuardrailRefusalError("blocked"),
	)
	engine = LLMEngine(transports=[transport], quiet=True)
	result = engine.rename("input.pdf", metadata)
	assert result.new_name == "My-File.pdf"
	assert result.reason == "ok"
	assert minimal_prompt in transport.calls


def test_rename_retries_minimal_prompt_on_context_error() -> None:
	metadata = {"extension": "pdf"}
	req = RenameRequest(metadata=metadata, current_name="input.pdf", context=None)
	minimal_prompt = build_rename_prompt_minimal(req)
	response = "<new_name>Renamed.pdf</new_name>\n<reason>ok</reason>"
	transport = ScriptedTransport(
		name="ContextWindow",
		responses={minimal_prompt: response},
		default_error=RuntimeError("context window exceeded"),
	)
	engine = LLMEngine(transports=[transport], quiet=True)
	result = engine.rename("input.pdf", metadata)
	assert result.new_name == "Renamed.pdf"
	assert minimal_prompt in transport.calls


def test_rename_retries_format_fix_on_parse_error(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(llm_engine_module, "log_parse_failure", _noop_log_parse_failure)
	metadata = {"extension": "txt"}
	fix_prompt = build_format_fix_prompt(RENAME_EXAMPLE_OUTPUT)
	response = "<new_name>Note.txt</new_name>\n<reason>short</reason>"
	transport = ScriptedTransport(
		name="Formatter",
		responses={fix_prompt: response},
		default_response="not valid xml",
	)
	engine = LLMEngine(transports=[transport], quiet=True)
	result = engine.rename("note.txt", metadata)
	assert result.new_name == "Note.txt"
	assert fix_prompt in transport.calls


def test_rename_format_fix_guardrail_raises(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(llm_engine_module, "log_parse_failure", _noop_log_parse_failure)
	metadata = {"extension": "txt"}
	fix_prompt = build_format_fix_prompt(RENAME_EXAMPLE_OUTPUT)
	transport = ScriptedTransport(
		name="Formatter",
		errors={fix_prompt: GuardrailRefusalError("blocked")},
		default_response="not valid xml",
	)
	engine = LLMEngine(transports=[transport], quiet=True)
	with pytest.raises(GuardrailRefusalError):
		engine.rename("note.txt", metadata)


def test_sort_empty_returns_blank() -> None:
	engine = LLMEngine(transports=[], quiet=True)
	result = engine.sort([])
	assert result.assignments == {}
	assert result.reasons == {}
	assert result.raw_text == ""


def test_sort_assigns_category() -> None:
	response = "<category>Document</category>\n<reason>manual</reason>"
	transport = ScriptedTransport(name="Sorter", default_response=response)
	engine = LLMEngine(transports=[transport], quiet=True)
	item = SortItem(
		path="notes.txt",
		name="notes",
		ext="txt",
		description="meeting notes",
	)
	result = engine.sort([item])
	assert result.assignments["notes.txt"] == "Document"
	assert result.reasons["notes.txt"] == "manual"
