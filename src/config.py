"""Configuration and Environment Loader."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Resilient imports for optional third-party modules
try:
    import yaml
except ImportError:
    yaml = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Base project directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env file if dotenv available
if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class AppSettings:
    """Application settings loaded from environment variables."""
    llm_provider: str = os.getenv("LLM_PROVIDER", "offline").lower()
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    llm_api_base_url: Optional[str] = os.getenv("LLM_API_BASE_URL")

    # Platform credentials (to be filled later by user)
    naukri_api_token: Optional[str] = os.getenv("NAUKRI_API_TOKEN")
    naukri_client_id: Optional[str] = os.getenv("NAUKRI_CLIENT_ID")
    apify_api_token: Optional[str] = os.getenv("APIFY_API_TOKEN")

    # Supabase Database Configuration
    supabase_url: Optional[str] = os.getenv("SUPABASE_URL")
    supabase_key: Optional[str] = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    database_url: Optional[str] = os.getenv("DATABASE_URL")

    # Paths
    candidate_profile_path: Path = PROJECT_ROOT / os.getenv("CANDIDATE_PROFILE_PATH", "data/candidate-profile.json")
    scoring_config_path: Path = PROJECT_ROOT / os.getenv("SCORING_CONFIG_PATH", "config/scoring.yaml")
    policy_config_path: Path = PROJECT_ROOT / os.getenv("POLICY_CONFIG_PATH", "config/policy.yaml")
    target_profile_path: Path = PROJECT_ROOT / "config/target-profile.yaml"
    output_dir: Path = PROJECT_ROOT / os.getenv("OUTPUT_DIR", "outputs")

    min_match_score: float = float(os.getenv("MIN_MATCH_SCORE", "75.0"))

    def has_llm_credentials(self) -> bool:
        """Check whether any live LLM API keys are provided."""
        if self.llm_provider == "gemini" and self.gemini_api_key and "your_" not in self.gemini_api_key:
            return True
        if self.llm_provider == "openai" and self.openai_api_key and "your_" not in self.openai_api_key:
            return True
        if self.llm_provider == "anthropic" and self.anthropic_api_key and "your_" not in self.anthropic_api_key:
            return True
        if any([
            self.gemini_api_key and "your_" not in self.gemini_api_key,
            self.openai_api_key and "your_" not in self.openai_api_key,
            self.anthropic_api_key and "your_" not in self.anthropic_api_key,
        ]):
            return True
        return False

    def credential_status(self) -> Dict[str, bool]:
        """Return status summary of all configured credentials."""
        def is_valid(val: Optional[str]) -> bool:
            return bool(val and not val.startswith("your_") and len(val.strip()) > 5)

        is_supabase_ready = (is_valid(self.supabase_url) and is_valid(self.supabase_key)) or (
            bool(self.database_url) and ("postgres://" in self.database_url or "postgresql://" in self.database_url)
        )

        return {
            "gemini_api": is_valid(self.gemini_api_key),
            "openai_api": is_valid(self.openai_api_key),
            "anthropic_api": is_valid(self.anthropic_api_key),
            "naukri_api": is_valid(self.naukri_api_token),
            "apify_api": is_valid(self.apify_api_token),
            "supabase_database": is_supabase_ready,
        }


def load_yaml_config(file_path: Path) -> Dict[str, Any]:
    """Safely load a YAML configuration file with JSON fallback."""
    if not file_path.exists():
        json_path = file_path.with_suffix(".json")
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    if yaml is not None:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Error parsing {file_path} with yaml: {e}")

    # Fallback to json equivalent if yaml is not installed or errors
    json_path = file_path.with_suffix(".json")
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    return {}


def load_candidate_profile(file_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the candidate profile JSON."""
    settings = AppSettings()
    path = file_path or settings.candidate_profile_path
    if not path.exists():
        fallback = PROJECT_ROOT / "data/candidate-profile.example.json"
        if fallback.exists():
            path = fallback
        else:
            raise FileNotFoundError(f"Candidate profile not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
