# Code architecture

## Overview
- This repo provides a local LLM wrapper library with a text-in, text-out API and pluggable transports.
- The primary workflow builds an `LLMClient` with transports, sends prompts, and parses structured results.

## Major components
- `local_llm_wrapper/llm_client.py`: Public client wrapper that delegates to `LLMEngine`.
- `local_llm_wrapper/llm_engine.py`: Core engine with fallback, parse-retry, and structured helpers.
- `local_llm_wrapper/transports/`: Backend implementations for Apple and Ollama plus the transport protocol.
- `local_llm_wrapper/llm_prompts.py`: Prompt builders and request dataclasses for structured tasks.
- `local_llm_wrapper/llm_parsers.py`: XML-like parsers and typed result objects.
- `local_llm_wrapper/llm_utils.py`: Prompt sanitizers, model selection, logging, and hardware checks.
- `local_llm_wrapper/errors.py`: Standardized exception taxonomy for callers and transports.
- `local_llm_wrapper/llm.py`: Convenience facade that re-exports common names for external callers.

## Data flow
- Caller constructs metadata or prompt text and instantiates `LLMClient`.
- `LLMClient` delegates to `LLMEngine` which builds prompts, selects transports, and requests generations.
- Transports return raw model text which is parsed into structured results.
- Parse failures trigger a format-fix prompt and retry before surfacing errors.

## Testing and verification
- Pytest tests live in `tests/` and run with `source source_me.sh && python3 -m pytest tests/`.
- Pyflakes lint: `source source_me.sh && python3 -m pytest tests/test_pyflakes_code_lint.py`.
- ASCII compliance: `source source_me.sh && python3 -m pytest tests/test_ascii_compliance.py`.

## Extension points
- Add new backends under `local_llm_wrapper/transports/` and implement the `LLMTransport` protocol.
- Add new structured tasks by pairing prompt builders in `local_llm_wrapper/llm_prompts.py` with parsers in `local_llm_wrapper/llm_parsers.py` and engine methods in `local_llm_wrapper/llm_engine.py`.
- Extend shared utilities in `local_llm_wrapper/llm_utils.py` for model selection or sanitization.
