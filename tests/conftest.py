"""Shared test setup: keep the LLM usage state file out of the real data/ folder."""

import os
import tempfile

# Must be set before src.config is imported, because AppSettings reads it at import time.
os.environ.setdefault("LLM_STATE_PATH", os.path.join(tempfile.mkdtemp(prefix="llm-state-"), "llm-state.json"))
