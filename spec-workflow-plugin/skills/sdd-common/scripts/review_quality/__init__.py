"""Review quality artifact builder — modular package."""

from .registry import SCHEMA_VERSION, DOCUMENT_REGISTRY
from .io import load_input, load_existing, write_artifact
from .validation import validate_input
from .scoring import recompute_doc_score
from .builders import merge_documents, build_history, compact_snapshot
from .tier1 import run_tier1_scripts
