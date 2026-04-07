# LLM facade module

## Purpose

`local_llm_wrapper/llm.py` is a convenience facade that re-exports the most common
names from across the package. External callers can access the full public surface
from a single import instead of importing from multiple submodules.

```python
import local_llm_wrapper.llm as llm
```

## When to use the facade (recommended)

Use the facade when a script needs several names from the package. Most callers
need `LLMClient`, one or two transports, `choose_model`, and possibly error types
or `extract_xml_tag_content`. The facade gives all of those from a single import
line, which keeps caller scripts clean. This is the recommended import pattern.

```python
import local_llm_wrapper.llm as llm

client = llm.LLMClient(
	transports=[
		llm.AppleTransport(),
		llm.OllamaTransport(model=llm.choose_model(None)),
	],
	quiet=True,
)
response = client.generate("Summarize this text.", max_tokens=200)
```

## When to use direct imports

Use direct submodule imports only when you need a single name and the extra
explicitness is worth the verbosity. For most callers this is unnecessary --
4-5 `from` lines per file adds clutter with no practical gain.

```python
from local_llm_wrapper.llm_client import LLMClient
from local_llm_wrapper.transports.ollama import OllamaTransport
```

See [docs/USAGE.md](USAGE.md) for the full quick-start guide.

## Exported names

### Classes

| Name | Source module | Description |
| --- | --- | --- |
| `LLMClient` | `llm_client` | Public entry point for all LLM operations |
| `OllamaTransport` | `transports.ollama` | Ollama HTTP chat transport |
| `AppleTransport` | `transports.apple` | Apple Foundation Models transport |
| `RenameResult` | `llm_parsers` | Parsed rename response dataclass |
| `SortResult` | `llm_parsers` | Parsed sort response dataclass |

### Functions

| Name | Source module | Description |
| --- | --- | --- |
| `choose_model` | `llm_utils` | Pick an Ollama model based on available RAM |
| `extract_xml_tag_content` | `llm_utils` | Extract the last occurrence of an XML-like tag |
| `sanitize_filename` | `llm_utils` | Clean a filename to ASCII-safe characters |
| `apple_models_available` | `llm_utils` | Check if Apple Intelligence is usable |
| `get_vram_size_in_gb` | `llm_utils` | Detect VRAM or unified memory size |
| `total_ram_bytes` | `llm_utils` | Estimate total system memory |

### Errors

| Name | Source module | Description |
| --- | --- | --- |
| `LLMError` | `errors` | Base class for all wrapper errors |
| `TransportUnavailableError` | `errors` | Transport cannot be used on this machine |
| `ContextWindowError` | `errors` | Prompt exceeds model context window |
| `GuardrailRefusalError` | `errors` | Model refused prompt due to safety guardrails |

## Design notes

- The facade contains no logic. Every name is a plain re-export.
- `__all__` is present to suppress pyflakes unused-import warnings on the re-exports.
- The facade surface is intentionally stable. Adding names is safe; removing names
  requires checking downstream callers (currently `vosslab-podcast`).
- For the full API contract and error handling patterns, see
  [docs/API_IMPLEMENTATION_GUIDE.md](API_IMPLEMENTATION_GUIDE.md).
