"""
Test Report Generation from Analysis Cache
=========================================

This script loads analyzed papers from data/analysis_cache/
and generates a final Markdown report using ReportAgent.

Usage:
    python tests/test_report_from_analysis.py [analysis_cache_file]
    python tests/test_report_from_analysis.py 2026-03-25
    python tests/test_report_from_analysis.py 2026-03-26
"""

import json
import sys
from datetime import date
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models import AnalyzedPaper, QuadrantCategory
from src.agents.report_agent import ReportAgent


def load_analysis_cache(date_str: str = None) -> list[AnalyzedPaper]:
    """
    Load analyzed papers from an analysis cache JSON file.

    Args:
        date_str: Date string (YYYY-MM-DD) to find the cache file.
                  If None, uses the most recent file.

    Returns:
        List of AnalyzedPaper objects
    """
    cache_dir = project_root / "data" / "analysis_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if date_str:
        # Find exact match
        cache_file = cache_dir / f"{date_str}.json"
        if not cache_file.exists():
            # Try without dashes
            cache_file = cache_dir / f"{date_str.replace('-', '')}.json"
    else:
        # Find most recent file
        json_files = sorted(cache_dir.glob("*.json"), reverse=True)
        json_files = [f for f in json_files if f.name != "mock_output.json"]
        if json_files:
            cache_file = json_files[0]
        else:
            cache_file = None

    if not cache_file or not cache_file.exists():
        print(f"[ERROR] No analysis cache file found for: {date_str or 'latest'}")
        print(f"Available files in {cache_dir}:")
        for f in sorted(cache_dir.glob("*.json")):
            print(f"  - {f.name}")
        sys.exit(1)

    print(f"[INFO] Loading from: {cache_file}")

    with open(cache_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    papers = []
    for item in data:
        # Convert date string to date object
        if isinstance(item.get("publication_date"), str):
            item["publication_date"] = date.fromisoformat(item["publication_date"])

        # Parse quadrant_category string to enum
        if isinstance(item.get("quadrant_category"), str):
            item["quadrant_category"] = QuadrantCategory(item["quadrant_category"])

        papers.append(AnalyzedPaper(**item))

    return papers


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate report from analysis cache"
    )
    parser.add_argument(
        "date",
        nargs="?",
        default=None,
        help="Date string (YYYY-MM-DD) to load specific cache file, or 'latest' for most recent"
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Custom output filename for the report"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Report Generation from Analysis Cache")
    print("=" * 60)

    # Load papers from cache
    date_str = args.date if args.date else None
    papers = load_analysis_cache(date_str)

    print(f"\n[INFO] Loaded {len(papers)} analyzed papers")

    # Count by category
    from collections import Counter
    categories = Counter(p.quadrant_category for p in papers)
    print(f"  - Crown Jewels: {categories[QuadrantCategory.CROWN_JEWEL]}")
    print(f"  - Core Track: {categories[QuadrantCategory.CORE_TRACK]}")
    print(f"  - Impact Track: {categories[QuadrantCategory.IMPACT_TRACK]}")
    print(f"  - Rejected: {categories[QuadrantCategory.REJECTED]}")

    # Initialize Report Agent
    print("\n[INFO] Initializing ReportAgent...")
    agent = ReportAgent()

    # Generate report
    print("[INFO] Generating report...")
    report_date = date.today()

    if args.output:
        filepath = agent.save_report(
            agent.generate_report(papers, report_date),
            args.output
        )
    else:
        # Use date from cache file as report date
        if papers:
            report_date = papers[0].publication_date
        filepath = agent.save_report(
            agent.generate_report(papers, report_date),
            None  # Use default filename
        )

    print(f"\n[OK] Report saved to: {filepath}")

    # Print summary
    print("\n" + "=" * 60)
    print("Report Summary")
    print("=" * 60)

    report = agent.generate_report(papers, report_date)
    print(f"Report Date: {report.report_date}")
    print(f"  👑 Crown Jewels: {len(report.crown_jewels)}")
    print(f"  🎯 Core Track: {len(report.core_papers)}")
    print(f"  🔭 Impact Track: {len(report.impact_papers)}")
    print(f"  🗑️  Rejected: {len(report.rejected_papers_log)}")
    print(f"\n[OK] Done! Report generated successfully.")


if __name__ == "__main__":
    main()
