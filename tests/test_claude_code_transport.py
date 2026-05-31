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
def test_default_argv_contains_tools_empty():
	"""Default construction emits --tools followed by an empty string."""
	transport = ClaudeCodeTransport()
	argv = transport._build_argv()
	# find position of --tools and check the next element is ""
	assert "--tools" in argv
	tools_index = argv.index("--tools")
	assert argv[tools_index + 1] == ""


#============================================
def test_default_argv_contains_permission_mode_default():
	"""Default construction emits --permission-mode default."""
	transport = ClaudeCodeTransport()
	argv = transport._build_argv()
	assert "--permission-mode" in argv
	perm_index = argv.index("--permission-mode")
	assert argv[perm_index + 1] == "default"


#============================================
def test_default_argv_contains_input_output_format_text():
	"""Default construction emits --input-format text and --output-format text."""
	transport = ClaudeCodeTransport()
	argv = transport._build_argv()
	assert "--input-format" in argv
	assert argv[argv.index("--input-format") + 1] == "text"
	assert "--output-format" in argv
	assert argv[argv.index("--output-format") + 1] == "text"


#============================================
def test_default_argv_contains_no_session_persistence():
	"""Default construction emits --no-session-persistence."""
	transport = ClaudeCodeTransport()
	argv = transport._build_argv()
	assert "--no-session-persistence" in argv


#============================================
def test_default_argv_does_not_contain_bare():
	"""Default construction does NOT emit --bare."""
	transport = ClaudeCodeTransport()
	argv = transport._build_argv()
	assert "--bare" not in argv


#============================================
def test_passthrough_permission_mode_plan():
	"""permission_mode='plan' appears verbatim in argv."""
	transport = ClaudeCodeTransport(permission_mode="plan")
	argv = transport._build_argv()
	perm_index = argv.index("--permission-mode")
	assert argv[perm_index + 1] == "plan"


#============================================
def test_passthrough_tools_default():
	"""tools='default' appears verbatim in argv."""
	transport = ClaudeCodeTransport(tools="default")
	argv = transport._build_argv()
	tools_index = argv.index("--tools")
	assert argv[tools_index + 1] == "default"


#============================================
def test_effort_high_included():
	"""effort='high' adds --effort high to argv."""
	transport = ClaudeCodeTransport(effort="high")
	argv = transport._build_argv()
	assert "--effort" in argv
	effort_index = argv.index("--effort")
	assert argv[effort_index + 1] == "high"


#============================================
def test_effort_none_omitted():
	"""effort=None (default) omits the --effort flag entirely."""
	transport = ClaudeCodeTransport(effort=None)
	argv = transport._build_argv()
	assert "--effort" not in argv


#============================================
def test_bare_true_adds_bare_flag():
	"""bare=True emits --bare in argv."""
	transport = ClaudeCodeTransport(bare=True)
	argv = transport._build_argv()
	assert "--bare" in argv


#============================================
def test_session_persistence_true_omits_no_session_flag():
	"""session_persistence=True means --no-session-persistence is absent."""
	transport = ClaudeCodeTransport(session_persistence=True)
	argv = transport._build_argv()
	assert "--no-session-persistence" not in argv


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
