# Changelog

## 2026-08-27

### Fixes and Maintenance

- Synchronized shared style guides, tests, and repository support files from the starter template.

## 2026-05-31

### Additions and New Features
- Add `local_llm_wrapper/transports/codex_cli.py`: new `CodexTransport` class that
  delegates to the `codex exec` CLI (verified CLI version: codex-cli 0.135.0).
  Constructor: `CodexTransport(model=None, *, binary="codex", timeout=300)`.
  Hardcoded safety flags: `--sandbox read-only`; output captured via
  `--output-last-message`. `codex exec` is non-interactive by default so
  `--ask-for-approval` is not passed (it is a top-level/TUI-only flag).
  `--skip-git-repo-check` is intentionally NOT emitted, so `codex exec` may refuse
  outside a git repo (surfaces as `TransportUnavailableError`). Advanced behavior via
  `~/.codex/config.toml`, not wrapper args. Opt-in only; never in any default chain.
- Re-export `CodexTransport` from `local_llm_wrapper/llm.py` facade: add
  `from local_llm_wrapper.transports.codex_cli import CodexTransport` (alphabetical between
  `claude_code` and `ollama` in the import block) and add `"CodexTransport"` to `__all__`
  (alphabetical between `"ClaudeCodeTransport"` and `"ContextWindowError"`).
- Add `local_llm_wrapper/transports/claude_code.py`: new `ClaudeCodeTransport` class that
  delegates to the `claude` CLI via `subprocess` with the verified default flag set:
  `--print --input-format text --output-format text
  --permission-mode default --tools "" --no-session-persistence`.
  All failure paths (missing binary, timeout, non-zero exit, empty output) raise
  `TransportUnavailableError` so the engine fallback chain skips the transport cleanly.
  The transport is opt-in and never included in any default chain.
- Add `tests/test_claude_code_transport.py`: deterministic pytest coverage for
  `ClaudeCodeTransport` using monkeypatched `subprocess.run`; covers default argv flags,
  stdin delivery, passthrough args, opt-in flags (`bare`, `session_persistence`),
  special-char round-trips, missing-binary error, timeout error, nonzero-exit error with
  stderr cap, empty-output error, and success path.
- Re-export `ClaudeCodeTransport` from the `local_llm_wrapper/llm.py` facade: add the
  import and add `"ClaudeCodeTransport"` to `__all__` in alphabetical order.
- Update `README.md` to reflect local-first, pluggable-transport framing: intro and Overview no
  longer claim "local only"; add `ClaudeCodeTransport` quick-start snippet and cloud-use caveats
  (cloud routing, trust-dialog skip, tools disabled by default); add transport to Transports list.

### Behavior or Interface Changes
- `ClaudeCodeTransport` model default changed from `"sonnet"` to `None`: passing `model=None`
  now omits `--model` entirely so the CLI uses its own configured default. Callers that want
  a specific model must pass it explicitly (e.g. `ClaudeCodeTransport(model="sonnet")`).
- Reframe package from "local only" to "local-first with pluggable transports including optional
  cloud (Claude Code CLI, Codex CLI)": update `pyproject.toml` description,
  `docs/CODE_ARCHITECTURE.md` overview and transport list, and `docs/USAGE.md` (add
  `ClaudeCodeTransport` section documenting default flags, `max_tokens`-not-forwarded note,
  and `bare=True` auth caveat; add new `CodexTransport` section).
- Verified `claude` CLI flag set used by `ClaudeCodeTransport` default invocation (with an
  explicit model): `--print --input-format text --output-format text --model <model>
  --permission-mode default --tools "" --no-session-persistence`.
  `--tools ""` disables Claude Code tools; the transport does not intentionally grant
  workspace read/write/exec capability in its default configuration.

### Fixes and Maintenance
- Audit follow-up (audit-code-reviewer): (a) remove fragile conditional `if` guard around the
  error-path assert in `test_temp_file_cleaned_up_on_success_and_error` so the cleanup check
  cannot silently skip; (b) fix stale "use a list" comment (state is a dict) in
  `tests/test_codex_transport.py`; (c) correct `docs/USAGE.md` Claude default-flag block to
  show `--model` as conditional on a non-None model (default `model=None` omits it); (d) name
  Codex CLI alongside Claude Code CLI as an opt-in cloud transport in
  `docs/API_IMPLEMENTATION_GUIDE.md`.
- Remove `--ask-for-approval never` from `CodexTransport`: `codex exec` is non-interactive
  by default and rejects this flag with exit code 2 (it is a top-level/TUI-only flag).
  Remaining hardcoded safety flag: `--sandbox read-only`.
- Fix two quality issues in `tests/test_claude_code_transport.py` (M2/WS3): (a) replace literal
  non-ASCII char `e` with accent in the special-chars test string with a Python unicode escape
  `\xe9` so the source file is pure ASCII (repo rule); (b) replace hardcoded `len(msg) <= 1100`
  tunable-constant assertion in the long-stderr truncation test with a stability-preserving check
  (`len(msg) < len(long_stderr)`) that verifies truncation occurred without asserting a magic
  constant.
- Harden `ClaudeCodeTransport.generate` exception paths: broaden `except FileNotFoundError`
  to `except OSError as exc` so `PermissionError` and other launch-time OS errors also map to
  `TransportUnavailableError` instead of escaping the fallback chain. Add `from exc` chain to
  the `TimeoutExpired` re-raise (matching `ollama.py` convention). Add `errors="replace"` to
  the `subprocess.run` call so malformed CLI bytes under a degraded locale cannot raise
  `UnicodeDecodeError`.

### Removals and Deprecations
- Remove 11 fragile argv flag-membership tests from `tests/test_claude_code_transport.py`
  (audit-code-reviewer Test auditor): per `docs/PYTEST_STYLE.md`, per-flag membership and
  hardcoded-default assertions break on harmless flag reordering and test no logic. Behavioral
  tests (generate round-trip, stdin delivery, error/timeout paths, model-None omission) are
  retained.

## 2026-04-08

### Additions and New Features
- Dual Apple backend support: `AppleTransport` now prefers `apple-fm-sdk` (Apple's official SDK) when importable, runtime-available, and no active event loop. Falls back to `apple-foundation-models` (community fork with prebuilt wheels) otherwise. Public API is unchanged; backend selection is fully internal.
- Add `_generate_via_fm_sdk()` adapter that wraps the async `apple-fm-sdk` API with `asyncio.run()`, including event loop safety check via `_can_use_asyncio_run()`.
- Add `_generate_via_afm()` adapter that preserves the existing `apple-foundation-models` behavior.
- Add `_select_apple_backend()` preference hint and `_AppleBackend` enum for clean backend dispatch.
- Add optional extras in `pyproject.toml`: `[apple]` (prebuilt wheels), `[apple-official]` (requires Xcode 26+), `[apple-all]` (both).
- Add unit tests for all backend fallback paths: fm-sdk-only, afm-only, both-missing, event-loop fallback, guardrail passthrough, context-window fallback, and dual context-window error precedence.
- Add `apple-foundation-models` to `pip_requirements.txt`; was imported but undeclared.

### Behavior or Interface Changes
- `apple_models_available()` now checks both `apple-fm-sdk` and `apple-foundation-models` for runtime availability. Does not check event loop state (that is a call-site concern).
- `_GUARDRAIL_ERRORS` tuple now collects guardrail exception types from both Apple SDKs.
- `ContextWindowError` from one Apple backend now triggers fallback to the other backend. `GuardrailRefusalError` does not trigger fallback (safety refusal is semantic).
- When both Apple backends fail, the final exception uses semantic precedence: `ContextWindowError` if either backend raised it, otherwise `TransportUnavailableError` with per-backend failure reasons.
- Add smart model-loading detection to `OllamaTransport`: before each API call, check `/api/ps` to see if the model is already loaded. If not, trigger loading with a minimal request and poll `/api/ps` until the model is ready (up to 600s), with periodic status messages. Replaces the old behavior of failing with a confusing "Ollama is unreachable" error after 120s when a large model was still loading.

### Fixes and Maintenance
- Normalize bare Ollama model names: if the model name has no `:` tag (e.g., `gemma4`), automatically append `:latest` to match Ollama's own resolution behavior.
- Fix Ollama model-loaded check failing for tag aliases: `_is_model_loaded()` compared model names exactly, but Ollama resolves aliases internally (e.g., `gemma4:e4b` becomes `gemma4:latest` in `/api/ps`). Add digest-based fallback via `/api/tags` so aliased models are recognized as already loaded.
- Auto-update stale Ollama models: before each session, check `/api/tags` for the model's `modified_at` timestamp. If older than 14 days, run `ollama pull` to fetch the latest version. Only updates already-installed models; does not download new ones.
- Switch Ollama transport to streaming mode: tokens arrive incrementally, so the timeout only applies between tokens (not total generation time). Large models no longer time out during long generations.
- Cache model readiness check so `_pull_if_stale()` and `_is_model_loaded()` only run once per transport session, not on every API call.
- Fix empty content from thinking models (e.g., Qwen3.5): set `num_predict` floor to 16384 so thinking tokens never starve the actual content. Falls back to `thinking` text as last resort if content is still empty. Extract `_send_request()` helper to avoid duplicating HTTP logic.

### Behavior or Interface Changes
- Rename `total_ram_bytes()` to `total_ram_bytes_in_gb()` for symmetry with `get_vram_size_in_gb()`. Function now returns whole gigabytes instead of raw bytes.
- Fix `choose_model()` RAM fallback: was multiplying bytes instead of dividing, referenced undefined variable `ram`, and had a missing colon on a conditional.
- Switch model ladder in `choose_model()` from mixed gpt-oss/phi4/llama3.2 to Qwen3.5 q4_K_M across all tiers. New thresholds: >= 33 GB gets 27b, >= 12 GB gets 9b, >= 8 GB gets 4b, below gets 2b. Design policy: pick the largest model that is plausibly stable, not the smallest that fits.
- Update `README.md` examples to use `qwen3.5:9b-q4_K_M` instead of `llama3.2:3b-instruct-q5_K_M`.

## 2026-04-07

### Fixes and Maintenance
- Simplify `local_llm_wrapper/llm.py` facade: remove `choose_model()` monkey-patching and `__globals__` mutation; replace with plain re-exports from submodules. Facade surface unchanged for external callers.
- Extract shared Ollama HTTP logic into `OllamaTransport._call_api()` to deduplicate `generate()` and `generate_chat()`.
- Remove unused `original_prompt` parameter from `build_format_fix_prompt()`.
- Remove unreachable `return 0, 0, 0` in `_parse_macos_version()`.
- Switch regex patterns in `get_vram_size_in_gb()` from double-backslash strings to raw strings for clarity.
- Remove redundant `_ensure_chat_messages()` call in `format_chat_prompt()`; callers validate upstream.
- Remove dead `upgrade_build_tools()` function from `devel/submit_to_pypi.py`.
- Fix next-step message in PyPI script to reference the script's own `--repo pypi` flag.
- Fix broken imports in `README.md`: `from local_llm_wrapper.transports import ...` fails because `__init__.py` is empty; corrected to import from submodules directly.

### Additions and New Features
- Add [USAGE.md](USAGE.md) with library quick start, CLI tool reference, structured helper examples, and both direct and facade import patterns.
- Add [LLM_FACADE.md](LLM_FACADE.md) documenting the `llm.py` convenience facade: exported names, source modules, and usage guidance.
- Bump version to 26.04 (CalVer).
- `devel/submit_to_pypi.py`: replace `--repo testpypi|pypi` with `--test` (default) and `--main` flags. `--repo` kept as escape hatch for specific `.pypirc` section names. When the target section is missing, auto-selects if one prefix match exists or prompts user to choose from multiple matches (e.g., `testpypi-llm`, `testpypi-qti`).
- `devel/submit_to_pypi.py`: add `require_pypirc_token()` pre-check that validates `~/.pypirc` exists, has the target section, uses token auth, and heuristically detects project-scoped tokens that don't match the current package.
- `devel/submit_to_pypi.py`: script now parses `~/.pypirc` credentials directly and injects them to twine via `TWINE_USERNAME`/`TWINE_PASSWORD` env vars and `--repository-url`. Eliminates dependency on `[distutils] index-servers` in `.pypirc`.
- `devel/submit_to_pypi.py`: require explicit "yes" confirmation before production PyPI uploads.
- `devel/submit_to_pypi.py`: print resolved upload target (section, URL, package, version) before uploading.
- `devel/submit_to_pypi.py`: token scope mismatch is now a hard fail instead of a warning - prevents wasting time building when the token targets the wrong project.
- `devel/submit_to_pypi.py`: read `repository` URL from `.pypirc` sections when present, falling back to defaults based on section name prefix.

### Removals and Deprecations
- Archive planning docs to `docs/archive/`: `PUBLIC_API_PLAN.md`, `LLM_WRAPPER_IDEAS.md`, `OPENAI_WRAPPER_NOTES.md`.
- Trim `API_IMPLEMENTATION_GUIDE.md` to remove duplicate quick-start content; link to [USAGE.md](USAGE.md) instead.

### Decisions and Failures
- `pick_category()` in `llm_utils.py` kept as compatibility utility despite no known internal callers; safer than deleting with limited downstream visibility.
- `llm.py` facade kept as a convenience module; external callers (vosslab-podcast) depend on it.

## 2026-02-22
- Fix `pytest tests/` collection imports by adding repo-root `sys.path` injection in `tests/conftest.py` so `local_llm_wrapper` resolves when running the `pytest` entrypoint.
- Remove shebang lines from pytest modules so shebang/executable alignment checks pass for test files.
- Treat Apple Foundation Models imports as optional-import guards in runtime helpers/transport checks to satisfy import-requirements lint behavior.
- Fix pyright protocol/return typing in transport and engine helpers and ignore missing third-party imports in `tests/pyrightconfig.json`.
- Raise default import-hygiene failure threshold to `high` so current repo policy gates only high-severity import violations unless overridden by env.

## 2026-01-15
- Add standardized LLM errors and transport-availability handling.
- Add quiet mode and a general text-only generate method.
- Add unified chat-or-prompt generation support with chat formatting helpers.
- Add Ollama chat-generation support for message lists.
- Add Apple transport instructions and retry support.
- Add Ollama transport history options with bounded turns and unreachable detection.
- Export the transport protocol alongside Apple and Ollama transports.
- Add pytest coverage for engine fallback and parse-retry behavior.
- Add architecture and file-structure documentation.
- Add a root-level `project.toml` with basic project metadata.
- Add notes summarizing the sibling OpenAI wrapper repo.
- Add a public API planning doc for cross-repo usage.
- Expand the public API plan with extended justifications and repo references.
- Update the public API plan with design decisions and stability rules.
- Implement the public API plan with a new LLMClient wrapper and docs updates.
- Add a pytest for the LLMClient wrapper.
- Update architecture docs to reflect the LLMClient public entry point.
- Update README examples to use LLMClient and dict-based sort inputs.
- Trim `local_llm_wrapper/llm.py` exports to the planned public surface.
- Set the project version to 0.1 in `pyproject.toml` and add a `VERSION` file.
- Add an API implementation guide for sibling repos.
- Document the `local-llm-wrapper` package name vs `local_llm_wrapper` import.
- Update packaging files to include `pyproject.toml`, `VERSION`, and an import hint.
- Expand README with usage examples, testing, and docs pointers.
- Add a README CLI example for quiet `generate`.
- Add a README chat example for unified message-based generation.
- Expand pytest coverage for rename and sort flows.
- Add packaging files for PyPI builds (pyproject.toml, MANIFEST.in).
- Add pytest coverage for parsers and utilities.
- Add pip_requirements.txt for core dev/test dependencies.
- Add pytest coverage for prompt builders and utility helpers.
- Add pytest conftest to ensure local imports resolve when running tests directly.
- Remove the redundant `project.toml` now that `pyproject.toml` is the source of truth.
- Add repo-root CLI demos (`llm_generate.py`, `llm_chat.py`, `llm_xml_demo.py`) with README and file-structure updates.
- Add a generic XML tag parser helper with coverage in parser tests.
