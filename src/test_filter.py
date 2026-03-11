"""
Test Script for Filter Agent
============================

This script creates mock paper data and runs the Filter Agent
to verify the dual-axis scoring and quadrant routing logic works correctly.

Usage:
    python -m src.test_filter
"""

from datetime import date, timedelta

from src.config_loader import Config
from src.models import CandidatePaper
from src.filter_agent import FilterAgent


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


def main() -> None:
    """Run the filter agent test."""
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

    # Create mock papers
    print("\n[2] Creating mock papers...")
    papers = create_mock_papers()
    print(f"    Created {len(papers)} mock papers")

    # Initialize Filter Agent (without LLM for this test)
    print("\n[3] Initializing Filter Agent (mock mode, no LLM)...")
    agent = FilterAgent(config=config)

    # Score papers
    print("\n[4] Scoring papers...")
    scored_papers = agent.score_papers(papers, use_llm=False)

    # Print results
    print("\n[5] Results:")
    print("-" * 60)

    for paper in scored_papers:
        print(f"\n  Paper: {paper.paper_id}")
        print(f"  Title: {paper.title[:60]}...")
        print(f"  Core Score: {paper.core_score:.2f}")
        print(f"  Impact Score: {paper.impact_score:.2f}")
        print(f"  Category: {paper.quadrant_category.value}")
        print(f"  Reason: {paper.routing_reason}")

    # Summary by category
    print("\n" + "=" * 60)
    print("Summary by Category:")
    print("-" * 60)

    from src.models import QuadrantCategory
    for category in QuadrantCategory:
        papers_in_category = agent.get_papers_by_category(scored_papers, category)
        print(f"  {category.value}: {len(papers_in_category)} paper(s)")
        for p in papers_in_category:
            print(f"    - {p.paper_id}: {p.title[:50]}...")

    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
