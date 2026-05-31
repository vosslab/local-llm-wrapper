"""
Tests for CodexTransport argv construction and generate() behavior.

All subprocess.run calls are monkeypatched; no real CLI, network, or file I/O
occurs except within the tmp_path fixture (for the output-last-message file
that the fake subprocess writes on behalf of the real codex binary).
"""

# Standard Library
import os
import subprocess

# PIP3 modules
import pytest

# local repo modules
from local_llm_wrapper.errors import TransportUnavailableError
from local_llm_wrapper.transports.codex_cli import CodexTransport


#============================================
# Helpers

class _FakeResult:
	"""Minimal stand-in for subprocess.CompletedProcess."""
	def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
		self.returncode = returncode
		self.stdout = stdout
		self.stderr = stderr


def _make_recorder(fake_result: _FakeResult, fake_output: str | None = None):
	"""
	Return a callable that records argv/kwargs and optionally writes fake_output
	to the --output-last-message path before returning fake_result.

	Args:
		fake_result: The _FakeResult to return.
		fake_output: If not None, written to the output file so generate() can read it.
	"""
	# use a dict so the closure can mutate captured state without nonlocal
	state: dict = {"argv": [], "kwargs": {}, "output_path": None}

	def _recorder(argv, **kwargs):
		state["argv"] = list(argv)
		state["kwargs"] = kwargs
		# find --output-last-message and write fake text to that path
		if fake_output is not None and "--output-last-message" in argv:
			idx = argv.index("--output-last-message")
			out_path = argv[idx + 1]
			state["output_path"] = out_path
			with open(out_path, "w", encoding="utf-8") as fh:
				fh.write(fake_output)
		return fake_result

	_recorder.state = state
	return _recorder


#============================================
def test_success_round_trip(monkeypatch):
	"""Fake writes '4' to the output file -> generate() returns '4'."""
	recorder = _make_recorder(_FakeResult(returncode=0), fake_output="4")
	monkeypatch.setattr("local_llm_wrapper.transports.codex_cli.subprocess.run", recorder)
	transport = CodexTransport()
	result = transport.generate("what is 2+2?", purpose="test", max_tokens=100)
	assert result == "4"


#============================================
def test_empty_output_raises_transport_error(monkeypatch):
	"""Fake writes empty string to output file -> TransportUnavailableError."""
	# write whitespace only so the strip() check triggers
	recorder = _make_recorder(_FakeResult(returncode=0), fake_output="   \n")
	monkeypatch.setattr("local_llm_wrapper.transports.codex_cli.subprocess.run", recorder)
	transport = CodexTransport()
	with pytest.raises(TransportUnavailableError):
		transport.generate("hello", purpose="test", max_tokens=100)


#============================================
def test_missing_output_file_raises_transport_error(monkeypatch):
	"""Fake does NOT write the output file -> generate() raises TransportUnavailableError."""
	# fake_output=None means the recorder never writes the file; codex left it empty (0 bytes)
	# but the real path still exists from mkstemp -- delete it to simulate FileNotFoundError
	def _deleting_recorder(argv, **kwargs):
		# find and delete the output file before returning so open() raises FileNotFoundError
		if "--output-last-message" in argv:
			idx = argv.index("--output-last-message")
			out_path = argv[idx + 1]
			try:
				os.unlink(out_path)
			except OSError:
				pass
		return _FakeResult(returncode=0)

	monkeypatch.setattr("local_llm_wrapper.transports.codex_cli.subprocess.run", _deleting_recorder)
	transport = CodexTransport()
	with pytest.raises(TransportUnavailableError):
		transport.generate("hello", purpose="test", max_tokens=100)


#============================================
def test_nonzero_exit_raises_transport_error_without_stdout(monkeypatch):
	"""returncode=1 -> TransportUnavailableError; stdout sentinel not in error message."""
	stdout_sentinel = "STDOUT_MUST_NOT_LEAK"
	long_stderr = "error line\n" * 200
	fake = _FakeResult(returncode=1, stdout=stdout_sentinel, stderr=long_stderr)
	monkeypatch.setattr(
		"local_llm_wrapper.transports.codex_cli.subprocess.run",
		lambda *a, **k: fake,
	)
	transport = CodexTransport()
	with pytest.raises(TransportUnavailableError) as exc_info:
		transport.generate("test", purpose="test", max_tokens=100)
	assert stdout_sentinel not in str(exc_info.value)


#============================================
def test_oserror_raises_transport_error(monkeypatch):
	"""subprocess.run raises OSError -> TransportUnavailableError."""
	def _raise(_argv, **_kw):
		raise OSError("codex: not found")
	monkeypatch.setattr("local_llm_wrapper.transports.codex_cli.subprocess.run", _raise)
	transport = CodexTransport()
	with pytest.raises(TransportUnavailableError):
		transport.generate("test", purpose="test", max_tokens=100)


#============================================
def test_timeout_expired_raises_transport_error(monkeypatch):
	"""subprocess.TimeoutExpired -> TransportUnavailableError."""
	def _raise(_argv, **_kw):
		raise subprocess.TimeoutExpired(cmd="codex", timeout=300)
	monkeypatch.setattr("local_llm_wrapper.transports.codex_cli.subprocess.run", _raise)
	transport = CodexTransport()
	with pytest.raises(TransportUnavailableError):
		transport.generate("test", purpose="test", max_tokens=100)


#============================================
def test_stdin_delivery_not_in_argv(monkeypatch):
	"""generate() passes prompt as input= kwarg; prompt does not appear in argv."""
	prompt = "explain recursion"
	recorder = _make_recorder(_FakeResult(returncode=0), fake_output="ok")
	monkeypatch.setattr("local_llm_wrapper.transports.codex_cli.subprocess.run", recorder)
	transport = CodexTransport()
	transport.generate(prompt, purpose="test", max_tokens=100)
	assert recorder.state["kwargs"]["input"] == prompt
	assert prompt not in recorder.state["argv"]


#============================================
def test_temp_file_cleaned_up_on_success_and_error(monkeypatch):
	"""Output temp file is deleted after a successful run AND after a failed run."""
	# --- success path ---
	recorder_ok = _make_recorder(_FakeResult(returncode=0), fake_output="ok")
	monkeypatch.setattr("local_llm_wrapper.transports.codex_cli.subprocess.run", recorder_ok)
	transport = CodexTransport()
	transport.generate("hello", purpose="test", max_tokens=100)
	captured_path = recorder_ok.state["output_path"]
	assert captured_path is not None, "recorder did not capture output_path"
	assert not os.path.exists(captured_path), f"temp file not cleaned up: {captured_path}"

	# --- error path ---
	recorder_err = _make_recorder(_FakeResult(returncode=1, stderr="boom"), fake_output=None)
	monkeypatch.setattr("local_llm_wrapper.transports.codex_cli.subprocess.run", recorder_err)
	with pytest.raises(TransportUnavailableError):
		transport.generate("hello", purpose="test", max_tokens=100)
	# on error the recorder does not write the file; the temp file must still be cleaned.
	# --output-last-message is always emitted, so derive the path unconditionally (no guard
	# that could let the assert silently skip).
	err_argv = recorder_err.state["argv"]
	err_path = err_argv[err_argv.index("--output-last-message") + 1]
	assert not os.path.exists(err_path), f"temp file leaked on error: {err_path}"


#============================================
def test_default_argv_contains_sandbox_read_only(monkeypatch):
	"""Default argv contains '--sandbox' immediately followed by 'read-only'."""
	recorder = _make_recorder(_FakeResult(returncode=0), fake_output="ok")
	monkeypatch.setattr("local_llm_wrapper.transports.codex_cli.subprocess.run", recorder)
	transport = CodexTransport()
	transport.generate("hello", purpose="test", max_tokens=100)
	argv = recorder.state["argv"]
	# safety: read-only sandbox must be present; codex exec is non-interactive by design
	assert "--sandbox" in argv
	assert argv[argv.index("--sandbox") + 1] == "read-only"
