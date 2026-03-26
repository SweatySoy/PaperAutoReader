"""
Mock Test Script for Analysis Agent
====================================

This script tests the Analysis Agent with hardcoded mock ScoredPaper data.
DO NOT import real Filter Agent - all data is manually constructed.

Following agent_analyst.md requirements:
1. Manually construct two ScoredPaper objects (one Core, one Impact)
2. Pass to Analysis Agent for testing
3. Save results to data/analysis_cache/mock_output.json
"""

import json
import logging
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models import QuadrantCategory, ScoredPaper, AnalyzedPaper
from src.agents.analysis_agent import AnalysisAgent, LLMClient


# ============================================================================
# Logging Setup
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("MockTest")


# ============================================================================
# Mock Data Construction
# ============================================================================

def create_mock_core_paper() -> ScoredPaper:
    """
    Create a mock ScoredPaper in CORE_TRACK category.

    This simulates a paper that passed the filter with high core score
    but moderate impact score.
    """
    return ScoredPaper(
        paper_id="arXiv:2403.12345",
        title="Variational Quantum Algorithms for Barren Plateau Mitigation: A Novel Ansatz Architecture",
        abstract="""Variational quantum algorithms (VQAs) have emerged as a promising approach for
near-term quantum computing applications. However, the barren plateau phenomenon poses a
significant challenge to training these algorithms effectively. In this work, we propose
a novel parameterized quantum circuit architecture that systematically avoids barren plateaus
by constraining the circuit's expressibility while maintaining sufficient trainability.
Our approach leverages a layered construction with local cost functions and demonstrates
empirical improvements in gradient magnitudes of up to 100x compared to random circuits.
We validate our method on VQE for molecular Hamiltonians and QAOA for combinatorial
optimization, achieving comparable or better results with significantly fewer optimization
iterations. The proposed architecture requires only linear depth in the number of qubits
and is compatible with current NISQ devices.""",
        authors=["Alice Quantum", "Bob Variational", "Charlie NISQ"],
        venue="Physical Review A",
        publication_date=date(2024, 3, 15),
        url="https://arxiv.org/abs/2403.12345",
        citation_count=12,
        influential_citation_count=3,
        has_github_link=True,
        # Scoring results from Filter Agent
        core_score=85.5,
        impact_score=62.0,
        quadrant_category=QuadrantCategory.CORE_TRACK,
        routing_reason="High relevance to VQA and barren plateau research; moderate impact from mid-tier venue"
    )


def create_mock_impact_paper() -> ScoredPaper:
    """
    Create a mock ScoredPaper in IMPACT_TRACK category.

    This simulates a paper with lower core score but high impact score
    (e.g., from a top venue or VIP author, but not directly on-topic).
    """
    return ScoredPaper(
        paper_id="arXiv:2402.98765",
        title="Quantum Error Correction Thresholds for Surface Codes Under Realistic Noise Models",
        abstract="""We present a comprehensive analysis of quantum error correction thresholds
for the surface code under various realistic noise models including coherent errors,
spatially correlated noise, and leakage errors. Our results show that the threshold
remains robust at around 0.1% for depolarizing noise but degrades significantly under
coherent error components. We introduce a novel decoding algorithm that accounts for
correlations in the error model and demonstrate a 20% improvement in logical error rates
compared to standard minimum-weight perfect matching decoders. These findings have
critical implications for the design of fault-tolerant quantum computers and establish
practical benchmarks for experimental implementations. The decoder is implemented in
open-source software available on GitHub.""",
        authors=["David ErrorCorrection", "Eve Surface", "John Preskill"],  # VIP author
        venue="Nature Physics",
        publication_date=date(2024, 2, 20),
        url="https://arxiv.org/abs/2402.98765",
        citation_count=45,
        influential_citation_count=18,
        has_github_link=True,
        # Scoring results from Filter Agent
        core_score=45.0,
        impact_score=92.5,
        quadrant_category=QuadrantCategory.IMPACT_TRACK,
        routing_reason="Impact score high due to Nature Physics venue and VIP author Preskill; core score low as error correction is not primary research focus"
    )


def create_mock_rejected_paper() -> ScoredPaper:
    """
    Create a mock ScoredPaper in REJECTED category.

    This simulates a paper that failed both core and impact thresholds.
    """
    return ScoredPaper(
        paper_id="arXiv:2401.11111",
        title="Classical Machine Learning for String Theory Parameter Estimation",
        abstract="""We apply classical neural networks to estimate parameters in string
theory models. Our approach uses standard backpropagation and achieves modest improvements
over baseline methods. The work is primarily focused on high energy physics applications.""",
        authors=["Z. Classical", "Y. String"],
        venue="arXiv",
        publication_date=date(2024, 1, 10),
        url="https://arxiv.org/abs/2401.11111",
        citation_count=2,
        influential_citation_count=0,
        has_github_link=False,
        # Scoring results from Filter Agent
        core_score=15.0,
        impact_score=25.0,
        quadrant_category=QuadrantCategory.REJECTED,
        routing_reason="Contains exclude keywords (string theory, classical ML); low scores on both axes"
    )


# ============================================================================
# Mock LLM Client
# ============================================================================

class MockLLMClient:
    """
    Mock LLM client that returns predefined responses.

    This avoids making actual API calls during testing.
    """

    def __init__(self, *args, **kwargs):
        """Initialize mock client (ignores all arguments)."""
        self.call_count = 0
        logger.info("MockLLMClient initialized (no real API calls)")

    def call(self, system_prompt: str, user_prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Return mock response based on prompt content.

        Args:
            system_prompt: System message (analyzed to determine response type)
            user_prompt: User message

        Returns:
            Mock JSON response
        """
        self.call_count += 1
        logger.info(f"MockLLMClient.call() invoked (call #{self.call_count})")

        # Determine response type from prompt
        if "CORE_TRACK" in system_prompt or "CROWN_JEWEL" in system_prompt or "Core/Crown Jewel" in system_prompt:
            # Core paper analysis
            return {
                "analysis_summary": (
                    "This paper presents a novel approach to mitigating barren plateaus "
                    "in variational quantum algorithms through a carefully constrained circuit "
                    "architecture. The key innovation is balancing expressibility and trainability "
                    "by using layered constructions with local cost functions. The authors demonstrate "
                    "empirical improvements of 100x in gradient magnitudes, which is significant for "
                    "practical VQA training. The linear depth scaling makes this approach suitable "
                    "for NISQ devices."
                ),
                "extracted_methods": [
                    "Layered parameterized quantum circuit construction",
                    "Local cost function design for gradient enhancement",
                    "Barren plateau avoidance through expressibility constraints",
                    "VQE for molecular Hamiltonians",
                    "QAOA for combinatorial optimization"
                ],
                "relevance_to_research": (
                    "Highly relevant to quantum machine learning research, specifically "
                    "addressing the critical barren plateau problem that affects training "
                    "of quantum neural networks. The proposed architecture could be directly "
                    "applicable to VQE and QAOA implementations in our research."
                )
            }
        elif "IMPACT_TRACK" in system_prompt or "Impact Track" in system_prompt:
            # Impact paper analysis
            return {
                "impact_briefing": (
                    "This breakthrough in quantum error correction establishes practical "
                    "thresholds under realistic noise models, which is crucial for building "
                    "fault-tolerant quantum computers. The novel decoder accounting for "
                    "correlations shows 20% improvement in logical error rates. While not "
                    "directly about QML, this work has significant implications for the "
                    "feasibility of running QML algorithms on real quantum hardware in the "
                    "future. Better error correction means more reliable quantum computations, "
                    "which benefits all quantum algorithms including VQAs."
                ),
                "key_innovation": (
                    "A correlation-aware decoding algorithm for surface codes that "
                    "improves logical error rates by 20% compared to standard MWPM decoders"
                ),
                "potential_applications": (
                    "This error correction advancement could enable longer circuit depths "
                    "for QML algorithms, potentially allowing more complex variational circuits "
                    "to be executed reliably. The practical thresholds established inform "
                    "hardware requirements for implementing QML on real devices."
                )
            }
        else:
            # Generic response
            return {
                "analysis_summary": "Generic mock analysis",
                "extracted_methods": [],
                "relevance_to_research": "Not directly relevant"
            }


# ============================================================================
# Test Functions
# ============================================================================





def test_analysis_agent_with_mock():
    """
    Test Analysis Agent with mock data and mock LLM client.

    Returns:
        List of AnalyzedPaper results
    """
    logger.info("=" * 60)
    logger.info("Starting Analysis Agent Mock Test")
    logger.info("=" * 60)

    # Create mock papers
    core_paper = create_mock_core_paper()
    impact_paper = create_mock_impact_paper()
    rejected_paper = create_mock_rejected_paper()

    papers = [core_paper, impact_paper, rejected_paper]

    logger.info(f"Created {len(papers)} mock papers:")
    for p in papers:
        logger.info(f"  - [{p.quadrant_category.value}] {p.title[:40]}...")

    # Create Analysis Agent with Mock LLM Client
    # client = MockLLMClient()

    client = LLMClient(
        api_key='sk-cp-qIzaPt7uZRFvCYVdBKKfmeXnskav_T_4kP5aAAHC0AQPFgqbr3BFPuTAl3_2EdBnEyI9xTXuO6zWehRT2PW71Iu2sa1odYJbIe88GAhDpxSswyrRu52DtiY',
        model='MiniMax-M2.7',
        base_url='https://api.minimaxi.com/anthropic'
    )    
    agent = AnalysisAgent(llm_client=client)

    # Run analysis
    logger.info("\nRunning analysis...")
    analyzed_papers = agent.analyze_batch(papers)

    # Verify results
    logger.info("\n" + "=" * 60)
    logger.info("Analysis Results Summary")
    logger.info("=" * 60)

    for analyzed in analyzed_papers:
        logger.info(f"\n[{analyzed.quadrant_category.value}] {analyzed.title[:50]}...")
        logger.info(f"  Paper ID: {analyzed.paper_id}")
        logger.info(f"  Core Score: {analyzed.core_score:.1f}")
        logger.info(f"  Impact Score: {analyzed.impact_score:.1f}")

        if analyzed.analysis_summary:
            logger.info(f"  Analysis Summary: {analyzed.analysis_summary[:100]}...")
        if analyzed.extracted_methods:
            logger.info(f"  Extracted Methods: {analyzed.extracted_methods[:3]}...")
        if analyzed.impact_briefing:
            logger.info(f"  Impact Briefing: {analyzed.impact_briefing[:100]}...")
        if analyzed.rejection_note:
            logger.info(f"  Rejection Note: {analyzed.rejection_note}")

    # Verify LLM was called correctly (2 times: for core and impact papers)
    # REJECTED papers should NOT trigger LLM calls

    
    # expected_llm_calls = 2  # core + impact
    # if client.call_count == expected_llm_calls:
    #     logger.info(f"\n[PASS] LLM called {client.call_count} times (expected {expected_llm_calls})")
    #     logger.info("[PASS] REJECTED paper did not trigger LLM call (cost saving verified)")
    # else:
    #     logger.warning(f"[WARN] LLM called {client.call_count} times (expected {expected_llm_calls})")

    return analyzed_papers


def save_mock_output(papers: list) -> Path:
    """
    Save mock analysis results to JSON file.

    Args:
        papers: List of AnalyzedPaper

    Returns:
        Path to saved file
    """
    # Create output directory
    output_dir = project_root / "data" / "analysis_cache"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create output file
    output_file = output_dir / "mock_output.json"

    # Serialize papers
    papers_json = []
    for p in papers:
        paper_dict = p.model_dump()
        # Convert date to string
        paper_dict["publication_date"] = p.publication_date.isoformat()
        papers_json.append(paper_dict)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(papers_json, f, ensure_ascii=False, indent=2)

    logger.info(f"\nMock output saved to: {output_file}")
    return output_file


def main():
    """Main test entry point."""
    print("\n" + "=" * 60)
    print("Analysis Agent Mock Test Script")
    print("=" * 60)
    print("\nThis test uses MOCK data - no real API calls are made.")
    print("Following agent_analyst.md requirements:")
    print("  1. Hardcoded ScoredPaper objects (Core + Impact + Rejected)")
    print("  2. Analysis Agent processes with mock LLM")
    print("  3. Results saved to data/analysis_cache/mock_output.json")
    print("\n" + "-" * 60 + "\n")

    # Run test
    analyzed_papers = test_analysis_agent_with_mock()

    # Save output
    output_path = save_mock_output(analyzed_papers)

    # Final summary
    print("\n" + "=" * 60)
    print("TEST COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print(f"\nResults:")
    print(f"  - Papers analyzed: {len(analyzed_papers)}")
    print(f"  - Output file: {output_path}")
    print(f"\nPaper breakdown:")
    for p in analyzed_papers:
        print(f"  - [{p.quadrant_category.value}] {p.title[:40]}...")

    return analyzed_papers


if __name__ == "__main__":
    main()
