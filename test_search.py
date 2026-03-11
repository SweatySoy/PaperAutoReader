# -*- coding: utf-8 -*-
"""
test_search.py - Search Agent Test Script
==========================================

Test arXiv API and Semantic Scholar API connectivity.
Only fetches a few papers (2) for validation.

Usage:
    python test_search.py
"""

import sys
import json
from datetime import date, datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ============================================================================
# Mock Data Model (simulates src.models.CandidatePaper)
# Since models.py is not yet completed by another Agent, provide temporary Mock
# ============================================================================
@dataclass
class MockCandidatePaper:
    """
    Mock CandidatePaper data model.
    Strictly follows Data_Schemas_Contract.md definition.
    """
    paper_id: str
    title: str
    abstract: str
    authors: List[str]
    venue: str
    publication_date: date
    url: str
    citation_count: int = 0
    influential_citation_count: int = 0
    has_github_link: bool = False

    def to_dict(self) -> dict:
        """Convert to dict (for JSON serialization)."""
        result = asdict(self)
        result["publication_date"] = self.publication_date.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "MockCandidatePaper":
        """Create instance from dict."""
        if isinstance(data.get("publication_date"), str):
            data["publication_date"] = date.fromisoformat(data["publication_date"])
        return cls(**data)

# ============================================================================
# Mock Config Loader (simulates src.config_loader.config)
# ============================================================================
class MockConfig:
    """Mock config object."""

    def __init__(self):
        self.keywords_scoring = {
            "must_have": ["quantum machine learning", "variational quantum algorithm"],
            "highly_relevant": ["barren plateau", "parameterized quantum circuit", "VQA"],
            "relevant": ["error mitigation", "tensor network"],
            "exclude": ["string theory", "fluid dynamics"]
        }

        self.impact_entities = {
            "tier_1_venues": ["Nature", "Science", "PRL", "NeurIPS", "ICLR"],
            "tier_2_venues": ["Quantum", "Physical Review A", "ICML"],
            "tier_1_institutions": ["MIT", "Caltech", "IBM Quantum", "Google Quantum AI"],
            "vip_authors": ["Maria Schuld", "John Preskill", "Seth Lloyd"]
        }

# Global config instance
config = MockConfig()

# ============================================================================
# Inject Mock into search_agent module
# ============================================================================
import src.agents.search_agent as search_module

try:
    from src.models import CandidatePaper
except ImportError:
    search_module.CandidatePaper = MockCandidatePaper
    print("[Test] Using MockCandidatePaper (src.models not found)")

try:
    from src.config_loader import config as real_config
except ImportError:
    search_module.config = config
    print("[Test] Using MockConfig (src.config_loader not found)")

# ============================================================================
# Test Functions
# ============================================================================
def test_arxiv_connection():
    """Test arXiv API connection."""
    print("\n" + "=" * 60)
    print("TEST 1: arXiv API Connection Test")
    print("=" * 60)

    import arxiv

    try:
        search = arxiv.Search(
            query="all:quantum machine learning",
            max_results=2,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )

        papers = list(search.results())
        print(f"[OK] Connected to arXiv, got {len(papers)} papers")

        for i, paper in enumerate(papers, 1):
            print(f"\n  Paper {i}:")
            print(f"    Title: {paper.title[:80]}...")
            print(f"    ID: {paper.entry_id}")
            print(f"    Published: {paper.published}")

        return True

    except Exception as e:
        print(f"[FAIL] arXiv API connection failed: {e}")
        return False

def test_semantic_scholar_connection():
    """Test Semantic Scholar API connection."""
    print("\n" + "=" * 60)
    print("TEST 2: Semantic Scholar API Connection Test")
    print("=" * 60)

    from src.agents.search_agent import SemanticScholarClient

    client = SemanticScholarClient()

    # Test with a known arXiv paper
    test_arxiv_id = "2303.01418"  # A QML paper

    try:
        result = client.get_paper_by_arxiv_id(test_arxiv_id)

        if result:
            print(f"[OK] Connected to Semantic Scholar")
            print(f"  Title: {result.get('title', 'N/A')}")
            print(f"  Citations: {result.get('citation_count', 0)}")
            print(f"  Influential citations: {result.get('influential_citation_count', 0)}")
            return True
        else:
            print("[WARN] Semantic Scholar returned empty (paper may not be indexed)")
            return True

    except Exception as e:
        print(f"[FAIL] Semantic Scholar API connection failed: {e}")
        return False

def test_github_detection():
    """Test GitHub link detection."""
    print("\n" + "=" * 60)
    print("TEST 3: GitHub Link Detection Test")
    print("=" * 60)

    from src.agents.search_agent import GitHubLinkDetector

    test_cases = [
        ("No GitHub link here", False),
        ("Code available at https://github.com/user/repo", True),
        ("See our implementation: https://www.github.com/org/project", True),
        ("Multiple links: https://github.com/a/b and https://github.com/c/d", True),
    ]

    all_passed = True
    for text, expected in test_cases:
        result = GitHubLinkDetector.detect(text)
        status = "[OK]" if result == expected else "[FAIL]"
        print(f"  {status} '{text[:40]}...' -> {result} (expected: {expected})")
        if result != expected:
            all_passed = False

    return all_passed

def test_full_search_workflow():
    """Test full search workflow (fetch only 2 papers)."""
    print("\n" + "=" * 60)
    print("TEST 4: Full Search Workflow Test (2 papers)")
    print("=" * 60)

    from src.agents.search_agent import SearchAgent

    agent = SearchAgent(
        config_source=config,
        max_papers_per_query=2
    )

    def progress(current, total, title):
        print(f"  Progress: {current}/{total} - {title[:50]}...")

    try:
        # Step 1: Fetch from arXiv
        arxiv_papers = agent.fetch_from_arxiv(days_back=30, max_results=2)

        if not arxiv_papers:
            print("[WARN] No papers fetched (network issue or no matches)")
            return False

        print(f"[OK] Got {len(arxiv_papers)} papers from arXiv")

        # Step 2: Enrich with citations
        enriched = agent.enrich_with_citations(
            arxiv_papers,
            progress_callback=progress
        )

        print(f"[OK] Citation enrichment complete")

        # Step 3: Save
        output_path = agent.save_checkpoint(enriched)
        print(f"[OK] Saved to: {output_path}")

        # Verify output file
        with open(output_path, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        print(f"[OK] Output file verified, contains {len(saved_data)} papers")

        for i, paper in enumerate(saved_data, 1):
            print(f"\n  Paper {i}:")
            print(f"    ID: {paper['paper_id']}")
            print(f"    Title: {paper['title'][:60]}...")
            print(f"    Authors: {', '.join(paper['authors'][:3])}")
            print(f"    Citations: {paper['citation_count']}")
            print(f"    Has GitHub: {paper['has_github_link']}")

        return True

    except Exception as e:
        print(f"[FAIL] Full workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_adapter():
    """Test config adapter."""
    print("\n" + "=" * 60)
    print("TEST 5: Config Adapter Test")
    print("=" * 60)

    from src.agents.search_agent import ConfigAdapter

    adapter = ConfigAdapter()

    queries = adapter.build_search_queries()
    print(f"[OK] Built {len(queries)} search queries:")
    for q in queries[:5]:
        print(f"    - {q}")

    if len(queries) > 5:
        print(f"    ... (total {len(queries)})")

    return True

# ============================================================================
# Main Test Entry
# ============================================================================
def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Search Agent Test Suite")
    print("=" * 60)

    tests = [
        ("arXiv API Connection", test_arxiv_connection),
        ("Semantic Scholar API Connection", test_semantic_scholar_connection),
        ("GitHub Link Detection", test_github_detection),
        ("Config Adapter", test_config_adapter),
        ("Full Search Workflow", test_full_search_workflow),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n[FAIL] Test '{name}' raised exception: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "[OK] PASS" if passed else "[FAIL] FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed_count}/{total_count} tests passed")

    return passed_count == total_count

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
