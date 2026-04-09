"""
Apple Foundation Models transport.

Supports two backends:
- apple-fm-sdk (Apple's official SDK, async API, requires Xcode 26+)
- apple-foundation-models (community fork, sync API, prebuilt wheels)

Prefers apple-fm-sdk when importable, available, and no active event loop.
Falls back to apple-foundation-models otherwise.
"""

from __future__ import annotations

# Standard Library
import asyncio
import enum
import platform
import time

# local repo modules
from local_llm_wrapper.errors import ContextWindowError, GuardrailRefusalError, TransportUnavailableError
from local_llm_wrapper.llm_utils import MIN_MACOS_MAJOR, _parse_macos_version


#============================================
class _AppleBackend(enum.Enum):
	"""Internal enum for Apple backend selection."""
	FM_SDK = "apple-fm-sdk"
	AFM = "apple-foundation-models"


#============================================
def _can_use_asyncio_run() -> bool:
	"""Return True if asyncio.run() is safe to call (no running loop)."""
	try:
		asyncio.get_running_loop()
	except RuntimeError:
		# no running loop -- safe
		return True
	return False


#============================================
def _generate_via_fm_sdk(
	prompt: str,
	instructions: str,
	temperature: float,
	max_tokens: int,
	max_retries: int,
) -> str:
	"""Generate text using Apple's official apple-fm-sdk.

	Authoritative adapter: validates all preconditions (event loop, import,
	availability) before calling the SDK.

	Args:
		prompt: the text prompt to send
		instructions: system instructions for the session
		temperature: sampling temperature
		max_tokens: maximum response tokens
		max_retries: number of retry attempts on transient errors

	Returns:
		stripped model response text

	Raises:
		TransportUnavailableError: if fm-sdk cannot be used
		GuardrailRefusalError: if model refuses on safety grounds
		ContextWindowError: if prompt exceeds context window
	"""
	# check event loop safety before importing
	if not _can_use_asyncio_run():
		raise TransportUnavailableError(
			"apple-fm-sdk: cannot use asyncio.run() -- event loop already running."
		)
	# lazy import
	try:
		import apple_fm_sdk
	except (ImportError, ModuleNotFoundError) as exc:
		raise TransportUnavailableError(
			"apple-fm-sdk is not installed."
		) from exc
	# check model availability
	model = apple_fm_sdk.SystemLanguageModel()
	is_available, reason = model.is_available()
	if not is_available:
		reason_text = reason.name if reason else "unknown"
		raise TransportUnavailableError(
			f"apple-fm-sdk: model unavailable ({reason_text})."
		)
	# build generation options
	options = apple_fm_sdk.GenerationOptions(
		temperature=temperature,
		maximum_response_tokens=max_tokens,
	)
	# retry loop
	for attempt in range(1, max_retries + 1):
		try:
			session = apple_fm_sdk.LanguageModelSession(instructions=instructions)
			result = asyncio.run(session.respond(prompt, options=options))
			text = str(result).strip()
			return text
		except apple_fm_sdk.GuardrailViolationError as exc:
			raise GuardrailRefusalError(str(exc)) from exc
		except apple_fm_sdk.ExceededContextWindowSizeError as exc:
			raise ContextWindowError(str(exc)) from exc
		except Exception as exc:
			if attempt < max_retries:
				time.sleep(attempt)
				continue
			raise TransportUnavailableError(
				"apple-fm-sdk call failed after retries."
			) from exc
	raise TransportUnavailableError("apple-fm-sdk call failed.")


#============================================
def _generate_via_afm(
	prompt: str,
	instructions: str,
	temperature: float,
	max_tokens: int,
	max_retries: int,
) -> str:
	"""Generate text using the apple-foundation-models package.

	Authoritative adapter: validates all preconditions (import, platform,
	availability) before calling the SDK.

	Args:
		prompt: the text prompt to send
		instructions: system instructions for the session
		temperature: sampling temperature
		max_tokens: maximum response tokens
		max_retries: number of retry attempts on transient errors

	Returns:
		stripped model response text

	Raises:
		TransportUnavailableError: if AFM cannot be used
		GuardrailRefusalError: if model refuses on safety grounds
	"""
	# lazy import
	try:
		from applefoundationmodels import Session, apple_intelligence_available
		from applefoundationmodels.exceptions import GuardrailViolationError
	except (ImportError, ModuleNotFoundError) as exc:
		raise TransportUnavailableError(
			"apple-foundation-models is not installed."
		) from exc
	# platform checks
	arch = platform.machine().lower()
	if arch != "arm64":
		raise TransportUnavailableError(
			"Apple Intelligence requires Apple Silicon (arm64)."
		)
	major, minor, patch = _parse_macos_version()
	if major < MIN_MACOS_MAJOR:
		raise TransportUnavailableError(
			f"macOS {MIN_MACOS_MAJOR}.0+ is required (detected {major}.{minor}.{patch})."
		)
	if not apple_intelligence_available():
		try:
			reason = Session.get_availability_reason()
		except Exception:
			reason = "Apple Intelligence not available or not enabled."
		raise TransportUnavailableError(str(reason))
	# retry loop
	for attempt in range(1, max_retries + 1):
		try:
			with Session(instructions=instructions) as session:
				response = session.generate(
					prompt,
					max_tokens=max_tokens,
					temperature=temperature,
				)
			return response.text.strip()
		except GuardrailViolationError as exc:
			raise GuardrailRefusalError(str(exc)) from exc
		except Exception as exc:
			if attempt < max_retries:
				time.sleep(attempt)
				continue
			raise TransportUnavailableError(
				"apple-foundation-models call failed after retries."
			) from exc
	raise TransportUnavailableError("apple-foundation-models call failed.")


#============================================
def _select_apple_backend() -> _AppleBackend:
	"""Return the preferred Apple backend as a lightweight hint.

	Checks importability, availability, and event loop safety for fm-sdk.
	Adapters still validate their own preconditions independently.
	"""
	# prefer fm-sdk if conditions look good
	if not _can_use_asyncio_run():
		return _AppleBackend.AFM
	try:
		import apple_fm_sdk
		model = apple_fm_sdk.SystemLanguageModel()
		is_available, _reason = model.is_available()
		if is_available:
			return _AppleBackend.FM_SDK
	except Exception:
		pass
	return _AppleBackend.AFM


#============================================
class AppleTransport:
	name = "AppleLLM"

	def __init__(
		self,
		instructions: str | None = None,
		max_retries: int = 2,
		temperature: float = 0.2,
	) -> None:
		self.instructions = instructions
		self.max_retries = max(1, int(max_retries))
		self.temperature = float(temperature)

	#============================================
	def generate(self, prompt: str, *, purpose: str, max_tokens: int) -> str:
		"""Generate text using the best available Apple backend.

		Tries the preferred backend first, falls back on TransportUnavailableError
		or ContextWindowError. GuardrailRefusalError is never caught for fallback.
		"""
		default_instructions = (
			"Follow the prompt precisely. "
			"If the prompt requests XML tags, output only those tags and nothing else."
		)
		session_instructions = self.instructions or default_instructions

		# determine backend order
		preferred = _select_apple_backend()
		if preferred == _AppleBackend.FM_SDK:
			adapters = [
				(_AppleBackend.FM_SDK, _generate_via_fm_sdk),
				(_AppleBackend.AFM, _generate_via_afm),
			]
		else:
			adapters = [
				(_AppleBackend.AFM, _generate_via_afm),
				(_AppleBackend.FM_SDK, _generate_via_fm_sdk),
			]

		# track per-backend failure reasons
		failures: dict[str, str] = {}
		# track the most semantically meaningful error for final raise
		last_context_error: ContextWindowError | None = None

		for backend, adapter_fn in adapters:
			try:
				text = adapter_fn(
					prompt,
					session_instructions,
					self.temperature,
					max_tokens,
					self.max_retries,
				)
				return text
			except GuardrailRefusalError:
				# safety refusal -- never fall back
				raise
			except ContextWindowError as exc:
				# context overflow may differ between backends -- try fallback
				failures[backend.value] = f"context window exceeded: {exc}"
				last_context_error = exc
				continue
			except TransportUnavailableError as exc:
				failures[backend.value] = str(exc)
				continue

		# both backends failed -- raise most meaningful error
		# exception precedence: ContextWindowError > TransportUnavailableError
		combined = "; ".join(
			f"{name}: {reason}" for name, reason in failures.items()
		)
		if last_context_error is not None:
			raise ContextWindowError(
				f"Both Apple backends exceeded context window. {combined}"
			) from last_context_error
		raise TransportUnavailableError(
			f"No Apple backend available. {combined}"
		)
