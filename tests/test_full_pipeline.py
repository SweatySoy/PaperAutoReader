"""
End-to-End Full Pipeline Test (Search → Filter → Analysis)
==========================================================

This script runs the complete PaperAutoReader pipeline without any mocks:
1. Search Agent: Fetch papers from arXiv for a specific date
2. Filter Agent: Score papers with real LLM + Embedding
3. Analysis Agent: Analyze papers with real LLM

Output: AnalyzedPaper list saved to data/analysis_cache/

Usage:
    python tests/test_full_pipeline.py [date] [--max-papers N]

Example:
    python tests/test_full_pipeline.py 2024-01-15 --max-papers 5
"""

import json
import logging
import sys
import argparse
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.search_agent import SearchAgent
from src.agents.analysis_agent import AnalysisAgent, LLMClient
from src.config_loader import Config
from src.models import CandidatePaper, ScoredPaper, AnalyzedPaper, QuadrantCategory
from src.agents.filter_agent import (
    FilterAgent,
    create_filter_agent,
    configure_llm,
    configure_embedding,
)


# ============================================================================
# Progress Bar (Simple Text-Based)
# ============================================================================

class SimpleProgressBar:
    """Simple text-based progress bar."""

    def __init__(self, total: int, prefix: str = "Progress", width: int = 40):
        self.total = total
        self.prefix = prefix
        self.width = width
        self.current = 0
        self.start_time = time.time()

    def update(self, current: int = None, suffix: str = ""):
        """Update progress bar."""
        if current is not None:
            self.current = current
        else:
            self.current += 1

        percent = self.current / self.total if self.total > 0 else 0
        filled = int(self.width * percent)
        bar = "█" * filled + "░" * (self.width - filled)
        elapsed = time.time() - self.start_time

        # Estimate remaining time
        if self.current > 0:
            eta = elapsed / self.current * (self.total - self.current)
            eta_str = f"ETA: {eta:.0f}s"
        else:
            eta_str = "ETA: --s"

        print(f"\r{self.prefix}: |{bar}| {self.current}/{self.total} [{percent*100:.0f}%] {eta_str} {suffix}", end="", flush=True)

        if self.current >= self.total:
            print()  # New line when complete

    def set_suffix(self, suffix: str):
        """Update the suffix text."""
        pass  # Will be shown on next update


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging() -> logging.Logger:
    """Configure logging for the pipeline."""
    logger = logging.getLogger("FullPipeline")
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
    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"system_{date.today().isoformat()}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter("%(asctime)s - [%(name)s] %(levelname)s: %(message)s")
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()


# ============================================================================
# Main Pipeline Functions
# ============================================================================

def load_api_config() -> dict:
    """Load API configuration from llm_key.json."""
    config_path = project_root / "llm_key.json"
    with open(config_path, "r", encoding="utf-8") as f:
        configs = json.load(f)
    return configs[0] if configs else {}


def step1_search(start_date: str, end_date: str, max_papers: int) -> List[CandidatePaper]:
    """
    Step 1: Search Agent - Fetch papers from arXiv.

    Args:
        start_date: Start date string in YYYY-MM-DD format
        end_date: End date string in YYYY-MM-DD format
        max_papers: Maximum number of papers to fetch per day

    Returns:
        List of CandidatePaper objects
    """
    print("\n" + "=" * 60)
    print("[STEP 1] Search Agent - Fetching papers from arXiv")
    print("=" * 60)
    print(f"Date range: {start_date} to {end_date}")
    print(f"Max papers per day: {max_papers}")

    logger.info(f"[STEP 1] Date range: {start_date} to {end_date}, max/day: {max_papers}")

    search_agent = SearchAgent()

    # Fetch papers for the date range
    papers = search_agent.run(
        date_range=(start_date, end_date),
        max_results=max_papers,
        use_field_filter=True,
        save_output=True
    )

    if not papers:
        logger.warning("No papers fetched from arXiv!")
        print("[WARNING] No papers fetched!")
        return []

    print(f"[OK] Fetched {len(papers)} raw papers")
    logger.info(f"[STEP 1] Fetched {len(papers)} papers")

    # Convert dict to CandidatePaper objects
    candidate_papers = []
    for p in papers:
        try:
            if isinstance(p.get("publication_date"), str):
                p["publication_date"] = date.fromisoformat(p["publication_date"])
            candidate_papers.append(CandidatePaper(**p))
        except Exception as e:
            logger.warning(f"Failed to parse paper {p.get('paper_id')}: {e}")

    print(f"[OK] Converted {len(candidate_papers)} CandidatePaper objects")
    return candidate_papers


def step2_filter(candidate_papers: List[CandidatePaper], api_config: dict) -> List[ScoredPaper]:
    """
    Step 2: Filter Agent - Score papers with LLM + Embedding.

    Args:
        candidate_papers: List of CandidatePaper objects
        api_config: API configuration dictionary

    Returns:
        List of ScoredPaper objects
    """
    print("\n" + "=" * 60)
    print("[STEP 2] Filter Agent - Scoring papers (LLM + Embedding)")
    print("=" * 60)

    if not candidate_papers:
        logger.warning("No papers to score!")
        return []

    # Configure LLM and Embedding
    configure_llm(
        api_key=api_config.get("api_token", ""),
        api_url=api_config.get("url", ""),
        model=api_config.get("model", "")
    )
    configure_embedding(
        api_key=api_config.get("embedding_token", ""),
        api_url=api_config.get("embedding_url", ""),
        model=api_config.get("embedding_model", "")
    )

    # Create Filter Agent with real services
    config = Config.get_instance()
    filter_agent = create_filter_agent(
        llm_api_key=api_config.get("api_token", ""),
        llm_api_url=api_config.get("url", ""),
        llm_model=api_config.get("model", ""),
        embedding_api_key=api_config.get("embedding_token", ""),
        embedding_api_url=api_config.get("embedding_url", ""),
        embedding_model=api_config.get("embedding_model", ""),
        config=config
    )

    # Score all papers with progress bar
    print(f"Scoring {len(candidate_papers)} papers...")
    progress = SimpleProgressBar(len(candidate_papers), prefix="[STEP 2] Scoring", width=30)

    scored_papers = []
    for i, paper in enumerate(candidate_papers):
        try:
            scored = filter_agent.score_paper(paper, use_llm=True)
            scored_papers.append(scored)
        except Exception as e:
            logger.warning(f"Failed to score paper {paper.paper_id}: {e}")
            # Create a fallback scored paper with neutral scores
            scored = ScoredPaper(
                **paper.model_dump(),
                core_score=50.0,
                impact_score=50.0,
                quadrant_category=QuadrantCategory.REJECTED,
                routing_reason=f"Scoring failed: {str(e)[:50]}"
            )
            scored_papers.append(scored)

        progress.update(suffix=f"| {paper.title[:30]}...")

    print(f"\n[OK] Scored {len(scored_papers)} papers")
    logger.info(f"[STEP 2] Scored {len(scored_papers)} papers")

    # Show scoring summary
    categories = {}
    for p in scored_papers:
        cat = p.quadrant_category.value
        categories[cat] = categories.get(cat, 0) + 1
    print(f"Distribution: {categories}")
    logger.info(f"[STEP 2] Distribution: {categories}")

    # Save checkpoint
    checkpoint_path = filter_agent.save_checkpoint(scored_papers)
    print(f"Checkpoint saved: {checkpoint_path}")

    return scored_papers


def step3_analysis(scored_papers: List[ScoredPaper], api_config: dict) -> List[AnalyzedPaper]:
    """
    Step 3: Analysis Agent - Deep analysis with LLM.

    Args:
        scored_papers: List of ScoredPaper objects
        api_config: API configuration dictionary

    Returns:
        List of AnalyzedPaper objects
    """
    print("\n" + "=" * 60)
    print("[STEP 3] Analysis Agent - Deep analysis (LLM)")
    print("=" * 60)

    if not scored_papers:
        logger.warning("No papers to analyze!")
        return []

    # Create LLM client for analysis
    llm_client = LLMClient(
        api_key=api_config.get("api_token", ""),
        model=api_config.get("model", ""),
        base_url=api_config.get("url", "")
    )

    analysis_agent = AnalysisAgent(llm_client=llm_client)

    # Analyze papers with progress bar
    print(f"Analyzing {len(scored_papers)} papers...")
    progress = SimpleProgressBar(len(scored_papers), prefix="[STEP 3] Analyzing", width=30)

    analyzed_papers = []
    for i, paper in enumerate(scored_papers):
        try:
            analyzed = analysis_agent.analyze_paper(paper)
            analyzed_papers.append(analyzed)
        except Exception as e:
            logger.warning(f"Failed to analyze paper {paper.paper_id}: {e}")
            # Create a fallback analyzed paper
            analyzed = AnalyzedPaper(
                **paper.model_dump(),
                analysis_summary=f"[Analysis failed: {str(e)[:80]}]",
                extracted_methods=[],
                impact_briefing=None,
                rejection_note=f"Analysis error: {str(e)[:100]}"
            )
            analyzed_papers.append(analyzed)

        progress.update(suffix=f"| {paper.title[:30]}...")

    print(f"\n[OK] Analyzed {len(analyzed_papers)} papers")
    logger.info(f"[STEP 3] Analyzed {len(analyzed_papers)} papers")

    # Save analysis checkpoint
    analysis_path = analysis_agent.save_checkpoint(analyzed_papers)
    print(f"Analysis checkpoint saved: {analysis_path}")

    return analyzed_papers


def print_summary(analyzed_papers: List[AnalyzedPaper]) -> None:
    """Print analysis summary."""
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE - Summary")
    print("=" * 60)

    # Group by category
    crown_jewels = [p for p in analyzed_papers if p.quadrant_category == QuadrantCategory.CROWN_JEWEL]
    core = [p for p in analyzed_papers if p.quadrant_category == QuadrantCategory.CORE_TRACK]
    impact = [p for p in analyzed_papers if p.quadrant_category == QuadrantCategory.IMPACT_TRACK]
    rejected = [p for p in analyzed_papers if p.quadrant_category == QuadrantCategory.REJECTED]

    print(f"Total papers: {len(analyzed_papers)}")
    print(f"  👑 Crown Jewels: {len(crown_jewels)}")
    print(f"  🎯 Core Track: {len(core)}")
    print(f"  🔭 Impact Track: {len(impact)}")
    print(f"  🗑️  Rejected: {len(rejected)}")

    logger.info(f"[SUMMARY] Total: {len(analyzed_papers)}, Crown: {len(crown_jewels)}, Core: {len(core)}, Impact: {len(impact)}, Rejected: {len(rejected)}")

    # Print Crown Jewels details
    if crown_jewels:
        print("\n--- Crown Jewels (Must Read) ---")
        for p in crown_jewels:
            print(f"  [{p.paper_id}] {p.title[:60]}...")
            if p.analysis_summary and not p.analysis_summary.startswith("["):
                print(f"    → {p.analysis_summary[:100]}...")

    # Print Impact details
    if impact:
        print("\n--- Impact Track ---")
        for p in impact:
            print(f"  [{p.paper_id}] {p.title[:60]}...")
            if p.impact_briefing and not p.impact_briefing.startswith("["):
                print(f"    → {p.impact_briefing[:80]}...")


def run_pipeline(start_date: str, end_date: str, max_papers: int = 20) -> List[AnalyzedPaper]:
    """
    Run the full pipeline for a given date range.

    Args:
        start_date: Start date string in YYYY-MM-DD format
        end_date: End date string in YYYY-MM-DD format
        max_papers: Maximum number of papers to process per day

    Returns:
        List of AnalyzedPaper objects
    """
    date_range_desc = f"{start_date} to {end_date}" if start_date != end_date else start_date
    print("\n" + "=" * 70)
    print("PaperAutoReader Full Pipeline")
    print(f"Date Range: {date_range_desc} | Max Papers/day: {max_papers}")
    print("=" * 70)

    # Load API config
    api_config = load_api_config()
    print(f"LLM: {api_config.get('model')} @ {api_config.get('url')}")
    print(f"Embedding: {api_config.get('embedding_model')} @ {api_config.get('embedding_url')}")

    logger.info(f"[PIPELINE] Starting - date range: {date_range_desc}, max/day: {max_papers}")
    logger.info(f"[PIPELINE] LLM: {api_config.get('model')}, Embedding: {api_config.get('embedding_model')}")

    # Step 1: Search
    candidate_papers = step1_search(start_date, end_date, max_papers)
    if not candidate_papers:
        logger.error("Pipeline failed at Step 1 (Search)")
        print("[ERROR] No papers fetched, exiting.")
        sys.exit(1)

    # Step 2: Filter
    scored_papers = step2_filter(candidate_papers, api_config)
    if not scored_papers:
        logger.error("Pipeline failed at Step 2 (Filter)")
        print("[ERROR] No papers scored, exiting.")
        sys.exit(1)

    # Step 3: Analysis
    analyzed_papers = step3_analysis(scored_papers, api_config)
    if not analyzed_papers:
        logger.error("Pipeline failed at Step 3 (Analysis)")
        print("[ERROR] No papers analyzed, exiting.")
        sys.exit(1)

    # Print summary
    print_summary(analyzed_papers)

    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE!")
    print("=" * 70)

    return analyzed_papers


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Full Pipeline Test (Search → Filter → Analysis)")
    parser.add_argument(
        "start_date",
        nargs="?",
        default=None,
        help="Start date (YYYY-MM-DD). Defaults to yesterday."
    )
    parser.add_argument(
        "end_date",
        nargs="?",
        default=None,
        help="End date (YYYY-MM-DD). If provided along with start_date, fetches date range."
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=10,
        help="Maximum papers to process per day (default: 10)"
    )
    args = parser.parse_args()

    # Determine date range
    if args.start_date:
        start_date = args.start_date
        if args.end_date:
            end_date = args.end_date
            date_desc = f"{start_date} to {end_date}"
        else:
            end_date = start_date
            date_desc = start_date
    else:
        yesterday = date.today() - timedelta(days=1)
        start_date = yesterday.isoformat()
        end_date = start_date
        date_desc = start_date

    # Validate date format
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        print(f"Error: Invalid date format. Use YYYY-MM-DD. Details: {e}")
        sys.exit(1)

    # Validate range
    if start_date > end_date:
        print(f"Error: Start date ({start_date}) must be before or equal to end date ({end_date}).")
        sys.exit(1)

    print(f"\n{'=' * 70}")
    print(f"PaperAutoReader - Full Pipeline Test")
    print(f"Date Range: {date_desc}")
    print(f"Max Papers per day: {args.max_papers}")
    print(f"{'=' * 70}\n")

    try:
        start_time = time.time()
        analyzed_papers = run_pipeline(start_date, end_date, args.max_papers)
        elapsed = time.time() - start_time

        print(f"\n{'=' * 70}")
        print(f"SUCCESS - {len(analyzed_papers)} papers analyzed in {elapsed:.1f}s")
        print(f"{'=' * 70}")
        sys.exit(0)
    except KeyboardInterrupt:
        print(f"\n\n[INTERRUPTED] Pipeline stopped by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n{'=' * 70}")
        print(f"ERROR - Pipeline failed: {e}")
        print(f"{'=' * 70}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
