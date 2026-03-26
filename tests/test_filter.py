"""
Test Script for Filter Agent
============================

This script creates mock paper data and runs the Filter Agent
to verify the dual-axis scoring and quadrant routing logic works correctly.

Usage:
    python test_filter.py              # Run with mock data (no LLM)
    python test_filter.py --real       # Run with real LLM/Embedding services
    python test_filter.py --checkpoint # Load from checkpoint file
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config_loader import Config
from src.models import CandidatePaper, QuadrantCategory
from src.agents.filter_agent import (
    FilterAgent,
    create_filter_agent,
    configure_llm,
    configure_embedding,
    OpenAIEmbeddingService,
    OpenAILLMScoringService,
)


def create_mock_papers() -> list[CandidatePaper]:
    """
    Create mock papers for testing.

    Returns:
        List of mock CandidatePaper objects
    """
    today = date.today()

    return [
        # Paper 1: Should be Crown Jewel (High Core + High Impact)
        # - Matches QML keywords -> High Core
        # - VIP author (Maria Schuld) + NeurIPS venue -> High Impact
        CandidatePaper(
            paper_id="arXiv:2401.00001",
            title="Barren Plateaus in Variational Quantum Circuits: A Comprehensive Study",
            abstract=(
                "We investigate barren plateaus in parameterized quantum circuits (PQCs) "
                "for quantum machine learning. Our analysis provides tight bounds on the "
                "variance of gradients for variational quantum algorithms (VQAs). "
                "We propose a novel quantum neural network architecture that avoids "
                "barren plateaus through local cost functions."
            ),
            authors=["Maria Schuld", "John Doe", "Jane Smith"],
            venue="NeurIPS",
            publication_date=today - timedelta(days=30),  # New paper
            url="https://arxiv.org/abs/2401.00001",
            citation_count=5,
            influential_citation_count=2,
            has_github_link=True
        ),

        # Paper 2: Should be Core Track (High Core + Low Impact)
        # - Matches QML keywords -> High Core
        # - Unknown venue + no VIP authors -> Low Impact
        CandidatePaper(
            paper_id="arXiv:2401.00002",
            title="Efficient Parameterized Quantum Circuit for Quantum Machine Learning",
            abstract=(
                "We propose a new ansatz for variational quantum eigensolver (VQE) "
                "that improves convergence. The quantum neural network architecture "
                "uses hardware-efficient gates. We demonstrate on small-scale "
                "quantum machine learning tasks."
            ),
            authors=["Anonymous Researcher", "Another Author"],
            venue="arXiv",
            publication_date=today - timedelta(days=60),  # New paper
            url="https://arxiv.org/abs/2401.00002",
            citation_count=0,
            influential_citation_count=0,
            has_github_link=False
        ),

        # Paper 3: Should be Impact Track (Low Core + High Impact)
        # - General physics (not QML specific) -> Low Core
        # - Nature + VIP author (John Preskill) -> High Impact
        CandidatePaper(
            paper_id="arXiv:2401.00003",
            title="Quantum Error Correction Breakthrough in Superconducting Qubits",
            abstract=(
                "We demonstrate a new quantum error correction scheme with "
                "unprecedented threshold. Our approach uses surface codes and "
                "achieves 99.9% fidelity in superconducting qubit systems. "
                "This breakthrough enables fault-tolerant quantum computing."
            ),
            authors=["John Preskill", "Google Quantum AI Team"],
            venue="Nature",
            publication_date=today - timedelta(days=45),  # New paper
            url="https://arxiv.org/abs/2401.00003",
            citation_count=50,
            influential_citation_count=20,
            has_github_link=True
        ),

        # Paper 4: Should be Rejected (Low Core + Low Impact)
        # - Classical ML (excluded) -> Low Core
        # - Unknown venue + no VIP -> Low Impact
        CandidatePaper(
            paper_id="arXiv:2401.00004",
            title="Deep Learning for Image Classification Using Convolutional Networks",
            abstract=(
                "We present a purely classical machine learning approach "
                "for image classification. Our convolutional neural network "
                "achieves state-of-the-art results on ImageNet. This work "
                "has no connection to quantum computing."
            ),
            authors=["Classical ML Researcher", "Another Classical Author"],
            venue="ICML",
            publication_date=today - timedelta(days=120),  # Older paper
            url="https://arxiv.org/abs/2401.00004",
            citation_count=10,
            influential_citation_count=3,
            has_github_link=True
        ),

        # Paper 5: Old paper with high citations (test time-decay)
        CandidatePaper(
            paper_id="arXiv:2201.00005",
            title="Quantum Machine Learning: A Classical Perspective",
            abstract=(
                "We analyze quantum machine learning algorithms and their "
                "quantum neural network implementations. This variational "
                "quantum algorithm study shows advantages in certain regimes."
            ),
            authors=["Some Researcher"],
            venue="Physical Review Letters",
            publication_date=today - timedelta(days=500),  # Old paper > 1 year
            url="https://arxiv.org/abs/2201.00005",
            citation_count=200,  # High citations
            influential_citation_count=80,
            has_github_link=False
        ),
    ]


def create_real_paper() -> List[CandidatePaper]:
    """Load real papers from data/raw_papers JSON file."""
    project_root = Path(__file__).parent
    data_dir = project_root / "data" / "raw_papers"

    # Find the most recent JSON file
    # json_files = sorted(data_dir.glob("*.json"), reverse=True)
    # if not json_files:
    #     raise FileNotFoundError("No raw papers JSON file found in data/raw_papers/")

    # latest_file = json_files[0]

    json_file = data_dir / "2026-03-11.json"
    print(f"    Loading from: {json_file}")

    with open(json_file, "r", encoding="utf-8") as f:
        raw_papers = json.load(f)

    # Convert date strings to date objects
    for paper in raw_papers:
        if isinstance(paper.get("publication_date"), str):
            paper["publication_date"] = date.fromisoformat(paper["publication_date"])

    return [CandidatePaper(**paper) for paper in raw_papers]


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test Filter Agent")
    parser.add_argument(
        "--real",
        action="store_true",
        help="Use real LLM/Embedding services (requires API keys)"
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Load scored papers from checkpoint file"
    )
    parser.add_argument(
        "--llm-api-key",
        type=str,
        default="",
        help="LLM API key (or set LLM_API_KEY env var)"
    )
    parser.add_argument(
        "--embedding-api-key",
        type=str,
        default="",
        help="Embedding API key (or set EMBEDDING_API_KEY env var)"
    )
    parser.add_argument(
        "--llm-url",
        type=str,
        default="https://api.openai.com/v1",
        help="LLM API URL"
    )
    parser.add_argument(
        "--embedding-url",
        type=str,
        default="https://api.openai.com/v1",
        help="Embedding API URL"
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default="gpt-3.5-turbo",
        help="LLM model name"
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default="text-embedding-ada-002",
        help="Embedding model name"
    )
    return parser.parse_args()


def load_llm_config() -> dict:
    """Load LLM configuration from llm_key.json."""
    project_root = Path(__file__).parent
    config_path = project_root / "llm_key.json"

    with open(config_path, "r", encoding="utf-8") as f:
        configs = json.load(f)

    # Return the first config entry
    if configs and len(configs) > 0:
        return configs[0]
    return {}


def main() -> None:
    """Run the filter agent test."""

    # Load LLM config from llm_key.json
    llm_config = load_llm_config()

    # Build args using llm_key.json config
    # LLM uses MiniMax, Embedding uses DashScope (separate tokens)
    args = argparse.Namespace(
        real=True,
        checkpoint=None,
        llm_api_key=llm_config.get("api_token", ""),  # MiniMax token
        llm_url=llm_config.get("url", ""),  # MiniMax URL
        llm_model=llm_config.get("model", ""),  # MiniMax model
        embedding_api_key=llm_config.get("embedding_token", ""),  # DashScope token
        embedding_url=llm_config.get("embedding_url", ""),  # DashScope URL
        embedding_model=llm_config.get("embedding_model", ""),  # Qwen embedding model
    )

    # print(args)

    # exit()

    print("=" * 60)
    print("Filter Agent Test - Dual-Axis Scoring & Quadrant Routing")
    print("=" * 60)

    # Load configuration
    print("\n[1] Loading configuration...")
    config = Config.get_instance()
    print(f"    Profile: {config.profile_name}")
    print(f"    Discipline: {config.target_discipline}")
    print(f"    Core Threshold: {config.core_threshold}")
    print(f"    Impact Threshold: {config.impact_threshold}")

    # Load papers
    print("\n[2] Loading papers...")

    # papers = create_mock_papers()

    try:
        papers = create_real_paper()
        print(f"    Loaded {len(papers)} real papers from data/raw_papers/")
    except FileNotFoundError:
        papers = create_mock_papers()
        print(f"    Created {len(papers)} mock papers (no real data found)")

    # Initialize Filter Agent
    print("\n[3] Initializing Filter Agent...")

    if args.real:
        # Get API keys from args
        llm_key = args.llm_api_key
        embedding_key = args.embedding_api_key

        if llm_key or embedding_key:
            agent = create_filter_agent(
                llm_api_key=llm_key,
                llm_api_url=args.llm_url,
                llm_model=args.llm_model,
                embedding_api_key=embedding_key,
                embedding_api_url=args.embedding_url,
                embedding_model=args.embedding_model,
                config=config
            )
            print(f"    Mode: Real LLM + Embedding services")
            print(f"    LLM URL: {args.llm_url}")
            print(f"    LLM Model: {args.llm_model}")
            print(f"    Embedding URL: {args.embedding_url}")
            print(f"    Embedding Model: {args.embedding_model}")
        else:
            agent = FilterAgent(config=config)
            print("    Mode: Mock (no API keys provided)")
    else:
        agent = FilterAgent(config=config)
        print("    Mode: Mock (use --real for LLM/Embedding)")

    # Score papers
    print("\n[4] Scoring papers...")
    use_llm = args.real and (args.llm_api_key or bool(__import__('os').environ.get("LLM_API_KEY")))
    scored_papers = agent.score_papers(papers, use_llm=use_llm)

    # Print results
    print("\n[5] Results:")
    print("-" * 60)

    for paper in scored_papers[:10]:  # Show first 10
        print(f"\n  Paper: {paper.paper_id}")
        print(f"  Title: {paper.title[:60]}...")
        print(f"  Core Score: {paper.core_score:.2f}")
        print(f"  Impact Score: {paper.impact_score:.2f}")
        print(f"  Category: {paper.quadrant_category.value}")
        print(f"  Reason: {paper.routing_reason}")

    if len(scored_papers) > 10:
        print(f"\n  ... and {len(scored_papers) - 10} more papers")

    # Summary by category
    print("\n" + "=" * 60)
    print("Summary by Category:")
    print("-" * 60)

    for category in QuadrantCategory:
        papers_in_category = agent.get_papers_by_category(scored_papers, category)
        print(f"  {category.value}: {len(papers_in_category)} paper(s)")
        for p in papers_in_category[:3]:  # Show first 3 per category
            print(f"    - {p.paper_id}: {p.title[:50]}...")
        if len(papers_in_category) > 3:
            print(f"    ... and {len(papers_in_category) - 3} more")

    # Save checkpoint
    print("\n[6] Saving checkpoint...")
    checkpoint_path = agent.save_checkpoint(scored_papers)
    print(f"    Saved to: {checkpoint_path}")

    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
