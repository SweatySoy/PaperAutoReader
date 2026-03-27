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

import logging
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol, Optional, Any

import requests

from src.config_loader import Config
from src.models import CandidatePaper, QuadrantCategory, ScoredPaper


# ============================================================================
# Logging Configuration
# ============================================================================

def setup_logging() -> logging.Logger:
    """Configure logging to both console and file."""
    logger = logging.getLogger("FilterAgent")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File Handler
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"system_{date.today().isoformat()}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s - [%(name)s] %(levelname)s: %(message)s"
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()


# ============================================================================
# LLM Service Configuration (Global Variables)
# ============================================================================

# Global configuration for LLM services
# These can be set once at application startup
LLM_API_KEY: str = ""
LLM_API_URL: str = "https://api.minimaxi.com/anthropic"
LLM_MODEL: str = "MiniMax-M2.7"

EMBEDDING_API_KEY: str = ""
EMBEDDING_API_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
EMBEDDING_MODEL: str = "text-embedding-v1"


def configure_llm(api_key: str, api_url: str = "https://api.minimaxi.com/anthropic", model: str = "MiniMax-M2.7") -> None:
    """Configure LLM service settings globally."""
    global LLM_API_KEY, LLM_API_URL, LLM_MODEL
    LLM_API_KEY = api_key
    LLM_API_URL = api_url
    LLM_MODEL = model
    logger.info(f"LLM configured: url={api_url}, model={model}")


def configure_embedding(api_key: str, api_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1", model: str = "qwen3-vl-embedding") -> None:
    """Configure Embedding service settings globally."""
    global EMBEDDING_API_KEY, EMBEDDING_API_URL, EMBEDDING_MODEL
    EMBEDDING_API_KEY = api_key
    EMBEDDING_API_URL = api_url
    EMBEDDING_MODEL = model
    logger.info(f"Embedding configured: url={api_url}, model={model}")


# ============================================================================
# Abstract Interfaces (Protocols)
# ============================================================================

class EmbeddingService(Protocol):
    """Protocol for embedding service."""

    def compute_similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts."""
        ...


class LLMScoringService(Protocol):
    """Protocol for LLM-based scoring."""

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
# Concrete Embedding Service Implementation
# ============================================================================

class OpenAIEmbeddingService:
    """
    Concrete implementation of EmbeddingService using DashScope Qwen embedding API.

    Uses global configuration variables for API settings.
    """

    # Cache for embeddings to reduce API calls
    _embedding_cache: dict[str, list[float]] = {}

    # Default embedding dimension for qwen3-vl-embedding
    DEFAULT_EMBEDDING_DIM: int = 1024

    def __init__(self) -> None:
        """Initialize the embedding service."""
        if not EMBEDDING_API_KEY:
            logger.warning("EMBEDDING_API_KEY not set. Similarity scores will be neutral.")
        self.api_key = EMBEDDING_API_KEY
        self.api_url = EMBEDDING_API_URL
        self.model = EMBEDDING_MODEL

    def _get_embedding(self, text: str) -> list[float]:
        """
        Get embedding vector for a text string.

        Args:
            text: Input text to embed

        Returns:
            Embedding vector (list of floats)
        """
        # Check cache first
        cache_key = hashlib_key(text)
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        # Truncate text if too long
        max_chars = 8000
        truncated_text = text[:max_chars] if len(text) > max_chars else text

        try:
            response = requests.post(
                f"{self.api_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "input": truncated_text,
                    "model": self.model
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            embedding = result["data"][0]["embedding"]

            # Cache the result
            self._embedding_cache[cache_key] = embedding
            logger.debug(f"Embedding computed successfully, dimension: {len(embedding)}")
            return embedding

        except requests.exceptions.RequestException as e:
            logger.error(f"Embedding API error: {e}")
            # Return a zero vector as fallback
            return [0.0] * self.DEFAULT_EMBEDDING_DIM

    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Cosine similarity score (-1 to 1)
        """
        if not self.api_key:
            # Return neutral similarity if not configured
            return 0.5

        emb1 = self._get_embedding(text1)
        emb2 = self._get_embedding(text2)

        # Compute cosine similarity
        similarity = cosine_similarity(emb1, emb2)
        logger.debug(f"Similarity computed: {similarity:.4f}")
        return similarity


def hashlib_key(text: str) -> str:
    """Generate a hash key for caching."""
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    import math

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


# ============================================================================
# Concrete LLM Scoring Service Implementation
# ============================================================================

class OpenAILLMScoringService:
    """
    Concrete implementation of LLMScoringService using Anthropic API (MiniMax-compatible).

    Uses global configuration variables for API settings.
    """

    def __init__(self) -> None:
        """Initialize the LLM service."""
        if not LLM_API_KEY:
            logger.warning("LLM_API_KEY not set. LLM scores will be neutral.")
        self.api_key = LLM_API_KEY
        self.api_url = LLM_API_URL
        self.model = LLM_MODEL
        self.MAX_RETRIES = 3
        self.BASE_DELAY = 2.0

    def _call_llm(self, prompt: str, max_tokens: int = 500) -> str:
        """
        Make a call to the LLM API using Anthropic SDK with retry logic.

        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens in response

        Returns:
            LLM response text (empty string on failure after retries)
        """
        if not self.api_key:
            return ""

        last_error = None
        import anthropic

        for attempt in range(self.MAX_RETRIES):
            try:
                client = anthropic.Anthropic(
                    api_key=self.api_key,
                    base_url=self.api_url,
                    timeout=60.0  # 60 second timeout to prevent hanging
                )
                response = client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    thinking={"type": "disabled"},  # Disable thinking to get clean text
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                # Handle TextBlock in response
                raw_content = ""
                for block in response.content:
                    if hasattr(block, 'text') and block.text:
                        raw_content = block.text
                        break

                return raw_content.strip()

            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                    logger.warning(f"LLM timeout (attempt {attempt + 1}/{self.MAX_RETRIES}), retrying...")
                else:
                    logger.warning(f"LLM API error (attempt {attempt + 1}/{self.MAX_RETRIES}): {error_type}")

                if attempt < self.MAX_RETRIES - 1:
                    import time
                    delay = self.BASE_DELAY * (2 ** attempt)  # Exponential backoff
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"LLM API failed after {self.MAX_RETRIES} attempts: {last_error}")
                    return ""

    def score_task_relevance(self, abstract: str, research_intent: str) -> float:
        """
        Score how well the paper addresses the research intent.

        Args:
            abstract: Paper abstract
            research_intent: Research intent/purpose

        Returns:
            Task relevance score (0-100)
        """
        if not self.api_key:
            return 50.0  # Neutral score

        prompt = f"""Rate how relevant this paper is to the research intent on a scale of 0-100.

Research Intent:
{research_intent}

Paper Abstract:
{abstract[:2000]}

Provide ONLY a single number between 0 and 100. No explanation needed."""

        response = self._call_llm(prompt, max_tokens=10)

        # Parse the score
        try:
            # Extract number from response
            match = re.search(r'\d+', response)
            if match:
                score = int(match.group())
                return float(max(0, min(100, score)))
        except (ValueError, AttributeError):
            pass

        logger.warning(f"Could not parse LLM score from response: {response}")
        return 50.0  # Neutral fallback

    def generate_routing_reason(
        self,
        core_score: float,
        impact_score: float,
        category: QuadrantCategory,
        paper: CandidatePaper
    ) -> str:
        """
        Generate a one-sentence explanation for the routing decision.

        Args:
            core_score: Core relevance score
            impact_score: Impact score
            category: Quadrant category
            paper: The paper

        Returns:
            One-sentence routing reason
        """
        if not self.api_key:
            # Generate mock reason without LLM
            return self._mock_reason(core_score, impact_score, category)

        prompt = f"""Generate a one-sentence explanation for why this paper was classified as {category.value}.

Paper Title: {paper.title}
Core Score: {core_score:.1f}/100
Impact Score: {impact_score:.1f}/100
Authors: {', '.join(paper.authors[:3])}
Venue: {paper.venue}
Citations: {paper.citation_count}

Provide a single sentence explaining the classification. Focus on the key factors."""

        response = self._call_llm(prompt, max_tokens=100)

        if response:
            return response

        # Fallback to mock reason
        return self._mock_reason(core_score, impact_score, category)

    def _mock_reason(
        self,
        core_score: float,
        impact_score: float,
        category: QuadrantCategory
    ) -> str:
        """Generate a mock reason when LLM is not available."""
        reasons = {
            QuadrantCategory.CROWN_JEWEL: f"High relevance ({core_score:.1f}) and high impact ({impact_score:.1f}) - priority read.",
            QuadrantCategory.CORE_TRACK: f"High relevance ({core_score:.1f}) but moderate impact ({impact_score:.1f}) - standard analysis.",
            QuadrantCategory.IMPACT_TRACK: f"Lower relevance ({core_score:.1f}) but high impact ({impact_score:.1f}) - cross-domain insight.",
            QuadrantCategory.REJECTED: f"Lower relevance ({core_score:.1f}) and impact ({impact_score:.1f}) - skip for now."
        }
        return reasons.get(category, "Unknown category")


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

        # Read weights from config
        time_decay_cfg = self.config.time_decay_config
        new_paper_cfg = time_decay_cfg.get("new_paper", {})
        old_paper_cfg = time_decay_cfg.get("old_paper", {})

        # New paper weights
        new_venue = new_paper_cfg.get("venue_weight", 0.50)
        new_author = new_paper_cfg.get("author_weight", 0.30)
        new_github = new_paper_cfg.get("github_weight", 0.20)
        new_citation = new_paper_cfg.get("citation_velocity_weight", 0.0)

        # Old paper weights
        old_venue = old_paper_cfg.get("venue_weight", 0.20)
        old_citation = old_paper_cfg.get("citation_velocity_weight", 0.80)

        # New paper regime (Age < new_threshold)
        if paper_age_days <= new_threshold:
            return {
                "venue": new_venue,
                "author": new_author,
                "github": new_github,
                "citation_velocity": new_citation
            }

        # Old paper regime (Age >= old_threshold)
        if paper_age_days >= old_threshold:
            return {
                "venue": old_venue,
                "author": 0.0,
                "github": 0.0,
                "citation_velocity": old_citation
            }

        # Transitional regime: interpolate between new and old
        # Linear interpolation from new_threshold to old_threshold
        progress = (paper_age_days - new_threshold) / (old_threshold - new_threshold)

        # Interpolate weights
        return {
            "venue": new_venue - (new_venue - old_venue) * progress,
            "author": new_author * (1 - progress),
            "github": new_github * (1 - progress),
            "citation_velocity": old_citation * progress
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
        # arXiv papers get higher score since QML field primarily uses arXiv
        if "arxiv" in venue.lower():
            return 55.0  # arXiv is field-relevant, give credit
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

    def save_checkpoint(
        self,
        scored_papers: list[ScoredPaper],
        output_path: Path | None = None,
        date_str: str | None = None
    ) -> Path:
        """
        Save scored papers to JSON checkpoint file.

        Following the File_IO_and_Logging.md contract:
        - Output to data/scored_papers/YYYY-MM-DD_HH-MM.json
        - Enables resumption if downstream agents fail
        - Auto-generates unique filename to avoid overwriting

        Args:
            scored_papers: List of scored papers to save
            output_path: Custom output path (optional)
            date_str: Date string for filename (defaults to today with time)

        Returns:
            Path to the saved file
        """
        if output_path is None:
            project_root = Path(__file__).parent.parent
            output_dir = project_root / "data" / "scored_papers"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with date and time to avoid overwriting
            if date_str is None:
                from datetime import datetime
                now = datetime.now()
                date_str = f"{now.strftime('%Y-%m-%d_%H-%M')}"

            output_path = output_dir / f"{date_str}.json"

            # If file still exists (same minute), add a counter
            counter = 1
            base_path = output_path
            while output_path.exists():
                output_path = output_dir / f"{date_str}_{counter:02d}.json"
                counter += 1

        # Convert to JSON-serializable format
        data = [paper.model_dump() for paper in scored_papers]

        # Convert date objects to strings for JSON serialization
        for paper_data in data:
            if isinstance(paper_data.get("publication_date"), date):
                paper_data["publication_date"] = paper_data["publication_date"].isoformat()

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(scored_papers)} scored papers to {output_path}")
        return output_path

    @classmethod
    def load_checkpoint(cls, input_path: Path) -> list[ScoredPaper]:
        """
        Load scored papers from JSON checkpoint file.

        Enables resumption from a previous run.

        Args:
            input_path: Path to the checkpoint file

        Returns:
            List of ScoredPaper objects
        """
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Convert date strings back to date objects
        for paper_data in data:
            if isinstance(paper_data.get("publication_date"), str):
                paper_data["publication_date"] = date.fromisoformat(paper_data["publication_date"])

        papers = [ScoredPaper(**paper_data) for paper_data in data]
        logger.info(f"Loaded {len(papers)} scored papers from {input_path}")
        return papers


# ============================================================================
# Factory Function for Easy Setup
# ============================================================================

def create_filter_agent(
    llm_api_key: str = "",
    llm_api_url: str = "https://api.minimaxi.com/anthropic",
    llm_model: str = "MiniMax-M2.7",
    embedding_api_key: str = "",
    embedding_api_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    embedding_model: str = "text-embedding-v1",
    config: Config | None = None
) -> FilterAgent:
    """
    Factory function to create a FilterAgent with configured services.

    This is the recommended way to create a FilterAgent for production use.

    Args:
        llm_api_key: API key for LLM service
        llm_api_url: API URL for LLM service
        llm_model: Model name for LLM service
        embedding_api_key: API key for embedding service
        embedding_api_url: API URL for embedding service
        embedding_model: Model name for embedding service
        config: Configuration instance (uses singleton if None)

    Returns:
        Configured FilterAgent instance
    """
    # Configure global settings
    if llm_api_key:
        configure_llm(llm_api_key, llm_api_url, llm_model)
    if embedding_api_key:
        configure_embedding(embedding_api_key, embedding_api_url, embedding_model)

    # Create services
    embedding_service = OpenAIEmbeddingService() if embedding_api_key else None
    llm_service = OpenAILLMScoringService() if llm_api_key else None

    # Create and return agent
    return FilterAgent(
        config=config,
        embedding_service=embedding_service,
        llm_service=llm_service
    )
