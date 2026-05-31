"""
Claude Code CLI transport.

Invokes the `claude` binary as a subprocess, passing the prompt via stdin
and collecting the response from stdout.  Every failure path raises
TransportUnavailableError so the engine can fall through to the next transport.

WARNING: the `bare` option forces ANTHROPIC_API_KEY / apiKeyHelper authentication
and never reads OAuth or keychain credentials.  Set bare=True only when using an
explicit API key; account/OAuth setups will break.
"""

from __future__ import annotations

# Standard Library
import subprocess

# local repo modules
from local_llm_wrapper.errors import TransportUnavailableError

#============================================


class ClaudeCodeTransport:
	"""
	Transport that delegates to the Claude Code CLI (`claude --print`).

	`max_tokens` and `purpose` are accepted to satisfy the LLMTransport Protocol
	but are not forwarded to the CLI.  max_tokens is an API-account concept; the
	account/OAuth Claude Code CLI path this transport targets handles context limits
	internally and does not expose a max-tokens flag.
	"""

	name = "ClaudeCode"

	def __init__(
		self,
		model: str = "sonnet",
		*,
		effort: str | None = None,
		permission_mode: str = "default",
		tools: str = "",
		session_persistence: bool = False,
		bare: bool = False,
		binary: str = "claude",
		timeout: int = 300,
	) -> None:
		"""
		Initialise a ClaudeCodeTransport.

		Args:
			model: Model alias or full ID passed straight to --model.  No
				normalisation is applied; the CLI accepts aliases such as
				"sonnet", "opus", or full model IDs.
			effort: Optional reasoning-effort level forwarded as --effort.
				None means the flag is omitted entirely.
			permission_mode: Value for --permission-mode.  Callers may pass
				"plan", "acceptEdits", etc.  Defaults to "default" so the model
				answers normally without extra restrictions.
			tools: Value for --tools.  An empty string (the default) disables
				all Claude Code tools, which is the safe default for non-interactive
				use.
			session_persistence: When False (default) emits
				--no-session-persistence so each call is stateless.
			bare: When True, emits --bare.  WARNING: --bare forces
				ANTHROPIC_API_KEY / apiKeyHelper authentication and never reads
				OAuth or keychain credentials.  Opt-in for API-key users only;
				account/OAuth setups will break.
			binary: Path or name of the claude executable.
			timeout: Seconds before the subprocess is killed.
		"""
		self.model = model
		self.effort = effort
		self.permission_mode = permission_mode
		self.tools = tools
		self.session_persistence = bool(session_persistence)
		self.bare = bool(bare)
		self.binary = binary
		self.timeout = int(timeout)

	#============================================
	def _build_argv(self) -> list[str]:
		"""
		Construct the subprocess argument list for the claude CLI.

		The prompt is NOT included here; it is passed via stdin.

		Returns:
			A list of strings ready for subprocess.run(argv, ...).
		"""
		# base flags that are always present
		argv = [
			self.binary,
			"--print",
			"--input-format", "text",
			"--output-format", "text",
			"--model", self.model,
			"--permission-mode", self.permission_mode,
			"--tools", self.tools,
		]
		# stateless sessions unless caller explicitly opts in
		if not self.session_persistence:
			argv.append("--no-session-persistence")
		# bare forces API-key auth; only emit when explicitly requested
		if self.bare:
			argv.append("--bare")
		# effort is optional; omit the flag entirely when not set
		if self.effort is not None:
			argv.extend(["--effort", self.effort])
		return argv

	#============================================
	def generate(self, prompt: str, *, purpose: str, max_tokens: int) -> str:
		"""
		Run the Claude Code CLI with the given prompt and return the response.

		The prompt is delivered via stdin; max_tokens and purpose are accepted
		to satisfy the LLMTransport Protocol but are not forwarded to the CLI.

		Raises:
			TransportUnavailableError: On any failure including missing binary,
				timeout, non-zero exit code, or empty output.
		"""
		argv = self._build_argv()
		try:
			# pass prompt through stdin; capture stdout and stderr separately
			# errors="replace" prevents UnicodeDecodeError under degraded locales
			result = subprocess.run(
				argv,
				input=prompt,
				capture_output=True,
				text=True,
				errors="replace",
				timeout=self.timeout,
			)
		except OSError as exc:
			# catches FileNotFoundError, PermissionError, and other launch-time OS errors
			raise TransportUnavailableError(f"Claude CLI could not be started: {exc}") from exc
		except subprocess.TimeoutExpired as exc:
			raise TransportUnavailableError(
				f"Claude CLI timed out after {self.timeout}s."
			) from exc
		# non-zero return code means the CLI reported an error
		if result.returncode != 0:
			stderr_text = result.stderr.strip()
			if stderr_text:
				# include at most ~1000 chars of stderr to keep the message manageable
				truncated = stderr_text[:1000]
				raise TransportUnavailableError(
					f"Claude CLI exited with code {result.returncode}: {truncated}"
				)
			raise TransportUnavailableError(
				f"Claude CLI exited with code {result.returncode} (no stderr)."
			)
		# strip surrounding whitespace from stdout
		output = result.stdout.strip()
		if not output:
			raise TransportUnavailableError("Claude CLI returned empty output.")
		return output
