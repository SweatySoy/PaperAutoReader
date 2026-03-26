"""
PaperAutoReader - Research Radar System
=======================================

A dual-axis paper classification and situational awareness system.
"""

from src.models import (
    CandidatePaper,
    ScoredPaper,
    AnalyzedPaper,
    FinalReport,
    QuadrantCategory,
)
from src.config_loader import Config
from src.agents.filter_agent import FilterAgent

__all__ = [
    "CandidatePaper",
    "ScoredPaper",
    "AnalyzedPaper",
    "FinalReport",
    "QuadrantCategory",
    "Config",
    "FilterAgent",
]
