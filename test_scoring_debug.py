#!/usr/bin/env python3
"""
Test script to debug and validate scoring adjustments.
"""

import sys
from pathlib import Path
from datetime import date, timedelta

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.filter_agent import (
    FilterAgent,
    ImpactScoreCalculator,
    TimeDecayCalculator,
    CoreScoreCalculator,
    QuadrantRouter,
    create_filter_agent,
    configure_llm,
    configure_embedding,
)
from src.config_loader import Config
from src.models import CandidatePaper


def create_mock_papers():
    """Create mock papers representing different scenarios."""

    today = date.today()

    papers = []

    # Paper 1: High-impact published paper (Nature Physics)
    papers.append(CandidatePaper(
        paper_id="mock:2024-nature-physics",
        title="Variational Quantum Eigensolver with provable quantum advantage",
        abstract="We demonstrate a variational quantum eigensolver (VQE) approach that achieves quantum advantage for quantum chemistry simulations. Our method uses a hardware-efficient ansatz and shows significant improvement over classical methods.",
        authors=["Jarrod McClean", "Maria Schuld"],
        venue="Nature Physics",
        publication_date=today - timedelta(days=180),  # 6 months old
        url="https://example.com/paper1",
        citation_count=45,
        influential_citation_count=12,
        has_github_link=True,
    ))

    # Paper 2: QML paper on arXiv (recent, no citations)
    papers.append(CandidatePaper(
        paper_id="mock:2026-arxiv-qaoa",
        title="Barren Plateaufree Quantum Approximate Optimization Algorithm",
        abstract="We propose a novel QAOA ansatz design that avoids barren plateaus while maintaining expressibility. Results show improved performance on Max-Cut problems for quantum hardware.",
        authors=["Edward Farhi", "Jeffrey Goldstone"],
        venue="arXiv",
        publication_date=today - timedelta(days=7),  # 1 week old
        url="https://arxiv.org/abs/2603.xxxxx",
        citation_count=0,
        influential_citation_count=0,
        has_github_link=False,
    ))

    # Paper 3: Published in PRX Quantum
    papers.append(CandidatePaper(
        paper_id="mock:2025-prx-quantum",
        title="Quantum Neural Networks for Supervised Learning",
        abstract="We provide a comprehensive analysis of quantum neural networks (QNN) for supervised learning tasks. We prove bounds on the expressibility and training complexity for parameterized quantum circuits.",
        authors=["Maria Schuld", "Francesco Tacchino"],
        venue="PRX Quantum",
        publication_date=today - timedelta(days=120),  # 4 months old
        url="https://example.com/paper3",
        citation_count=28,
        influential_citation_count=8,
        has_github_link=True,
    ))

    # Paper 4: Paper with citations (published in PRA)
    papers.append(CandidatePaper(
        paper_id="mock:2025-pra-quantum",
        title="Hardware-Efficient Ansatz Design for VQE on NISQ Devices",
        abstract="We study hardware-efficient ansatz designs for variational quantum eigensolver on noisy intermediate-scale quantum (NISQ) devices. Our approach reduces circuit depth while maintaining solution quality.",
        authors=["Alberto Peruzzo"],
        venue="Physical Review A",
        publication_date=today - timedelta(days=200),  # ~6 months old
        url="https://example.com/paper4",
        citation_count=15,
        influential_citation_count=3,
        has_github_link=True,
    ))

    # Paper 5: Recent arXiv paper with GitHub
    papers.append(CandidatePaper(
        paper_id="mock:2026-arxiv-variational",
        title="Variational Quantum Algorithms for Combinatorial Optimization",
        abstract="We present variational quantum algorithms for solving combinatorial optimization problems using parameterized quantum circuits. Our method demonstrates improvement over classical approaches on synthetic benchmark problems.",
        authors=["Jules Tilly", "Alberto Peruzzo"],
        venue="arXiv",
        publication_date=today - timedelta(days=14),  # 2 weeks old
        url="https://arxiv.org/abs/2603.yyyyy",
        citation_count=3,
        influential_citation_count=0,
        has_github_link=True,
    ))

    # Paper 6: Paper from non-VIP authors on arXiv
    papers.append(CandidatePaper(
        paper_id="mock:2026-arxiv-generic",
        title="A New Quantum Circuit Design for Machine Learning",
        abstract="We propose a new quantum circuit architecture for machine learning applications. The design uses parameterized gates and shows promising results on benchmark datasets.",
        authors=["John Doe", "Jane Smith"],
        venue="arXiv",
        publication_date=today - timedelta(days=3),  # 3 days old
        url="https://arxiv.org/abs/2603.zzzzz",
        citation_count=0,
        influential_citation_count=0,
        has_github_link=False,
    ))

    return papers


def test_scoring():
    """Test the scoring system with mock papers."""

    # Load config
    config = Config.get_instance()

    # Create mock papers
    papers = create_mock_papers()

    print("=" * 80)
    print("SCORING TEST RESULTS")
    print("=" * 80)

    # Test each paper
    for paper in papers:
        age_days = (date.today() - paper.publication_date).days

        print(f"\n{'='*60}")
        print(f"Paper: {paper.title[:50]}...")
        print(f"ID: {paper.paper_id}")
        print(f"Age: {age_days} days")
        print(f"Venue: {paper.venue}")
        print(f"Authors: {', '.join(paper.authors[:2])}...")
        print(f"Citations: {paper.citation_count}")
        print(f"GitHub: {paper.has_github_link}")
        print("-" * 60)

        # Create time decay calculator for this specific paper
        time_decay = TimeDecayCalculator(config)
        weights = time_decay.get_impact_weights(age_days)
        print(f"Impact Weights (age={age_days}): {weights}")

        # Calculate individual components
        impact_calc = ImpactScoreCalculator(config)

        venue_score = impact_calc._compute_venue_score(paper.venue)
        author_score = impact_calc._compute_author_score(paper.authors)
        github_score = impact_calc._compute_github_score(paper.has_github_link)
        velocity = time_decay.compute_citation_velocity(paper.citation_count, age_days)
        velocity_score = impact_calc._compute_citation_velocity_score(
            paper.citation_count, age_days
        )

        print(f"Venue Score: {venue_score}")
        print(f"Author Score: {author_score}")
        print(f"GitHub Score: {github_score}")
        print(f"Citation Velocity: {velocity:.2f} citations/month -> Score: {velocity_score}")

        # Calculate impact score manually
        impact_score = (
            weights["venue"] * venue_score +
            weights["author"] * author_score +
            weights["github"] * github_score +
            weights["citation_velocity"] * velocity_score
        )
        print(f"Calculated Impact Score: {impact_score:.2f}")

        # Core score
        core_calc = CoreScoreCalculator(config)
        keyword_score = core_calc._compute_keyword_score(paper.title, paper.abstract)
        print(f"Keyword Score: {keyword_score:.2f}")

        # Router
        router = QuadrantRouter(config)
        category = router.route(keyword_score, impact_score)
        print(f"Category: {category.value}")

    print("\n" + "=" * 80)
    print("CONFIG VALUES:")
    print(f"core_threshold: {config.core_threshold}")
    print(f"impact_threshold: {config.impact_threshold}")
    print(f"new_paper_threshold_days: {config.new_paper_threshold_days}")
    print(f"old_paper_threshold_days: {config.old_paper_threshold_days}")
    print("=" * 80)


if __name__ == "__main__":
    test_scoring()
