# Usage

## Library quick start

Install the package and import via the `llm` facade module.

```python
import local_llm_wrapper.llm as llm

client = llm.LLMClient(
	transports=[
		llm.AppleTransport(),
		llm.OllamaTransport(model=llm.choose_model(None)),
	],
	quiet=True,
)

response = client.generate("Say hello in one sentence.", max_tokens=120)
print(response)
```

## Import patterns

### Facade import (recommended)

Most callers need `LLMClient`, one or two transports, `choose_model`, and possibly
error types. The facade gives all of those from a single import line, which keeps
caller scripts clean.

```python
import local_llm_wrapper.llm as llm
```

See [docs/LLM_FACADE.md](LLM_FACADE.md) for the full list of exported names.

### Direct submodule imports

Use direct imports only when you need a single name and want to document exactly
where it lives. For most callers this adds unnecessary verbosity.

```python
from local_llm_wrapper.llm_client import LLMClient
from local_llm_wrapper.transports.ollama import OllamaTransport
```

## CLI tools

All CLI tools live at the repo root and use the Ollama transport.

### llm_generate.py

Quick single-prompt test.

```bash
source source_me.sh && python3 llm_generate.py -p "Say hello." -t 80
```

Flags: `-p/--prompt`, `-m/--model`, `-t/--max-tokens`, `-q/--quiet`, `-v/--verbose`.

### llm_chat.py

Interactive multi-turn chat loop.

```bash
source source_me.sh && python3 llm_chat.py -s "Answer briefly."
```

Flags: `-m/--model`, `-s/--system`, `-t/--max-tokens`, `-q/--quiet`, `-v/--verbose`.
Type `exit`, `quit`, or `q` to end the session.

### llm_xml_demo.py

Request a tagged response and extract `<answer>` from model output.

```bash
source source_me.sh && python3 llm_xml_demo.py -p "What is a mutex?"
```

Flags: `-p/--prompt`, `-m/--model`, `-t/--max-tokens`, `-q/--quiet`, `-v/--verbose`.

## Structured helpers

### Rename

Generate a descriptive filename from metadata.

```python
result = client.rename("IMG_1234.jpg", {"title": "Sunset at beach", "extension": "jpg"})
print(result.new_name)
print(result.reason)
```

### Sort

Assign a category to a file based on its description.

```python
result = client.sort([{
	"path": "notes.txt", "name": "notes", "ext": "txt",
	"description": "meeting notes from standup",
}])
print(result.assignments)
```

## Inputs and outputs

- **Input:** plain text prompts or chat-style message lists (`list[dict]` with `role` and `content`).
- **Output:** raw text from `generate()`, or typed dataclass results from `rename()` and `sort()`.
- Structured helpers return `RenameResult`, `KeepResult`, or `SortResult` with parsed fields.

## Related docs

- [docs/LLM_FACADE.md](LLM_FACADE.md): Full reference for the facade module's exported names.
- [docs/API_IMPLEMENTATION_GUIDE.md](API_IMPLEMENTATION_GUIDE.md): Migration guide for sibling repos integrating with this package.
- [docs/CODE_ARCHITECTURE.md](CODE_ARCHITECTURE.md): High-level system design and data flow.

## ClaudeCodeTransport (opt-in cloud)

`ClaudeCodeTransport` delegates to the `claude` CLI binary, which routes prompts to the
Anthropic cloud. It is opt-in and never included in any default transport chain.

```python
import local_llm_wrapper.llm as llm

client = llm.LLMClient(
	transports=[llm.ClaudeCodeTransport(model="sonnet")],
	quiet=True,
)
response = client.generate("What is 2+2?", max_tokens=120)
print(response)
```

Default flags used internally:
`--print --input-format text --output-format text --model sonnet
--permission-mode default --tools "" --no-session-persistence`

Key notes:
- `max_tokens` is accepted by the transport to satisfy the `LLMTransport` protocol but is
  not forwarded to the CLI. `max_tokens` is an API-account concept; the account/OAuth
  Claude Code CLI path handles context limits internally.
- Default `tools=""` disables Claude Code tools and does not intentionally grant workspace
  read/write/exec capability. Use `tools="default"` to restore full tool access.
- `bare=True` forces `ANTHROPIC_API_KEY` / `apiKeyHelper` authentication and never reads
  OAuth or keychain credentials. Set `bare=True` only for API-key setups; account/OAuth
  setups will break.
- Prompts are sent to the Anthropic cloud, not processed locally.

## Known gaps

- No configuration file support; all settings are passed as arguments.
- Additional backends require implementing the `LLMTransport` protocol in
  `local_llm_wrapper/transports/`.
