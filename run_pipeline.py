#!/usr/bin/env python3
"""
PaperAutoReader - Full Pipeline Execution
==========================================

This is the main entry point for the Research Radar system.
It runs the complete pipeline from paper search to final report.

Pipeline Steps:
1. Search: Fetch papers from arXiv
2. Filter: Score papers with Core + Impact metrics
3. Analysis: Deep analysis based on quadrant
4. Report: Generate Markdown report

Usage:
    python run_pipeline.py                              # Yesterday's papers
    python run_pipeline.py 2024-01-15                   # Specific date
    python run_pipeline.py 2024-01-15 2024-01-24       # Date range
    python run_pipeline.py --max-papers 50              # Limit papers per day

Author: PaperAutoReader Team
"""

import json
import logging
import sys
import time
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

# Project root
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.search_agent import SearchAgent
from src.agents.filter_agent import (
    FilterAgent,
    create_filter_agent,
    configure_llm,
    configure_embedding,
)
from src.agents.analysis_agent import AnalysisAgent, LLMClient
from src.agents.report_agent import ReportAgent
from src.config_loader import Config
from src.models import CandidatePaper, ScoredPaper, AnalyzedPaper, QuadrantCategory


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging() -> logging.Logger:
    """Configure logging for the pipeline."""
    logger = logging.getLogger("PaperAutoReader")
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
    log_dir = PROJECT_ROOT / "logs"
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
# Progress Bar
# ============================================================================

class ProgressBar:
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

        if self.current > 0:
            eta = elapsed / self.current * (self.total - self.current)
            eta_str = f"ETA: {eta:.0f}s"
        else:
            eta_str = "ETA: --s"

        print(f"\r{self.prefix}: |{bar}| {self.current}/{self.total} [{percent*100:.0f}%] {eta_str} {suffix}", end="", flush=True)

        if self.current >= self.total:
            print()


# ============================================================================
# Configuration
# ============================================================================

def load_api_config() -> dict:
    """Load API configuration from llm_key.json."""
    config_path = PROJECT_ROOT / "llm_key.json"
    with open(config_path, "r", encoding="utf-8") as f:
        configs = json.load(f)
    return configs[0] if configs else {}


# ============================================================================
# Pipeline Steps
# ============================================================================

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

    # Create Filter Agent
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

    # Score all papers
    print(f"Scoring {len(candidate_papers)} papers...")
    progress = ProgressBar(len(candidate_papers), prefix="[STEP 2] Scoring", width=30)

    scored_papers = []
    for i, paper in enumerate(candidate_papers):
        try:
            scored = filter_agent.score_paper(paper, use_llm=True)
            scored_papers.append(scored)
        except Exception as e:
            logger.warning(f"Failed to score paper {paper.paper_id}: {e}")
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

    # Analyze papers
    print(f"Analyzing {len(scored_papers)} papers...")
    progress = ProgressBar(len(scored_papers), prefix="[STEP 3] Analyzing", width=30)

    analyzed_papers = []
    for i, paper in enumerate(scored_papers):
        try:
            analyzed = analysis_agent.analyze_paper(paper)
            analyzed_papers.append(analyzed)
        except Exception as e:
            logger.warning(f"Failed to analyze paper {paper.paper_id}: {e}")
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


def step4_report(analyzed_papers: List[AnalyzedPaper], report_date: date) -> tuple:
    """
    Step 4: Report Agent - Generate final Markdown report.

    Args:
        analyzed_papers: List of AnalyzedPaper objects
        report_date: Date for the report

    Returns:
        Tuple of (FinalReport, filepath)
    """
    print("\n" + "=" * 60)
    print("[STEP 4] Report Agent - Generating Markdown report")
    print("=" * 60)

    if not analyzed_papers:
        logger.warning("No papers to generate report!")
        return None, None

    report_agent = ReportAgent()
    report, filepath = report_agent.run(
        papers=analyzed_papers,
        report_date=report_date
    )

    print(f"[OK] Report generated: {filepath}")
    logger.info(f"[STEP 4] Report saved to: {filepath}")

    return report, filepath


# ============================================================================
# Main Pipeline
# ============================================================================

def run_full_pipeline(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    max_papers: int = 10,
    output_dir: Optional[str] = None
) -> str:
    """
    Run the full PaperAutoReader pipeline.

    Args:
        date_from: Start date (YYYY-MM-DD). Defaults to yesterday.
        date_to: End date (YYYY-MM-DD). Defaults to date_from.
        max_papers: Maximum papers per day.
        output_dir: Custom output directory for reports.

    Returns:
        Path to the generated report file.
    """
    # Determine date range
    if date_from is None:
        yesterday = date.today() - timedelta(days=1)
        date_from = yesterday.isoformat()

    if date_to is None:
        date_to = date_from

    date_desc = f"{date_from} to {date_to}" if date_from != date_to else date_from

    print("\n" + "=" * 70)
    print("PaperAutoReader - Full Pipeline")
    print(f"Date Range: {date_desc} | Max Papers/day: {max_papers}")
    print("=" * 70)

    # Load API config
    api_config = load_api_config()
    print(f"LLM: {api_config.get('model')} @ {api_config.get('url')}")
    print(f"Embedding: {api_config.get('embedding_model')} @ {api_config.get('embedding_url')}")

    logger.info(f"[PIPELINE] Starting - date range: {date_desc}, max/day: {max_papers}")
    logger.info(f"[PIPELINE] LLM: {api_config.get('model')}, Embedding: {api_config.get('embedding_model')}")

    report_date = date.today()

    # Step 1: Search
    candidate_papers = step1_search(date_from, date_to, max_papers)
    if not candidate_papers:
        logger.error("Pipeline failed at Step 1 (Search)")
        raise RuntimeError("No papers fetched from arXiv")

    # Step 2: Filter
    scored_papers = step2_filter(candidate_papers, api_config)
    if not scored_papers:
        logger.error("Pipeline failed at Step 2 (Filter)")
        raise RuntimeError("No papers scored")

    # Step 3: Analysis
    analyzed_papers = step3_analysis(scored_papers, api_config)
    if not analyzed_papers:
        logger.error("Pipeline failed at Step 3 (Analysis)")
        raise RuntimeError("No papers analyzed")

    # Step 4: Report
    report, filepath = step4_report(analyzed_papers, report_date)
    if filepath is None:
        logger.error("Pipeline failed at Step 4 (Report)")
        raise RuntimeError("Failed to generate report")

    # Print summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

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

    print("\n" + "=" * 70)
    print(f"✅ PIPELINE COMPLETE - Report: {filepath}")
    print("=" * 70)

    return str(filepath)


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PaperAutoReader - Full Pipeline (Search → Filter → Analysis → Report)"
    )
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
        help="End date (YYYY-MM-DD). If provided with start_date, processes date range."
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=10,
        help="Maximum papers to process per day (default: 10)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom output directory for reports"
    )

    args = parser.parse_args()

    # Determine date range
    if args.start_date:
        start_date = args.start_date
        end_date = args.end_date if args.end_date else args.start_date
    else:
        yesterday = date.today() - timedelta(days=1)
        start_date = yesterday.isoformat()
        end_date = start_date

    # Validate date format
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        print(f"Error: Invalid date format. Use YYYY-MM-DD. Details: {e}")
        sys.exit(1)

    if start_date > end_date:
        print(f"Error: Start date ({start_date}) must be before or equal to end date ({end_date}).")
        sys.exit(1)

    try:
        start_time = time.time()
        report_path = run_full_pipeline(
            date_from=start_date,
            date_to=end_date,
            max_papers=args.max_papers,
            output_dir=args.output_dir
        )
        elapsed = time.time() - start_time
        print(f"\n✅ Success! Report generated in {elapsed:.1f}s")
        print(f"📄 {report_path}")
        sys.exit(0)
    except KeyboardInterrupt:
        print(f"\n\n[INTERRUPTED] Pipeline stopped by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n{'=' * 70}")
        print(f"❌ ERROR - Pipeline failed: {e}")
        print(f"{'=' * 70}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
