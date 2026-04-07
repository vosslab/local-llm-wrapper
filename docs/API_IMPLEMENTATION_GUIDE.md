# API implementation guide

## Overview

This guide shows how to integrate `local_llm_wrapper` into the five sibling repos.
For general usage, quick start, CLI tools, and import patterns see [docs/USAGE.md](USAGE.md).

## Error handling
- Catch typed errors from `local_llm_wrapper.errors`.
- Handle unavailable transports and guardrail refusals explicitly.

```python
from local_llm_wrapper.errors import GuardrailRefusalError, TransportUnavailableError

try:
	response = client.generate("Say hello.")
except GuardrailRefusalError:
	response = ""
except TransportUnavailableError as exc:
	raise RuntimeError("No local LLM available.") from exc
```

## Repo-specific guidance

### llm-file-rename-n-sort
- Keep using structured helpers, but switch to `LLMClient` instead of `LLMEngine`.
- Use `rename` and `sort` to preserve strict parsing and retries.

### automated_radio_disc_jockey
- Use `generate` with Apple-first fallback and optional instructions.
- Replace env var model selection with explicit `choose_model(None)` or override.

### biology-problems-website
- Use Ollama only, with `quiet=True`.
- Replace subprocess calls with `OllamaTransport` HTTP usage.

### screenshot-ai-renamer-macos
- Use Apple only, with short prompts and `quiet=True`.
- Keep output sanitization local to the project if needed.

### ai_image_caption
- Keep vision flow out of this wrapper.
- Use `generate` only for text-only post-processing if needed.

## Configuration rules
- Do not use custom environment variables for behavior.
- Pass explicit parameters into transports or `LLMClient`.
- Keep local-only behavior in this repo.

## Testing guidance
- Mock transports when unit testing to keep tests deterministic.
- Avoid real network or model calls inside tests.
