"""
Configuration Loader for PaperAutoReader - Research Radar System
================================================================

This module provides a singleton-based configuration loader that reads
domain-specific settings from YAML files. Following the strict decoupling
principle: NO hardcoded domain values in the code.

All system-level configurations, prompts, scoring weights, and entity lists
are dynamically loaded from the Domain Profile YAML file.

Usage:
    from src.config_loader import Config
    config = Config.get_instance()
    print(config.profile_name)
"""

from pathlib import Path
from typing import Any, Optional

import yaml


class Config:
    """
    Singleton configuration loader for domain profile settings.

    This class ensures:
    1. Single instance across the application
    2. Lazy loading of YAML configuration
    3. Type-safe access to configuration values
    4. Default fallback values where appropriate
    """

    _instance: Optional["Config"] = None
    _config_path: Optional[Path] = None

    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize configuration - only loads on first access."""
        if not hasattr(self, "_loaded"):
            self._loaded = False
            self._raw_config: dict[str, Any] = {}

    @classmethod
    def get_instance(cls, config_path: Optional[Path] = None) -> "Config":
        """
        Get the singleton instance, optionally specifying config path.

        Args:
            config_path: Path to the YAML config file. If None, uses default.

        Returns:
            The singleton Config instance.
        """
        instance = cls()
        if config_path is not None:
            cls._config_path = config_path
        if not instance._loaded:
            instance._load_config()
        return instance

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if self._config_path is None:
            # Default path: fields/Domain_Profile_*.yaml
            project_root = Path(__file__).parent.parent
            fields_dir = project_root / "fields"
            # Find the first matching profile file
            profile_files = list(fields_dir.glob("Domain_Profile_*.yaml"))
            if not profile_files:
                raise FileNotFoundError(
                    "No Domain_Profile_*.yaml found in fields/ directory. "
                    "Please create a domain profile configuration file."
                )
            self._config_path = profile_files[0]

        with open(self._config_path, "r", encoding="utf-8") as f:
            self._raw_config = yaml.safe_load(f) or {}

        self._loaded = True

    # ========================================================================
    # Basic Profile Information
    # ========================================================================

    @property
    def profile_name(self) -> str:
        """Name of the research profile."""
        return self._raw_config.get("profile_name", "Default Researcher")

    @property
    def target_discipline(self) -> str:
        """Target discipline for the research."""
        return self._raw_config.get("target_discipline", "General Research")

    @property
    def research_intent(self) -> str:
        """Research intent/purpose for prompt injection."""
        return self._raw_config.get("research_intent", "")

    # ========================================================================
    # Scoring Thresholds (with defaults)
    # ========================================================================

    @property
    def core_threshold(self) -> float:
        """Threshold for Core Score classification (default: 70)."""
        return self._raw_config.get("scoring_thresholds", {}).get("core_threshold", 70.0)

    @property
    def impact_threshold(self) -> float:
        """Threshold for Impact Score classification (default: 70)."""
        return self._raw_config.get("scoring_thresholds", {}).get("impact_threshold", 70.0)

    # ========================================================================
    # Keyword Scoring Configuration
    # ========================================================================

    @property
    def keywords_scoring(self) -> dict[str, Any]:
        """Full keyword scoring configuration."""
        return self._raw_config.get("keywords_scoring", {})

    @property
    def must_have_keywords(self) -> list[str]:
        """Must-have keywords for core scoring."""
        return self.keywords_scoring.get("must_have", [])

    @property
    def highly_relevant_keywords(self) -> list[str]:
        """Highly relevant keywords (weight: 1.0)."""
        return self.keywords_scoring.get("highly_relevant", [])

    @property
    def relevant_keywords(self) -> list[str]:
        """Relevant keywords (weight: 0.5)."""
        return self.keywords_scoring.get("relevant", [])

    @property
    def exclude_keywords(self) -> list[str]:
        """Exclude keywords (weight: -100, triggers rejection)."""
        return self.keywords_scoring.get("exclude", [])

    # ========================================================================
    # Impact Entities Configuration
    # ========================================================================

    @property
    def impact_entities(self) -> dict[str, Any]:
        """Full impact entities configuration."""
        return self._raw_config.get("impact_entities", {})

    @property
    def tier_1_venues(self) -> list[str]:
        """Tier 1 publication venues (top journals/conferences)."""
        return self.impact_entities.get("tier_1_venues", [])

    @property
    def tier_2_venues(self) -> list[str]:
        """Tier 2 publication venues."""
        return self.impact_entities.get("tier_2_venues", [])

    @property
    def tier_1_institutions(self) -> list[str]:
        """Tier 1 institutions (top research institutions)."""
        return self.impact_entities.get("tier_1_institutions", [])

    @property
    def vip_authors(self) -> list[str]:
        """VIP authors (must-follow researchers)."""
        return self.impact_entities.get("vip_authors", [])

    # ========================================================================
    # Analysis Prompts Configuration
    # ========================================================================

    @property
    def analysis_prompts(self) -> dict[str, str]:
        """Full analysis prompts configuration."""
        return self._raw_config.get("analysis_prompts", {})

    @property
    def core_paper_focus(self) -> str:
        """Focus prompt for core paper analysis."""
        return self.analysis_prompts.get("core_paper_focus", "")

    @property
    def impact_paper_focus(self) -> str:
        """Focus prompt for impact paper analysis."""
        return self.analysis_prompts.get("impact_paper_focus", "")

    # ========================================================================
    # Time-Decay Weighting Configuration
    # ========================================================================

    @property
    def time_decay_config(self) -> dict[str, Any]:
        """Time-decay weighting configuration."""
        return self._raw_config.get("time_decay", {})

    @property
    def new_paper_threshold_days(self) -> int:
        """Days threshold for 'new paper' (default: 90 days = 3 months)."""
        return self.time_decay_config.get("new_paper_threshold_days", 90)

    @property
    def old_paper_threshold_days(self) -> int:
        """Days threshold for 'old paper' (default: 365 days = 1 year)."""
        return self.time_decay_config.get("old_paper_threshold_days", 365)

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_all_venues(self) -> list[str]:
        """Get all venues (Tier 1 + Tier 2) for matching."""
        return self.tier_1_venues + self.tier_2_venues

    def is_tier_1_venue(self, venue: str) -> bool:
        """Check if a venue is Tier 1."""
        return venue in self.tier_1_venues

    def is_vip_author(self, author: str) -> bool:
        """Check if an author is a VIP."""
        return author in self.vip_authors

    def is_tier_1_institution(self, institution: str) -> bool:
        """Check if an institution is Tier 1."""
        return institution in self.tier_1_institutions

    def reload(self, config_path: Optional[Path] = None) -> None:
        """
        Force reload configuration from file.

        Args:
            config_path: New config path to use (optional).
        """
        if config_path is not None:
            self._config_path = config_path
        self._loaded = False
        self._load_config()

    def to_dict(self) -> dict[str, Any]:
        """
        Export configuration as dictionary (for debugging/logging).

        Returns:
            A copy of the raw configuration dictionary.
        """
        return self._raw_config.copy()
