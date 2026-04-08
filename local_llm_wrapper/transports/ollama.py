"""
Ollama chat transport.
"""

from __future__ import annotations

# Standard Library
import datetime
import json
import random
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

# local repo modules
from local_llm_wrapper.errors import TransportUnavailableError


class OllamaTransport:
	name = "Ollama"

	def __init__(
		self,
		model: str,
		base_url: str = "http://localhost:11434",
		system_message: str = "",
		use_history: bool = False,
		max_turns: int = 6,
		timeout: int = 120,
	) -> None:
		self.model = model
		self.base_url = base_url.rstrip("/")
		self.system_message = system_message
		self.use_history = bool(use_history)
		self.max_turns = int(max_turns)
		self.timeout = int(timeout)
		self.messages: list[dict[str, str]] = []
		self._model_ready = False

	def _build_messages(self, prompt: str) -> list[dict[str, str]]:
		messages: list[dict[str, str]] = []
		if self.system_message:
			messages.append({"role": "system", "content": self.system_message})
		if self.use_history and self.messages:
			messages.extend(self.messages)
		messages.append({"role": "user", "content": prompt})
		return messages

	def _build_messages_from_chat(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
		combined: list[dict[str, str]] = []
		if self.system_message:
			combined.append({"role": "system", "content": self.system_message})
		if self.use_history and self.messages:
			combined.extend(self.messages)
		combined.extend(messages)
		return combined

	def _last_user_message(self, messages: list[dict[str, str]]) -> str | None:
		for msg in reversed(messages):
			if msg.get("role") == "user":
				content = msg.get("content", "")
				return content if isinstance(content, str) and content else None
		return None

	def _trim_history(self) -> None:
		if not self.use_history:
			return
		if self.max_turns < 1:
			self.messages = []
			return
		max_messages = self.max_turns * 2
		while len(self.messages) > max_messages:
			if len(self.messages) >= 2:
				self.messages = self.messages[2:]
			else:
				self.messages = []
				return

	def _record_history(self, prompt: str, assistant_message: str) -> None:
		if not self.use_history:
			return
		self.messages.append({"role": "user", "content": prompt})
		self.messages.append({"role": "assistant", "content": assistant_message})
		self._trim_history()

	def _validated_chat_endpoint(self) -> str:
		"""
		Build and validate the Ollama chat endpoint URL.
		"""
		parsed = urllib.parse.urlparse(self.base_url)
		if parsed.scheme not in {"http", "https"}:
			raise TransportUnavailableError("Ollama base_url must use http or https.")
		if not parsed.netloc:
			raise TransportUnavailableError("Ollama base_url must include a host.")
		return urllib.parse.urljoin(self.base_url + "/", "api/chat")

	#============================================
	def _is_model_loaded(self) -> bool:
		"""Check via /api/ps whether self.model is already in memory."""
		url = urllib.parse.urljoin(self.base_url + "/", "api/ps")
		request = urllib.request.Request(url, method="GET")
		try:
			with urllib.request.urlopen(request, timeout=5) as response:  # nosec B310
				data = json.loads(response.read().decode("utf-8"))
		except (urllib.error.URLError, OSError, json.JSONDecodeError):
			return False
		for model_info in data.get("models", []):
			# match model name with or without tag suffix
			name = model_info.get("name", "")
			if name == self.model or name.startswith(self.model + ":"):
				return True
		return False

	#============================================
	def _pull_if_stale(self, max_age_days: int = 14) -> None:
		"""Pull the latest model version if the local copy is older than max_age_days.

		Uses GET /api/tags to check the modified_at timestamp. If the model
		is stale, runs 'ollama pull' to fetch the latest version.
		"""
		url = urllib.parse.urljoin(self.base_url + "/", "api/tags")
		request = urllib.request.Request(url, method="GET")
		try:
			with urllib.request.urlopen(request, timeout=5) as response:  # nosec B310
				data = json.loads(response.read().decode("utf-8"))
		except (urllib.error.URLError, OSError, json.JSONDecodeError):
			return
		# find the matching model entry
		modified_at = None
		for model_info in data.get("models", []):
			name = model_info.get("name", "")
			if name == self.model or name.startswith(self.model + ":"):
				modified_at = model_info.get("modified_at", "")
				break
		if not modified_at:
			return
		# parse the ISO 8601 timestamp (strip sub-second timezone colon for compatibility)
		# example: "2026-04-08T09:31:06.979197805-05:00"
		try:
			# truncate nanoseconds to microseconds and normalize timezone
			ts = modified_at
			if "." in ts:
				# split at dot, keep up to 6 fractional digits
				before_dot, rest = ts.split(".", 1)
				# separate fractional seconds from timezone offset
				frac = ""
				tz_part = ""
				for i, ch in enumerate(rest):
					if ch in ("+", "-", "Z"):
						frac = rest[:i]
						tz_part = rest[i:]
						break
				else:
					frac = rest
				frac = frac[:6].ljust(6, "0")
				ts = f"{before_dot}.{frac}{tz_part}"
			model_time = datetime.datetime.fromisoformat(ts)
		except (ValueError, IndexError):
			return
		now = datetime.datetime.now(datetime.timezone.utc)
		age = now - model_time
		if age.days < max_age_days:
			return
		# model is stale, pull the latest version
		print(f"[LLM] model {self.model} is {age.days} days old, pulling latest version...")
		try:
			subprocess.run(
				["ollama", "pull", self.model],
				timeout=600,
				check=False,
			)
			print(f"[LLM] model {self.model} updated")
		except (OSError, subprocess.TimeoutExpired):
			print(f"[LLM] failed to pull {self.model}, continuing with existing version")

	#============================================
	def _wait_for_model(self) -> None:
		"""Ensure the model is loaded before sending the real request.

		If the model is not already in memory, trigger loading with a
		minimal one-token chat request, then poll /api/ps until the model
		appears (up to 600 seconds).
		"""
		if self._model_ready:
			return
		self._pull_if_stale()
		if self._is_model_loaded():
			self._model_ready = True
			return
		# trigger model loading with a tiny request (fire and forget via short timeout)
		print(f"[LLM] model {self.model} is not loaded, triggering load...")
		trigger_payload: dict[str, object] = {
			"model": self.model,
			"messages": [{"role": "user", "content": "hi"}],
			"stream": False,
			"options": {"num_predict": 1},
		}
		trigger_request = urllib.request.Request(
			self._validated_chat_endpoint(),
			data=json.dumps(trigger_payload).encode("utf-8"),
			headers={"Content-Type": "application/json"},
			method="POST",
		)
		# send the trigger request with a long timeout since loading happens inline
		try:
			with urllib.request.urlopen(trigger_request, timeout=600) as response:  # nosec B310
				response.read()
		except (urllib.error.URLError, OSError):
			pass
		# poll /api/ps to confirm model is loaded
		max_wait = 600
		poll_interval = 5
		waited = 0
		while waited < max_wait:
			if self._is_model_loaded():
				print(f"[LLM] model {self.model} is loaded and ready")
				self._model_ready = True
				return
			time.sleep(poll_interval)
			waited += poll_interval
			if waited % 30 == 0:
				print(f"[LLM] still waiting for {self.model} to load ({waited}s)...")
		raise TransportUnavailableError(
			f"Ollama model {self.model} did not load within {max_wait}s."
		)

	#============================================
	def _call_api(self, messages: list[dict[str, str]], max_tokens: int) -> str:
		"""
		Send messages to the Ollama chat endpoint and return the assistant reply.

		Uses streaming mode so each token resets the socket timeout. The
		connection only times out if no token arrives within self.timeout
		seconds, which means the model has genuinely stalled.
		"""
		self._wait_for_model()
		# use a large num_predict so thinking models have room for both
		# reasoning tokens and actual content (num_predict does not affect VRAM)
		effective_tokens = max(max_tokens, 16384)
		payload: dict[str, object] = {
			"model": self.model,
			"messages": messages,
			"stream": True,
			"options": {"num_predict": effective_tokens},
		}
		time.sleep(random.random())
		request = urllib.request.Request(
			self._validated_chat_endpoint(),
			data=json.dumps(payload).encode("utf-8"),
			headers={"Content-Type": "application/json"},
			method="POST",
		)
		try:
			response = urllib.request.urlopen(request, timeout=self.timeout)  # nosec B310
		except urllib.error.URLError as exc:
			raise TransportUnavailableError("Ollama is unreachable.") from exc
		# read streaming chunks, accumulating content and thinking text
		content_parts: list[str] = []
		thinking_parts: list[str] = []
		try:
			for raw_line in response:
				line = raw_line.decode("utf-8").strip()
				if not line:
					continue
				chunk = json.loads(line)
				msg = chunk.get("message", {})
				content_parts.append(msg.get("content", ""))
				thinking_parts.append(msg.get("thinking", ""))
				if chunk.get("done", False):
					break
		except (urllib.error.URLError, OSError) as exc:
			raise TransportUnavailableError("Ollama connection lost during streaming.") from exc
		finally:
			response.close()
		assistant_message = "".join(content_parts)
		thinking_text = "".join(thinking_parts)
		# last resort: extract from thinking field
		if not assistant_message and thinking_text:
			assistant_message = thinking_text
		if not assistant_message:
			raise RuntimeError("Ollama chat returned empty content")
		return assistant_message

	#============================================
	def generate(self, prompt: str, *, purpose: str, max_tokens: int) -> str:
		messages = self._build_messages(prompt)
		assistant_message = self._call_api(messages, max_tokens)
		self._record_history(prompt, assistant_message)
		return assistant_message

	#============================================
	def generate_chat(
		self,
		messages: list[dict[str, str]],
		*,
		purpose: str,
		max_tokens: int,
	) -> str:
		combined = self._build_messages_from_chat(messages)
		assistant_message = self._call_api(combined, max_tokens)
		# Record only the last user message for history
		last_user = self._last_user_message(messages)
		if last_user:
			self._record_history(last_user, assistant_message)
		return assistant_message
