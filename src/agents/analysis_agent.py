"""
Analysis Agent - Deep Paper Analysis Module
============================================

Responsibilities:
- Receive ScoredPaper list and analyze based on quadrant category
- Dynamically assemble prompts based on paper classification
- Call LLM with anti-hallucination measures
- Generate AnalyzedPaper output

Strictly follows:
- rules/System_Architecture_PRD.md
- rules/Data_Schemas_Contract.md
- rules/File_IO_and_Logging.md
"""

import json
import logging
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

# Import models and config
from src.models import AnalyzedPaper, QuadrantCategory, ScoredPaper
from src.config_loader import Config

# ============================================================================
# Logging Configuration (follows File_IO_and_Logging.md)
# ============================================================================

def setup_logging() -> logging.Logger:
    """Configure standard logging with console and file output."""
    logger = logging.getLogger("AnalysisAgent")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File Handler
    log_dir = Path(__file__).parent.parent.parent / "logs"
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
# LLM Client with Retry & Anti-Hallucination
# ============================================================================

class LLMClient:
    """
    LLM API client with retry mechanism and JSON parsing.

    Uses Anthropic API (MiniMax-compatible). Handles:
    - Rate limiting with exponential backoff
    - JSON parsing from various response formats
    - Retry on transient failures
    """

    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # seconds
    DEFAULT_MODEL = "MiniMax-M2.7"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize LLM client.

        Args:
            api_key: Anthropic API key (if None, reads from ANTHROPIC_AUTH_TOKEN env)
            model: Model to use (default: MiniMax-M2.7)
            base_url: Custom base URL (for MiniMax/custom deployments)
        """
        try:
            import anthropic
            self._anthropic = anthropic
        except ImportError:
            raise ImportError(
                "anthropic package not installed. "
                "Please install with: pip install anthropic"
            )

        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=60.0  # 60 second timeout to prevent hanging
        )
        self.model = model or self.DEFAULT_MODEL
        logger.info(f"LLM Client initialized with model: {self.model}, base_url: {base_url}")

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Extract JSON from LLM response with anti-hallucination measures.

        Handles various formats:
        - Pure JSON
        - ```json ... ``` code blocks
        - ``` ... ``` code blocks
        - Text with embedded JSON

        Args:
            text: Raw text from LLM

        Returns:
            Parsed JSON dictionary

        Raises:
            ValueError: If no valid JSON found
        """
        text = text.strip()

        # Try direct JSON parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from ```json ... ``` blocks
        json_block_pattern = r'```(?:json)?\s*\n?([\s\S]*?)\n?```'
        matches = re.findall(json_block_pattern, text)

        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

        # Try finding JSON-like structures with braces
        brace_pattern = r'\{[\s\S]*\}'
        brace_matches = re.findall(brace_pattern, text)

        for match in brace_matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        raise ValueError(f"Could not extract valid JSON from response: {text[:200]}...")

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Call LLM with retry mechanism.

        Args:
            system_prompt: System message
            user_prompt: User message
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            Parsed JSON response

        Raises:
            RuntimeError: If all retries fail
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )

                # Handle both TextBlock and ThinkingBlock in response
                # MiniMax-M2.7 may return ThinkingBlock with thinking content
                raw_content = ""
                for block in response.content:
                    if hasattr(block, 'text') and block.text:
                        raw_content = block.text
                        break

                if not raw_content:
                    # Try to extract from ThinkingBlock if no TextBlock found
                    for block in response.content:
                        if hasattr(block, 'thinking'):
                            raw_content = f"[Thinking: {block.thinking[:500]}...]"
                            break

                logger.debug(f"LLM raw response (attempt {attempt + 1}): {raw_content[:100]}...")

                # Parse JSON from response
                parsed = self._extract_json(raw_content)
                return parsed

            except self._anthropic.RateLimitError as e:
                last_error = e
                delay = self.BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"LLM rate limited, attempt {attempt + 1}/{self.MAX_RETRIES}, "
                    f"waiting {delay:.1f}s..."
                )
                time.sleep(delay)

            except self._anthropic.APIError as e:
                last_error = e
                logger.error(f"LLM API error (attempt {attempt + 1}): {e}")
                time.sleep(self.BASE_DELAY * (attempt + 1))

            except ValueError as e:
                # JSON parsing error
                last_error = e
                logger.error(f"JSON parsing error (attempt {attempt + 1}): {e}")
                # Retry with more explicit JSON request
                user_prompt = user_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON."

            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                if "timeout" in error_str or "timed out" in error_str:
                    logger.warning(f"LLM timeout (attempt {attempt + 1}/{self.MAX_RETRIES})")
                else:
                    logger.warning(f"Unexpected error (attempt {attempt + 1}/{self.MAX_RETRIES}): {type(e).__name__}")

        # Return fallback response instead of raising error to allow pipeline to continue
        logger.warning(f"LLM call failed after {self.MAX_RETRIES} retries, using fallback. Last error: {last_error}")
        return {
            "analysis_summary": f"[Analysis unavailable due to LLM error: {type(last_error).__name__}]",
            "extracted_methods": [],
            "relevance_to_research": "Analysis failed due to service error"
        }


# ============================================================================
# Prompt Assembler
# ============================================================================

class PromptAssembler:
    """
    Dynamically assemble prompts based on paper quadrant and config.
    """

    def __init__(self, config: Config):
        """
        Initialize with config.

        Args:
            config: Config instance for reading prompts
        """
        self.config = config

    def assemble_system_prompt(self, paper: ScoredPaper) -> str:
        """
        Assemble system prompt based on paper's quadrant category.

        Args:
            paper: ScoredPaper to analyze

        Returns:
            Complete system prompt for LLM
        """
        base_prompt = f"""You are an expert research paper analyst specializing in {self.config.target_discipline}.

Your task is to analyze the following paper and extract structured insights.

RESEARCH CONTEXT:
{self.config.research_intent}

PAPER TITLE: {paper.title}
PAPER ABSTRACT: {paper.abstract}
PAPER AUTHORS: {', '.join(paper.authors)}
PUBLICATION VENUE: {paper.venue}
"""

        category = paper.quadrant_category

        if category in (QuadrantCategory.CROWN_JEWEL, QuadrantCategory.CORE_TRACK):
            # Deep analysis for core papers
            specific_instructions = f"""
ANALYSIS FOCUS (Core/Crown Jewel Paper):
{self.config.core_paper_focus}

You MUST respond with a JSON object containing:
1. "analysis_summary": A 2-3 paragraph summary of the paper's key contributions
2. "extracted_methods": An array of specific methodologies/techniques mentioned (be precise)
3. "relevance_to_research": How this relates to the research context above
"""
        elif category == QuadrantCategory.IMPACT_TRACK:
            # Impact-focused analysis
            specific_instructions = f"""
ANALYSIS FOCUS (Impact Track Paper):
{self.config.impact_paper_focus}

You MUST respond with a JSON object containing:
1. "impact_briefing": A concise explanation of the breakthrough and its potential cross-domain impact
2. "key_innovation": The single most important innovation in this paper
3. "potential_applications": How this might influence other fields
"""
        else:
            # Should not reach here (REJECTED papers don't call LLM)
            specific_instructions = ""

        return base_prompt + specific_instructions

    def assemble_user_prompt(self, paper: ScoredPaper) -> str:
        """
        Assemble user prompt for analysis.

        Args:
            paper: ScoredPaper to analyze

        Returns:
            User prompt for LLM
        """
        category = paper.quadrant_category

        if category in (QuadrantCategory.CROWN_JEWEL, QuadrantCategory.CORE_TRACK):
            return """Analyze this paper and extract the following:

1. A comprehensive summary focusing on technical contributions
2. Specific methodologies, algorithms, or techniques used
3. How it relates to variational quantum algorithms or quantum machine learning

Respond in JSON format with keys: "analysis_summary", "extracted_methods", "relevance_to_research"
"""
        elif category == QuadrantCategory.IMPACT_TRACK:
            return """Analyze this paper for its broader impact:

1. What is the core breakthrough? Explain in simple terms.
2. How might this influence quantum machine learning research?
3. What paradigm shift does this represent?

Respond in JSON format with keys: "impact_briefing", "key_innovation", "potential_applications"
"""
        else:
            return ""


# ============================================================================
# Analysis Agent
# ============================================================================

class AnalysisAgent:
    """
    Analysis Agent: Deep paper analysis based on quadrant classification.

    Workflow:
    1. Receive ScoredPaper list
    2. Skip REJECTED papers (no LLM call to save cost)
    3. Call LLM for CORE_TRACK/CROWN_JEWEL/IMPACT_TRACK papers
    4. Parse and validate results
    5. Output AnalyzedPaper list
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        llm_client: Optional[LLMClient] = None
    ):
        """
        Initialize Analysis Agent.

        Args:
            config: Config instance (default: load from file)
            llm_client: LLM client instance (default: create new)
        """
        self.config = config or Config.get_instance()
        self.prompt_assembler = PromptAssembler(self.config)
        self.llm_client = llm_client or LLMClient()

    def _analyze_core_paper(
        self,
        paper: ScoredPaper
    ) -> Dict[str, Any]:
        """
        Analyze a core/crown jewel paper with deep technical focus.

        Args:
            paper: ScoredPaper to analyze

        Returns:
            Analysis result dictionary
        """
        logger.info(f"Analyzing core paper: {paper.title[:50]}...")

        system_prompt = self.prompt_assembler.assemble_system_prompt(paper)
        user_prompt = self.prompt_assembler.assemble_user_prompt(paper)

        try:
            result = self.llm_client.call(system_prompt, user_prompt)

            return {
                "analysis_summary": result.get("analysis_summary", ""),
                "extracted_methods": result.get("extracted_methods", []),
                "impact_briefing": None,
                "rejection_note": None
            }
        except Exception as e:
            logger.error(f"Failed to analyze core paper {paper.paper_id}: {e}")
            # Return fallback analysis
            return {
                "analysis_summary": f"Analysis failed: {str(e)}",
                "extracted_methods": [],
                "impact_briefing": None,
                "rejection_note": None
            }

    def _analyze_impact_paper(
        self,
        paper: ScoredPaper
    ) -> Dict[str, Any]:
        """
        Analyze an impact track paper with focus on broader implications.

        Args:
            paper: ScoredPaper to analyze

        Returns:
            Analysis result dictionary
        """
        logger.info(f"Analyzing impact paper: {paper.title[:50]}...")

        system_prompt = self.prompt_assembler.assemble_system_prompt(paper)
        user_prompt = self.prompt_assembler.assemble_user_prompt(paper)

        try:
            result = self.llm_client.call(system_prompt, user_prompt)

            return {
                "analysis_summary": None,
                "extracted_methods": [],
                "impact_briefing": result.get("impact_briefing", ""),
                "rejection_note": None
            }
        except Exception as e:
            logger.error(f"Failed to analyze impact paper {paper.paper_id}: {e}")
            return {
                "analysis_summary": None,
                "extracted_methods": [],
                "impact_briefing": f"Analysis failed: {str(e)}",
                "rejection_note": None
            }

    def _generate_rejection_note(
        self,
        paper: ScoredPaper
    ) -> str:
        """
        Generate rejection note for rejected papers (no LLM call).

        Args:
            paper: ScoredPaper (REJECTED category)

        Returns:
            Rejection note string
        """
        logger.info(f"Generating rejection note for: {paper.title[:50]}...")

        # Build rejection note based on routing reason
        note = f"Rejected: {paper.routing_reason}"

        # Add score context
        note += f" (Core Score: {paper.core_score:.1f}, Impact Score: {paper.impact_score:.1f})"

        # Add keyword hints if available
        if paper.core_score < 50:
            note += " - Low relevance to research focus."

        return note

    def analyze_paper(
        self,
        paper: ScoredPaper
    ) -> AnalyzedPaper:
        """
        Analyze a single paper based on its quadrant category.

        Args:
            paper: ScoredPaper to analyze

        Returns:
            AnalyzedPaper with analysis results
        """
        category = paper.quadrant_category

        logger.info(
            f"Processing paper [{paper.paper_id}] "
            f"in category: {category.value}"
        )

        # Route to appropriate analysis method
        if category == QuadrantCategory.REJECTED:
            # No LLM call for rejected papers (save cost)
            analysis_result = {
                "analysis_summary": None,
                "extracted_methods": [],
                "impact_briefing": None,
                "rejection_note": self._generate_rejection_note(paper)
            }
        elif category in (QuadrantCategory.CROWN_JEWEL, QuadrantCategory.CORE_TRACK):
            analysis_result = self._analyze_core_paper(paper)
        elif category == QuadrantCategory.IMPACT_TRACK:
            analysis_result = self._analyze_impact_paper(paper)
        else:
            raise ValueError(f"Unknown quadrant category: {category}")

        # Create AnalyzedPaper
        analyzed = AnalyzedPaper(
            # Inherited from ScoredPaper
            paper_id=paper.paper_id,
            title=paper.title,
            abstract=paper.abstract,
            authors=paper.authors,
            venue=paper.venue,
            publication_date=paper.publication_date,
            url=paper.url,
            citation_count=paper.citation_count,
            influential_citation_count=paper.influential_citation_count,
            has_github_link=paper.has_github_link,
            core_score=paper.core_score,
            impact_score=paper.impact_score,
            quadrant_category=paper.quadrant_category,
            routing_reason=paper.routing_reason,
            # Analysis results
            analysis_summary=analysis_result["analysis_summary"],
            extracted_methods=analysis_result["extracted_methods"],
            impact_briefing=analysis_result["impact_briefing"],
            rejection_note=analysis_result["rejection_note"]
        )

        logger.debug(f"Analysis complete for [{paper.paper_id}]")
        return analyzed

    def analyze_batch(
        self,
        papers: List[ScoredPaper],
        progress_callback: Optional[callable] = None
    ) -> List[AnalyzedPaper]:
        """
        Analyze a batch of scored papers.

        Args:
            papers: List of ScoredPaper to analyze
            progress_callback: Optional callback(current, total, paper_id)

        Returns:
            List of AnalyzedPaper
        """
        logger.info(f"Starting batch analysis of {len(papers)} papers")

        results: List[AnalyzedPaper] = []

        # Count by category
        categories = {}
        for p in papers:
            cat = p.quadrant_category.value
            categories[cat] = categories.get(cat, 0) + 1

        logger.info(f"Paper distribution: {categories}")

        for i, paper in enumerate(papers):
            try:
                analyzed = self.analyze_paper(paper)
                results.append(analyzed)

                if progress_callback:
                    progress_callback(i + 1, len(papers), paper.paper_id)

            except Exception as e:
                logger.error(f"Failed to analyze paper [{paper.paper_id}]: {e}")
                # Create minimal AnalyzedPaper with error note
                analyzed = AnalyzedPaper(
                    paper_id=paper.paper_id,
                    title=paper.title,
                    abstract=paper.abstract,
                    authors=paper.authors,
                    venue=paper.venue,
                    publication_date=paper.publication_date,
                    url=paper.url,
                    citation_count=paper.citation_count,
                    influential_citation_count=paper.influential_citation_count,
                    has_github_link=paper.has_github_link,
                    core_score=paper.core_score,
                    impact_score=paper.impact_score,
                    quadrant_category=paper.quadrant_category,
                    routing_reason=paper.routing_reason,
                    analysis_summary=None,
                    extracted_methods=[],
                    impact_briefing=None,
                    rejection_note=f"Analysis error: {str(e)}"
                )
                results.append(analyzed)

        logger.info(f"Batch analysis complete: {len(results)} papers processed")
        return results

    def save_checkpoint(
        self,
        papers: List[AnalyzedPaper],
        output_date: Optional[date] = None,
        output_dir: Optional[Path] = None
    ) -> Path:
        """
        Save analyzed papers to JSON file (checkpoint mechanism).

        Args:
            papers: List of AnalyzedPaper
            output_date: Date for filename (default: today)
            output_dir: Output directory (default: data/analysis_cache)

        Returns:
            Path to saved file
        """
        if output_date is None:
            output_date = date.today()

        if output_dir is None:
            project_root = Path(__file__).parent.parent.parent
            output_dir = project_root / "data" / "analysis_cache"

        output_dir.mkdir(parents=True, exist_ok=True)
        # Add time suffix to avoid overwriting if run multiple times per day
        now = datetime.now()
        output_file = output_dir / f"{output_date.isoformat()}_{now.strftime('%H-%M')}.json"

        # Serialize papers
        papers_json = [p.model_dump() for p in papers]

        # Custom serializer for date objects
        def json_serializer(obj):
            if isinstance(obj, date):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(papers_json, f, ensure_ascii=False, indent=2, default=json_serializer)

        logger.info(f"Analysis checkpoint saved to: {output_file}")
        return output_file

    @classmethod
    def load_checkpoint(
        cls,
        input_path: Path
    ) -> List[AnalyzedPaper]:
        """
        Load analyzed papers from JSON checkpoint file.

        Enables resumption from a previous run.

        Args:
            input_path: Path to the checkpoint file

        Returns:
            List of AnalyzedPaper objects
        """
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Convert date strings back to date objects
        for paper_data in data:
            if isinstance(paper_data.get("publication_date"), str):
                paper_data["publication_date"] = date.fromisoformat(paper_data["publication_date"])

        papers = [AnalyzedPaper(**paper_data) for paper_data in data]
        logger.info(f"Loaded {len(papers)} analyzed papers from {input_path}")
        return papers

    def run(
        self,
        papers: List[ScoredPaper],
        save_output: bool = True
    ) -> List[AnalyzedPaper]:
        """
        Execute complete analysis pipeline.

        Args:
            papers: List of ScoredPaper to analyze
            save_output: Whether to save checkpoint

        Returns:
            List of AnalyzedPaper
        """
        logger.info("=" * 60)
        logger.info("[Analysis Agent] Starting analysis pipeline")
        logger.info(f"  - Input papers: {len(papers)}")
        logger.info("=" * 60)

        # Analyze all papers
        analyzed_papers = self.analyze_batch(papers)

        # Save checkpoint
        if save_output:
            self.save_checkpoint(analyzed_papers)

        logger.info("[Analysis Agent] Analysis pipeline complete")
        return analyzed_papers


# ============================================================================
# Convenience Functions
# ============================================================================

def analyze_papers(
    papers: List[ScoredPaper],
    config: Optional[Config] = None,
    llm_client: Optional[LLMClient] = None
) -> List[AnalyzedPaper]:
    """
    Convenience function: Analyze papers.

    Args:
        papers: List of ScoredPaper
        config: Config instance
        llm_client: LLM client instance

    Returns:
        List of AnalyzedPaper
    """
    agent = AnalysisAgent(config=config, llm_client=llm_client)
    return agent.run(papers)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    # This is for testing purposes
    print("Analysis Agent module loaded successfully.")
    print("Use test_analysis.py for full testing with mock data.")
