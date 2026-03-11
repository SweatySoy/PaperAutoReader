"""
Core Data Models for PaperAutoReader - Research Radar System
=============================================================

This module defines all Pydantic data models following the strict data contract
specified in rules/Data_Schemas_Contract.md.

The pipeline lifecycle is:
    CandidatePaper -> ScoredPaper -> AnalyzedPaper -> FinalReport
"""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class QuadrantCategory(str, Enum):
    """
    Four-quadrant classification for paper routing.

    Based on dual-axis scoring (Core Score vs Impact Score):
    - CROWN_JEWEL: High Core + High Impact -> Deep Analysis (Max)
    - CORE_TRACK: High Core + Low Impact -> Deep Analysis (Std)
    - IMPACT_TRACK: Low Core + High Impact -> Impact Briefing
    - REJECTED: Low Core + Low Impact -> Short Note
    """
    CROWN_JEWEL = "CROWN_JEWEL"
    CORE_TRACK = "CORE_TRACK"
    IMPACT_TRACK = "IMPACT_TRACK"
    REJECTED = "REJECTED"


# ============================================================================
# State 1: CandidatePaper (Search Agent Output / Filter Agent Input)
# ============================================================================

class CandidatePaper(BaseModel):
    """
    Raw paper fetched from arXiv or Semantic Scholar, before any processing.

    This represents the initial state of a paper entering the pipeline.
    """
    paper_id: str = Field(..., description="Unique identifier, e.g., arXiv ID")
    title: str = Field(..., description="Paper title")
    abstract: str = Field(..., description="Paper abstract text")
    authors: list[str] = Field(default_factory=list, description="List of author names")
    venue: str = Field(default="arXiv", description="Publication venue (journal/conference)")
    publication_date: date = Field(..., description="Publication date for age calculation")
    url: str = Field(..., description="URL to the paper")
    citation_count: int = Field(default=0, ge=0, description="Total citation count")
    influential_citation_count: int = Field(default=0, ge=0, description="Influential citation count")
    has_github_link: bool = Field(default=False, description="Whether paper has a GitHub link")


# ============================================================================
# State 2: ScoredPaper (Filter Agent Output / Analysis Agent Input)
# ============================================================================

class ScoredPaper(CandidatePaper):
    """
    Paper after dual-axis scoring by Filter Agent.

    Inherits all CandidatePaper fields and adds scoring + classification.
    """
    core_score: float = Field(..., ge=0.0, le=100.0, description="Core relevance score (0-100)")
    impact_score: float = Field(..., ge=0.0, le=100.0, description="Impact score (0-100)")
    quadrant_category: QuadrantCategory = Field(
        ...,
        description="Classification quadrant based on scores"
    )
    routing_reason: str = Field(
        ...,
        description="One-sentence explanation for the classification"
    )


# ============================================================================
# State 3: AnalyzedPaper (Analysis Agent Output / Report Agent Input)
# ============================================================================

class AnalyzedPaper(ScoredPaper):
    """
    Paper after deep analysis by Analysis Agent.

    Inherits all ScoredPaper fields and adds analysis content.
    The content fields are filled based on the quadrant category:
    - CROWN_JEWEL / CORE_TRACK: analysis_summary, extracted_methods
    - IMPACT_TRACK: impact_briefing
    - REJECTED: rejection_note
    """
    analysis_summary: Optional[str] = Field(
        default=None,
        description="Summary generated based on quadrant category"
    )
    extracted_methods: list[str] = Field(
        default_factory=list,
        description="Extracted methodologies (mainly for Core / Crown Jewel)"
    )
    impact_briefing: Optional[str] = Field(
        default=None,
        description="Cross-domain insights (mainly for Impact Track)"
    )
    rejection_note: Optional[str] = Field(
        default=None,
        description="Rejection reason (mainly for Rejected)"
    )


# ============================================================================
# State 4: FinalReport (Report Agent Output)
# ============================================================================

class FinalReport(BaseModel):
    """
    Final report structure for rendering user-facing output.

    Papers are organized by quadrant category for easy navigation.
    """
    report_date: date = Field(..., description="Report generation date")
    crown_jewels: list[AnalyzedPaper] = Field(
        default_factory=list,
        description="Must-read classic papers"
    )
    core_papers: list[AnalyzedPaper] = Field(
        default_factory=list,
        description="Daily domain tracking papers"
    )
    impact_papers: list[AnalyzedPaper] = Field(
        default_factory=list,
        description="Cross-domain high-impact papers"
    )
    rejected_papers_log: list[AnalyzedPaper] = Field(
        default_factory=list,
        description="Filtered-out papers for audit trail"
    )
