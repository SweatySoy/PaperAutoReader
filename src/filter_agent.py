"""
Filter Agent - Dual-Axis Scoring & Quadrant Routing
====================================================

This module implements the Filter Agent responsible for:
1. Computing Core Score (S_core) - relevance to research intent
2. Computing Impact Score (S_impact) - metadata-based influence
3. Time-decay weighting for dynamic impact calculation
4. Quadrant routing (Crown Jewel / Core / Impact / Rejected)

All domain-specific logic is loaded from the YAML configuration.
NO hardcoded domain values in this code.
"""

from datetime import date, timedelta
from typing import Protocol

from src.config_loader import Config
from src.models import CandidatePaper, QuadrantCategory, ScoredPaper


# ============================================================================
# Abstract Interfaces (for LLM/Embedding integration)
# ============================================================================

class EmbeddingService(Protocol):
    """Protocol for embedding service (to be implemented with actual LLM)."""

    def compute_similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts."""
        ...


class LLMScoringService(Protocol):
    """Protocol for LLM-based scoring (to be implemented with actual LLM)."""

    def score_task_relevance(self, abstract: str, research_intent: str) -> float:
        """Score how well the paper addresses the research intent."""
        ...

    def generate_routing_reason(
        self,
        core_score: float,
        impact_score: float,
        category: QuadrantCategory,
        paper: CandidatePaper
    ) -> str:
        """Generate a one-sentence explanation for the routing decision."""
        ...


# ============================================================================
# Time-Decay Weighting Calculator
# ============================================================================

class TimeDecayCalculator:
    """
    Calculate time-decay weights for impact score computation.

    Based on PRD:
    - New papers (Age < 3 months): 50% Venue + 30% Author + 20% GitHub
    - Old papers (Age > 1 year): 20% Venue + 80% Citation Velocity
    - Transitional papers: interpolated weights
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def get_paper_age_days(self, publication_date: date, current_date: date | None = None) -> int:
        """
        Calculate paper age in days.

        Args:
            publication_date: Paper publication date
            current_date: Current date (defaults to today)

        Returns:
            Age in days
        """
        if current_date is None:
            current_date = date.today()
        return (current_date - publication_date).days

    def get_impact_weights(self, paper_age_days: int) -> dict[str, float]:
        """
        Get impact scoring weights based on paper age.

        Args:
            paper_age_days: Paper age in days

        Returns:
            Dictionary of weights for each impact component
        """
        new_threshold = self.config.new_paper_threshold_days  # 90 days
        old_threshold = self.config.old_paper_threshold_days  # 365 days

        # New paper regime (Age < 3 months)
        if paper_age_days <= new_threshold:
            return {
                "venue": 0.50,
                "author": 0.30,
                "github": 0.20,
                "citation_velocity": 0.0
            }

        # Old paper regime (Age > 1 year)
        if paper_age_days >= old_threshold:
            return {
                "venue": 0.20,
                "author": 0.0,
                "github": 0.0,
                "citation_velocity": 0.80
            }

        # Transitional regime: interpolate between new and old
        # Linear interpolation from new_threshold to old_threshold
        progress = (paper_age_days - new_threshold) / (old_threshold - new_threshold)

        # Interpolate weights
        return {
            "venue": 0.50 - 0.30 * progress,  # 0.50 -> 0.20
            "author": 0.30 * (1 - progress),  # 0.30 -> 0.0
            "github": 0.20 * (1 - progress),  # 0.20 -> 0.0
            "citation_velocity": 0.80 * progress  # 0.0 -> 0.80
        }

    def compute_citation_velocity(
        self,
        citation_count: int,
        paper_age_days: int
    ) -> float:
        """
        Compute monthly citation velocity.

        Args:
            citation_count: Total citations
            paper_age_days: Paper age in days

        Returns:
            Citations per month
        """
        if paper_age_days <= 0:
            return 0.0
        months = paper_age_days / 30.0
        return citation_count / months


# ============================================================================
# Core Score Calculator
# ============================================================================

class CoreScoreCalculator:
    """
    Calculate Core Score (S_core) for papers.

    Components (per PRD):
    - Semantic Match (40%): Embedding similarity with research intent
    - Tech Stack Match (30%): Keyword matching
    - Task Relevance (30%): LLM-based scoring
    """

    def __init__(
        self,
        config: Config,
        embedding_service: EmbeddingService | None = None,
        llm_service: LLMScoringService | None = None
    ) -> None:
        self.config = config
        self.embedding_service = embedding_service
        self.llm_service = llm_service

    def _compute_keyword_score(self, title: str, abstract: str) -> float:
        """
        Compute keyword-based score using configuration keywords.

        Args:
            title: Paper title
            abstract: Paper abstract

        Returns:
            Keyword score (0-100)
        """
        text = (title + " " + abstract).lower()
        score = 0.0

        # Check exclude keywords first (major penalty)
        for keyword in self.config.exclude_keywords:
            if keyword.lower() in text:
                return -100.0  # Immediate rejection

        # Must-have keywords (required)
        must_have_matches = sum(
            1 for kw in self.config.must_have_keywords
            if kw.lower() in text
        )
        if self.config.must_have_keywords:
            must_have_ratio = must_have_matches / len(self.config.must_have_keywords)
            score += 30.0 * must_have_ratio

        # Highly relevant keywords (weight: 1.0)
        highly_relevant_matches = sum(
            1 for kw in self.config.highly_relevant_keywords
            if kw.lower() in text
        )
        score += min(40.0, highly_relevant_matches * 8.0)

        # Relevant keywords (weight: 0.5)
        relevant_matches = sum(
            1 for kw in self.config.relevant_keywords
            if kw.lower() in text
        )
        score += min(20.0, relevant_matches * 4.0)

        return max(-100.0, min(100.0, score))

    def compute_semantic_score(self, abstract: str) -> float:
        """
        Compute semantic similarity with research intent.

        Args:
            abstract: Paper abstract

        Returns:
            Semantic score (0-100). Returns 50.0 if no embedding service.
        """
        if self.embedding_service is None:
            # Mock: return neutral score
            return 50.0

        similarity = self.embedding_service.compute_similarity(
            abstract,
            self.config.research_intent
        )
        # Convert similarity (-1 to 1) to score (0 to 100)
        return max(0.0, min(100.0, (similarity + 1) * 50))

    def compute_task_relevance(self, abstract: str) -> float:
        """
        Compute task relevance using LLM.

        Args:
            abstract: Paper abstract

        Returns:
            Task relevance score (0-100). Returns 50.0 if no LLM service.
        """
        if self.llm_service is None:
            return 50.0

        return self.llm_service.score_task_relevance(
            abstract,
            self.config.research_intent
        )

    def compute_core_score(
        self,
        paper: CandidatePaper,
        use_llm: bool = True
    ) -> float:
        """
        Compute the overall Core Score for a paper.

        Args:
            paper: The candidate paper
            use_llm: Whether to use LLM for scoring (default True)

        Returns:
            Core score (0-100)
        """
        # Component 1: Semantic match (40%)
        semantic_score = self.compute_semantic_score(paper.abstract)

        # Component 2: Keyword match (30%) - serves as tech stack match
        keyword_score = self._compute_keyword_score(paper.title, paper.abstract)

        # Component 3: Task relevance (30%)
        task_score = (
            self.compute_task_relevance(paper.abstract)
            if use_llm else 50.0
        )

        # Combine scores
        # If keyword score is very negative (exclude hit), penalize heavily
        if keyword_score < 0:
            return max(0.0, keyword_score)

        final_score = (
            0.40 * semantic_score +
            0.30 * keyword_score +
            0.30 * task_score
        )

        return max(0.0, min(100.0, final_score))


# ============================================================================
# Impact Score Calculator
# ============================================================================

class ImpactScoreCalculator:
    """
    Calculate Impact Score (S_impact) for papers.

    Components vary by paper age (time-decay weighting).
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.time_decay = TimeDecayCalculator(config)

    def _compute_venue_score(self, venue: str) -> float:
        """
        Compute venue-based score.

        Args:
            venue: Publication venue name

        Returns:
            Venue score (0-100)
        """
        if self.config.is_tier_1_venue(venue):
            return 100.0
        if venue in self.config.get_all_venues():
            return 70.0  # Tier 2
        return 30.0  # Unknown venue

    def _compute_author_score(self, authors: list[str]) -> float:
        """
        Compute author-based score.

        Args:
            authors: List of author names

        Returns:
            Author score (0-100)
        """
        for author in authors:
            if self.config.is_vip_author(author):
                return 100.0

        # Check institutions (simplified - would need affiliation data)
        # For now, return neutral score
        return 50.0

    def _compute_github_score(self, has_github: bool) -> float:
        """
        Compute GitHub presence score.

        Args:
            has_github: Whether paper has GitHub link

        Returns:
            GitHub score (0-100)
        """
        return 80.0 if has_github else 20.0

    def _compute_citation_velocity_score(
        self,
        citation_count: int,
        paper_age_days: int
    ) -> float:
        """
        Compute citation velocity score.

        Args:
            citation_count: Total citations
            paper_age_days: Paper age in days

        Returns:
            Citation velocity score (0-100)
        """
        velocity = self.time_decay.compute_citation_velocity(
            citation_count,
            paper_age_days
        )

        # Normalize velocity to 0-100
        # High velocity: > 10 citations/month -> 100
        # Low velocity: < 1 citation/month -> 20
        if velocity >= 10:
            return 100.0
        if velocity >= 5:
            return 80.0
        if velocity >= 2:
            return 60.0
        if velocity >= 1:
            return 40.0
        return 20.0

    def compute_impact_score(
        self,
        paper: CandidatePaper,
        current_date: date | None = None
    ) -> float:
        """
        Compute the overall Impact Score for a paper.

        Args:
            paper: The candidate paper
            current_date: Current date (defaults to today)

        Returns:
            Impact score (0-100)
        """
        if current_date is None:
            current_date = date.today()

        age_days = self.time_decay.get_paper_age_days(
            paper.publication_date,
            current_date
        )
        weights = self.time_decay.get_impact_weights(age_days)

        # Compute individual scores
        venue_score = self._compute_venue_score(paper.venue)
        author_score = self._compute_author_score(paper.authors)
        github_score = self._compute_github_score(paper.has_github_link)
        velocity_score = self._compute_citation_velocity_score(
            paper.citation_count,
            age_days
        )

        # Combine with time-decay weights
        final_score = (
            weights["venue"] * venue_score +
            weights["author"] * author_score +
            weights["github"] * github_score +
            weights["citation_velocity"] * velocity_score
        )

        return max(0.0, min(100.0, final_score))


# ============================================================================
# Quadrant Router
# ============================================================================

class QuadrantRouter:
    """
    Route papers to quadrants based on dual-axis scores.

    Threshold values are loaded from configuration.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def route(
        self,
        core_score: float,
        impact_score: float
    ) -> QuadrantCategory:
        """
        Determine quadrant category based on scores.

        Args:
            core_score: Core relevance score
            impact_score: Impact score

        Returns:
            Quadrant category
        """
        core_threshold = self.config.core_threshold
        impact_threshold = self.config.impact_threshold

        is_high_core = core_score >= core_threshold
        is_high_impact = impact_score >= impact_threshold

        if is_high_core and is_high_impact:
            return QuadrantCategory.CROWN_JEWEL
        if is_high_core and not is_high_impact:
            return QuadrantCategory.CORE_TRACK
        if not is_high_core and is_high_impact:
            return QuadrantCategory.IMPACT_TRACK
        return QuadrantCategory.REJECTED


# ============================================================================
# Filter Agent (Main Orchestrator)
# ============================================================================

class FilterAgent:
    """
    Filter Agent: Orchestrates dual-axis scoring and quadrant routing.

    This is the main entry point for the filtering pipeline.
    """

    def __init__(
        self,
        config: Config | None = None,
        embedding_service: EmbeddingService | None = None,
        llm_service: LLMScoringService | None = None
    ) -> None:
        """
        Initialize Filter Agent with optional services.

        Args:
            config: Configuration instance (uses singleton if None)
            embedding_service: Embedding service for semantic scoring
            llm_service: LLM service for task relevance scoring
        """
        self.config = config or Config.get_instance()
        self.core_calculator = CoreScoreCalculator(
            self.config,
            embedding_service,
            llm_service
        )
        self.impact_calculator = ImpactScoreCalculator(self.config)
        self.router = QuadrantRouter(self.config)
        self.llm_service = llm_service

    def _generate_routing_reason(
        self,
        paper: CandidatePaper,
        core_score: float,
        impact_score: float,
        category: QuadrantCategory
    ) -> str:
        """
        Generate explanation for routing decision.

        Args:
            paper: The paper being scored
            core_score: Core score
            impact_score: Impact score
            category: Resulting category

        Returns:
            One-sentence routing reason
        """
        if self.llm_service is not None:
            return self.llm_service.generate_routing_reason(
                core_score,
                impact_score,
                category,
                paper
            )

        # Mock reason based on scores
        reasons = {
            QuadrantCategory.CROWN_JEWEL: f"High relevance ({core_score:.1f}) and high impact ({impact_score:.1f}) - priority read.",
            QuadrantCategory.CORE_TRACK: f"High relevance ({core_score:.1f}) but moderate impact ({impact_score:.1f}) - standard analysis.",
            QuadrantCategory.IMPACT_TRACK: f"Lower relevance ({core_score:.1f}) but high impact ({impact_score:.1f}) - cross-domain insight.",
            QuadrantCategory.REJECTED: f"Lower relevance ({core_score:.1f}) and impact ({impact_score:.1f}) - skip for now."
        }
        return reasons.get(category, "Unknown category")

    def score_paper(
        self,
        paper: CandidatePaper,
        use_llm: bool = True
    ) -> ScoredPaper:
        """
        Score a single paper and determine its quadrant.

        Args:
            paper: The candidate paper to score
            use_llm: Whether to use LLM for scoring (default True)

        Returns:
            ScoredPaper with scores and classification
        """
        # Compute scores
        core_score = self.core_calculator.compute_core_score(paper, use_llm)
        impact_score = self.impact_calculator.compute_impact_score(paper)

        # Determine category
        category = self.router.route(core_score, impact_score)

        # Generate reason
        reason = self._generate_routing_reason(
            paper,
            core_score,
            impact_score,
            category
        )

        # Create scored paper
        return ScoredPaper(
            **paper.model_dump(),
            core_score=core_score,
            impact_score=impact_score,
            quadrant_category=category,
            routing_reason=reason
        )

    def score_papers(
        self,
        papers: list[CandidatePaper],
        use_llm: bool = True
    ) -> list[ScoredPaper]:
        """
        Score multiple papers in batch.

        Args:
            papers: List of candidate papers
            use_llm: Whether to use LLM for scoring (default True)

        Returns:
            List of scored papers
        """
        return [self.score_paper(paper, use_llm) for paper in papers]

    def get_papers_by_category(
        self,
        scored_papers: list[ScoredPaper],
        category: QuadrantCategory
    ) -> list[ScoredPaper]:
        """
        Filter scored papers by category.

        Args:
            scored_papers: List of scored papers
            category: Category to filter by

        Returns:
            Papers matching the category
        """
        return [p for p in scored_papers if p.quadrant_category == category]
