"""
Tests for ClaudeCodeTransport argv construction and generate() behavior.

All subprocess.run calls are monkeypatched; no real CLI or network calls occur.
"""

# Standard Library
import subprocess

# PIP3 modules
import pytest

# local repo modules
from local_llm_wrapper.errors import TransportUnavailableError
from local_llm_wrapper.transports.claude_code import ClaudeCodeTransport


#============================================
# Helpers

class _FakeResult:
	"""Minimal stand-in for subprocess.CompletedProcess."""
	def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
		self.returncode = returncode
		self.stdout = stdout
		self.stderr = stderr


class _SubprocessRecorder:
	"""Records the most recent call kwargs passed to a fake subprocess.run."""
	def __init__(self, result: _FakeResult) -> None:
		self._result = result
		self.call_kwargs: dict = {}
		self.call_args: list = []

	def __call__(self, argv, **kwargs):
		self.call_args = list(argv)
		self.call_kwargs = kwargs
		return self._result


#============================================
def test_generate_passes_prompt_via_stdin(monkeypatch):
	"""generate() passes the prompt as input= kwarg, not in argv."""
	prompt = "what is 2+2?"
	recorder = _SubprocessRecorder(_FakeResult(returncode=0, stdout="4\n"))
	monkeypatch.setattr("local_llm_wrapper.transports.claude_code.subprocess.run", recorder)
	transport = ClaudeCodeTransport()
	transport.generate(prompt, purpose="test", max_tokens=100)
	# prompt must appear as the input kwarg
	assert recorder.call_kwargs["input"] == prompt
	# prompt must NOT appear in the argv list
	assert prompt not in recorder.call_args


#============================================
def test_generate_subprocess_kwargs(monkeypatch):
	"""generate() calls subprocess.run with text, capture_output, and timeout."""
	recorder = _SubprocessRecorder(_FakeResult(returncode=0, stdout="result\n"))
	monkeypatch.setattr("local_llm_wrapper.transports.claude_code.subprocess.run", recorder)
	transport = ClaudeCodeTransport(timeout=42)
	transport.generate("hello", purpose="test", max_tokens=100)
	assert recorder.call_kwargs.get("text") is True
	assert recorder.call_kwargs.get("capture_output") is True
	assert recorder.call_kwargs.get("timeout") == 42


#============================================
def test_generate_special_chars_pass_through(monkeypatch):
	"""Prompt with spaces, quotes, newline, and non-ASCII char passes through input= unchanged."""
	# non-ASCII char kept as escaped unicode per repo ASCII rule; \xe9 is 'e' with acute accent
	special_prompt = "hello world \"it's\" a\nnewline caf\xe9"
	recorder = _SubprocessRecorder(_FakeResult(returncode=0, stdout="ok\n"))
	monkeypatch.setattr("local_llm_wrapper.transports.claude_code.subprocess.run", recorder)
	transport = ClaudeCodeTransport()
	transport.generate(special_prompt, purpose="test", max_tokens=100)
	assert recorder.call_kwargs["input"] == special_prompt


#============================================
def test_file_not_found_raises_transport_error(monkeypatch):
	"""FileNotFoundError from subprocess.run -> TransportUnavailableError."""
	def _raise(_argv, **_kw):
		raise FileNotFoundError("claude: not found")
	monkeypatch.setattr("local_llm_wrapper.transports.claude_code.subprocess.run", _raise)
	transport = ClaudeCodeTransport()
	with pytest.raises(TransportUnavailableError):
		transport.generate("test", purpose="test", max_tokens=100)


#============================================
def test_permission_error_raises_transport_error(monkeypatch):
	"""PermissionError from subprocess.run -> TransportUnavailableError."""
	def _raise(_argv, **_kw):
		raise PermissionError("claude: permission denied")
	monkeypatch.setattr("local_llm_wrapper.transports.claude_code.subprocess.run", _raise)
	transport = ClaudeCodeTransport()
	with pytest.raises(TransportUnavailableError):
		transport.generate("test", purpose="test", max_tokens=100)


#============================================
def test_timeout_expired_raises_transport_error(monkeypatch):
	"""subprocess.TimeoutExpired -> TransportUnavailableError."""
	def _raise(_argv, **_kw):
		raise subprocess.TimeoutExpired(cmd="claude", timeout=300)
	monkeypatch.setattr("local_llm_wrapper.transports.claude_code.subprocess.run", _raise)
	transport = ClaudeCodeTransport()
	with pytest.raises(TransportUnavailableError):
		transport.generate("test", purpose="test", max_tokens=100)


#============================================
def test_nonzero_exit_long_stderr_truncated(monkeypatch):
	"""returncode=1 with long stderr -> TransportUnavailableError; stderr capped at 1000 chars."""
	long_stderr = "E" * 5000
	stdout_content = "STDOUT_SHOULD_NOT_APPEAR"
	fake = _FakeResult(returncode=1, stdout=stdout_content, stderr=long_stderr)
	monkeypatch.setattr("local_llm_wrapper.transports.claude_code.subprocess.run", lambda *a, **k: fake)
	transport = ClaudeCodeTransport()
	with pytest.raises(TransportUnavailableError) as exc_info:
		transport.generate("test", purpose="test", max_tokens=100)
	msg = str(exc_info.value)
	# stderr was truncated: message must be shorter than the full stderr input
	assert len(msg) < len(long_stderr)
	# stdout content must not appear in the error message
	assert stdout_content not in msg


#============================================
def test_nonzero_exit_empty_stderr_names_return_code(monkeypatch):
	"""returncode=2 with empty stderr -> TransportUnavailableError naming the return code."""
	fake = _FakeResult(returncode=2, stdout="", stderr="")
	monkeypatch.setattr("local_llm_wrapper.transports.claude_code.subprocess.run", lambda *a, **k: fake)
	transport = ClaudeCodeTransport()
	with pytest.raises(TransportUnavailableError) as exc_info:
		transport.generate("test", purpose="test", max_tokens=100)
	msg = str(exc_info.value)
	# the return code value should appear in the message
	assert "2" in msg


#============================================
def test_empty_output_raises_transport_error(monkeypatch):
	"""returncode=0 with whitespace-only stdout -> TransportUnavailableError."""
	fake = _FakeResult(returncode=0, stdout="  \n")
	monkeypatch.setattr("local_llm_wrapper.transports.claude_code.subprocess.run", lambda *a, **k: fake)
	transport = ClaudeCodeTransport()
	with pytest.raises(TransportUnavailableError):
		transport.generate("test", purpose="test", max_tokens=100)


#============================================
def test_success_returns_stripped_output(monkeypatch):
	"""returncode=0 with stdout='4\n' -> generate() returns '4'."""
	fake = _FakeResult(returncode=0, stdout="4\n")
	monkeypatch.setattr("local_llm_wrapper.transports.claude_code.subprocess.run", lambda *a, **k: fake)
	transport = ClaudeCodeTransport()
	result = transport.generate("what is 2+2?", purpose="test", max_tokens=100)
	assert result == "4"


#============================================
def test_default_model_none_omits_model_flag():
	"""Default construction (model=None) -> _build_argv() does NOT contain '--model'."""
	transport = ClaudeCodeTransport()
	argv = transport._build_argv()
	assert "--model" not in argv
