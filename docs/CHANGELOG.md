# Changelog

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
- Add [docs/USAGE.md](USAGE.md) with library quick start, CLI tool reference, structured helper examples, and both direct and facade import patterns.
- Add [docs/LLM_FACADE.md](LLM_FACADE.md) documenting the `llm.py` convenience facade: exported names, source modules, and usage guidance.
- Bump version to 26.04 (CalVer).
- `devel/submit_to_pypi.py`: replace `--repo testpypi|pypi` with `--test` (default) and `--main` flags. `--repo` kept as escape hatch for specific `.pypirc` section names. When the target section is missing, auto-selects if one prefix match exists or prompts user to choose from multiple matches (e.g., `testpypi-llm`, `testpypi-qti`).
- `devel/submit_to_pypi.py`: add `require_pypirc_token()` pre-check that validates `~/.pypirc` exists, has the target section, uses token auth, and heuristically detects project-scoped tokens that don't match the current package.
- `devel/submit_to_pypi.py`: script now parses `~/.pypirc` credentials directly and injects them to twine via `TWINE_USERNAME`/`TWINE_PASSWORD` env vars and `--repository-url`. Eliminates dependency on `[distutils] index-servers` in `.pypirc`.

### Removals and Deprecations
- Archive planning docs to `docs/archive/`: `PUBLIC_API_PLAN.md`, `LLM_WRAPPER_IDEAS.md`, `OPENAI_WRAPPER_NOTES.md`.
- Trim `API_IMPLEMENTATION_GUIDE.md` to remove duplicate quick-start content; link to [docs/USAGE.md](USAGE.md) instead.

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
