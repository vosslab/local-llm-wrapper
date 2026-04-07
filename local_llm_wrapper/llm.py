"""
Convenience facade for local_llm_wrapper.

External callers can use `import local_llm_wrapper.llm as llm` to access
the most common names from a single import.
"""

from __future__ import annotations

from local_llm_wrapper.errors import (
	ContextWindowError,
	GuardrailRefusalError,
	LLMError,
	TransportUnavailableError,
)
from local_llm_wrapper.llm_client import LLMClient
from local_llm_wrapper.llm_parsers import RenameResult, SortResult
from local_llm_wrapper.llm_utils import (
	apple_models_available,
	choose_model,
	extract_xml_tag_content,
	get_vram_size_in_gb,
	sanitize_filename,
	total_ram_bytes,
)
from local_llm_wrapper.transports.apple import AppleTransport
from local_llm_wrapper.transports.ollama import OllamaTransport

# Re-exports are intentional; __all__ suppresses pyflakes unused-import warnings.
__all__ = [
	"AppleTransport",
	"ContextWindowError",
	"GuardrailRefusalError",
	"LLMClient",
	"LLMError",
	"OllamaTransport",
	"RenameResult",
	"SortResult",
	"TransportUnavailableError",
	"apple_models_available",
	"choose_model",
	"extract_xml_tag_content",
	"get_vram_size_in_gb",
	"sanitize_filename",
	"total_ram_bytes",
]
