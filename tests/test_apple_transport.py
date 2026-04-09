"""
Tests for AppleTransport dual-backend selection and fallback.

Uses monkeypatching to simulate import failures and event loop states.
"""

# Standard Library
import asyncio

# PIP3 modules
import pytest

# local repo modules
from local_llm_wrapper.errors import ContextWindowError, GuardrailRefusalError, TransportUnavailableError
from local_llm_wrapper.transports.apple import (
	AppleTransport,
	_AppleBackend,
	_can_use_asyncio_run,
)


#============================================
def test_can_use_asyncio_run_no_loop():
	"""No running event loop means asyncio.run() is safe."""
	result = _can_use_asyncio_run()
	assert result is True


#============================================
def test_can_use_asyncio_run_with_loop():
	"""Running event loop means asyncio.run() is not safe."""
	loop = asyncio.new_event_loop()
	# run a coroutine that checks from inside a loop
	async def check():
		return _can_use_asyncio_run()
	result = loop.run_until_complete(check())
	loop.close()
	assert result is False


#============================================
def test_fm_sdk_unavailable_falls_back_to_afm(monkeypatch):
	"""When fm-sdk import fails, transport falls back to afm."""
	# make fm-sdk adapter always unavailable
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._generate_via_fm_sdk",
		_raise_unavailable_fm_sdk,
	)
	# make afm adapter return a known value
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._generate_via_afm",
		_return_afm_response,
	)
	transport = AppleTransport()
	result = transport.generate("test", purpose="test", max_tokens=100)
	assert result == "afm-response"


#============================================
def test_event_loop_running_falls_back_to_afm(monkeypatch):
	"""When event loop is running, fm-sdk is skipped and afm is used."""
	# make fm-sdk raise due to event loop
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._generate_via_fm_sdk",
		_raise_unavailable_event_loop,
	)
	# make afm adapter return a known value
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._generate_via_afm",
		_return_afm_response,
	)
	transport = AppleTransport()
	result = transport.generate("test", purpose="test", max_tokens=100)
	assert result == "afm-response"


#============================================
def test_both_unavailable_raises_combined_error(monkeypatch):
	"""When both backends fail, error message includes both reasons."""
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._generate_via_fm_sdk",
		_raise_unavailable_fm_sdk,
	)
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._generate_via_afm",
		_raise_unavailable_afm,
	)
	transport = AppleTransport()
	with pytest.raises(TransportUnavailableError) as exc_info:
		transport.generate("test", purpose="test", max_tokens=100)
	msg = str(exc_info.value)
	# both backend names should appear in the error
	assert "apple-fm-sdk" in msg
	assert "apple-foundation-models" in msg


#============================================
def test_guardrail_error_no_fallback(monkeypatch):
	"""GuardrailRefusalError from fm-sdk propagates without fallback."""
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._generate_via_fm_sdk",
		_raise_guardrail,
	)
	# afm should never be called
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._generate_via_afm",
		_should_not_be_called,
	)
	# make selector prefer fm-sdk
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._select_apple_backend",
		lambda: _AppleBackend.FM_SDK,
	)
	transport = AppleTransport()
	with pytest.raises(GuardrailRefusalError):
		transport.generate("test", purpose="test", max_tokens=100)


#============================================
def test_context_window_error_falls_back(monkeypatch):
	"""ContextWindowError from fm-sdk triggers fallback to afm."""
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._generate_via_fm_sdk",
		_raise_context_window,
	)
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._generate_via_afm",
		_return_afm_response,
	)
	# make selector prefer fm-sdk
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._select_apple_backend",
		lambda: _AppleBackend.FM_SDK,
	)
	transport = AppleTransport()
	result = transport.generate("test", purpose="test", max_tokens=100)
	assert result == "afm-response"


#============================================
def test_both_context_window_raises_context_error(monkeypatch):
	"""When both backends raise ContextWindowError, final error is ContextWindowError."""
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._generate_via_fm_sdk",
		_raise_context_window,
	)
	monkeypatch.setattr(
		"local_llm_wrapper.transports.apple._generate_via_afm",
		_raise_context_window_afm,
	)
	transport = AppleTransport()
	with pytest.raises(ContextWindowError) as exc_info:
		transport.generate("test", purpose="test", max_tokens=100)
	# should mention both backends
	msg = str(exc_info.value)
	assert "Both Apple backends" in msg


# ---- test helpers ----

#============================================
def _raise_unavailable_fm_sdk(prompt, instructions, temperature, max_tokens, max_retries):
	raise TransportUnavailableError("apple-fm-sdk is not installed.")


#============================================
def _raise_unavailable_event_loop(prompt, instructions, temperature, max_tokens, max_retries):
	raise TransportUnavailableError("apple-fm-sdk: event loop already running.")


#============================================
def _raise_unavailable_afm(prompt, instructions, temperature, max_tokens, max_retries):
	raise TransportUnavailableError("apple-foundation-models is not installed.")


#============================================
def _return_afm_response(prompt, instructions, temperature, max_tokens, max_retries):
	return "afm-response"


#============================================
def _raise_guardrail(prompt, instructions, temperature, max_tokens, max_retries):
	raise GuardrailRefusalError("content refused")


#============================================
def _raise_context_window(prompt, instructions, temperature, max_tokens, max_retries):
	raise ContextWindowError("fm-sdk context exceeded")


#============================================
def _raise_context_window_afm(prompt, instructions, temperature, max_tokens, max_retries):
	raise ContextWindowError("afm context exceeded")


#============================================
def _should_not_be_called(prompt, instructions, temperature, max_tokens, max_retries):
	raise AssertionError("This adapter should not have been called.")
