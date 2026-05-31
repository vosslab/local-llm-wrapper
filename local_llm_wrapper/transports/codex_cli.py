"""
Codex CLI transport.

Invokes the `codex exec` binary as a subprocess, passing the prompt via stdin
and collecting the final message from a temp file written by --output-last-message.
Every failure path raises TransportUnavailableError so the engine can fall through
to the next transport.

NOTE: --sandbox read-only prevents workspace writes but does NOT make Codex a
passive text model -- it may still run read-only inspection commands.  Advanced
behavior (session, cwd, profiles) is controlled by the user's ~/.codex/config.toml,
not by this wrapper.
"""

from __future__ import annotations

# Standard Library
import os
import subprocess
import tempfile

# local repo modules
from local_llm_wrapper.errors import TransportUnavailableError

#============================================


class CodexTransport:
	"""
	Transport that delegates to the OpenAI Codex CLI (`codex exec`).

	`max_tokens` and `purpose` are accepted to satisfy the LLMTransport Protocol
	but are not forwarded to the CLI.  max_tokens is an API-account concept; the
	account/OAuth Codex CLI path this transport targets handles context limits
	internally and does not expose a max-tokens flag.

	The safety boundary is the read-only sandbox (--sandbox read-only), hardcoded
	and not configurable via the constructor.  `codex exec` is non-interactive by
	design; no approval flag is needed or accepted.  Advanced Codex behavior should
	be set in the user's ~/.codex/config.toml before invoking this transport.
	"""

	name = "Codex"

	def __init__(
		self,
		model: str | None = None,
		*,
		binary: str = "codex",
		timeout: int = 300,
	) -> None:
		"""
		Initialise a CodexTransport.

		Args:
			model: Model alias or full ID passed straight to -m/--model.  No
				normalisation is applied.  None omits the flag entirely and uses
				the CLI's configured default from ~/.codex/config.toml.
			binary: Path or name of the codex executable.
			timeout: Seconds before the subprocess is killed.
		"""
		self.model = model
		self.binary = binary
		self.timeout = int(timeout)

	#============================================
	def _build_argv(self, output_path: str) -> list[str]:
		"""
		Construct the subprocess argument list for the codex CLI.

		The prompt is NOT included here; it is passed via stdin using "-".
		`codex exec` is non-interactive by design; the safety boundary is the
		read-only sandbox (--sandbox read-only).

		Args:
			output_path: Path where the CLI will write the final message via
				--output-last-message.

		Returns:
			A list of strings ready for subprocess.run(argv, ...).
		"""
		# hardcoded safety posture: read-only sandbox (codex exec is non-interactive by default)
		argv = [
			self.binary,
			"exec",
			"--sandbox", "read-only",
			"--output-last-message", output_path,
		]
		# omit -m entirely when model is None to use the CLI's configured default
		if self.model is not None:
			argv.extend(["-m", self.model])
		# trailing "-" tells codex exec to read the prompt from stdin
		argv.append("-")
		return argv

	#============================================
	def generate(self, prompt: str, *, purpose: str, max_tokens: int) -> str:
		"""
		Run the Codex CLI with the given prompt and return the final message.

		The prompt is delivered via stdin; the reply is read from the temp file
		written by --output-last-message (stdout is noisy and not parsed).
		max_tokens and purpose are accepted to satisfy the LLMTransport Protocol
		but are not forwarded to the CLI.

		Raises:
			TransportUnavailableError: On any failure including missing binary,
				timeout, non-zero exit code, or empty/missing output file.
		"""
		# create a temp file for the final message; close fd immediately so codex can write it
		fd, output_path = tempfile.mkstemp(suffix=".txt", prefix="codex_out_")
		os.close(fd)
		try:
			argv = self._build_argv(output_path)
			try:
				# pass prompt through stdin; capture stdout/stderr separately
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
				raise TransportUnavailableError(
					f"Codex CLI could not be started: {exc}"
				) from exc
			except subprocess.TimeoutExpired as exc:
				raise TransportUnavailableError(
					f"Codex CLI timed out after {self.timeout}s."
				) from exc
			# non-zero return code means the CLI reported an error
			if result.returncode != 0:
				stderr_text = result.stderr.strip()
				if stderr_text:
					# include at most ~1000 chars of stderr; never stdout (may echo logs/prompt)
					truncated = stderr_text[:1000]
					raise TransportUnavailableError(
						f"Codex CLI exited with code {result.returncode}: {truncated}"
					)
				raise TransportUnavailableError(
					f"Codex CLI exited with code {result.returncode} (no stderr)."
				)
			# read the final message from the output file (outside the launch try/except)
			try:
				with open(output_path, "r", encoding="utf-8", errors="replace") as fh:
					output = fh.read().strip()
			except FileNotFoundError:
				raise TransportUnavailableError("Codex CLI returned empty output.")
			except OSError as exc:
				raise TransportUnavailableError("Could not read Codex CLI output.") from exc
			# an empty output file means codex produced no usable final message
			if not output:
				raise TransportUnavailableError("Codex CLI returned empty output.")
			result_text = output
			return result_text
		finally:
			# best-effort cleanup; ignore missing-file error (already cleaned or never created)
			try:
				os.unlink(output_path)
			except OSError:
				pass
