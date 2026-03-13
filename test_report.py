"""
Test Script for Report Agent (Agent 4)
======================================

This script creates mock AnalyzedPaper data and tests the Report Agent
to generate a sample report for visual inspection.

Author: AI Coding Agent
Branch: feat/agent4-report
"""

import sys
from datetime import date
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from models import AnalyzedPaper, QuadrantCategory
from agents.report_agent import ReportAgent


def create_mock_papers() -> list[AnalyzedPaper]:
    """Create mock AnalyzedPaper data covering all quadrants."""

    papers = []

    # === CROWN JEWELS (High Core + High Impact) ===
    papers.append(AnalyzedPaper(
        paper_id="arXiv:2024.12345",
        title="Quantum Variational Circuits for Efficient Molecular Simulation: A Comprehensive Study",
        abstract="This paper presents a novel variational quantum algorithm for molecular simulation...",
        authors=["Alice Zhang", "Bob Wang", "Carol Li", "David Chen", "Eve Liu", "Frank Wu"],
        venue="Nature Physics",
        publication_date=date(2024, 12, 15),
        url="https://arxiv.org/abs/2024.12345",
        citation_count=156,
        influential_citation_count=42,
        has_github_link=True,
        core_score=92.5,
        impact_score=88.0,
        quadrant_category=QuadrantCategory.CROWN_JEWEL,
        routing_reason="Core score 92.5 (highly relevant to quantum simulation), Impact score 88.0 (Nature Physics, high citations, GitHub repo with 500+ stars)",
        analysis_summary="本文提出了一种创新的变分量子电路架构，通过引入自适应参数化层，显著提升了分子基态能量模拟的精度。核心贡献包括：(1) 自适应电路深度优化策略；(2) 新型的噪声缓解技术；(3) 在H2O和LiH分子上的实验验证。",
        extracted_methods=[
            "Adaptive Variational Quantum Eigensolver (ADAPT-VQE)",
            "Noise-aware parameter optimization",
            "Trotterized Hamiltonian simulation with error bounds",
            "Hybrid quantum-classical gradient descent"
        ]
    ))

    papers.append(AnalyzedPaper(
        paper_id="arXiv:2024.67890",
        title="Topological Quantum Error Correction with Surface Codes: Scalable Architecture Design",
        abstract="We propose a scalable architecture for topological quantum error correction...",
        authors=["Yuki Tanaka", "Hiroshi Sato", "Kenji Yamamoto"],
        venue="Physical Review X",
        publication_date=date(2024, 11, 20),
        url="https://arxiv.org/abs/2024.67890",
        citation_count=89,
        influential_citation_count=28,
        has_github_link=True,
        core_score=85.0,
        impact_score=82.5,
        quadrant_category=QuadrantCategory.CROWN_JEWEL,
        routing_reason="Directly addresses quantum error correction, critical for quantum computing; published in PRX with significant citations",
        analysis_summary="提出了一种基于表面码的可扩展拓扑量子纠错架构。通过创新的晶格设计和 syndrome 测量协议，实现了优于传统表面码 15% 的阈值提升。",
        extracted_methods=[
            "Modified surface code lattice surgery",
            "Syndrome measurement optimization",
            "Logical qubit transversal gates"
        ]
    ))

    # === CORE TRACK (High Core + Low Impact) ===
    papers.append(AnalyzedPaper(
        paper_id="arXiv:2024.11111",
        title="Parameterized Quantum Circuit Optimization Using Gradient-Free Methods",
        abstract="Gradient-free optimization techniques for parameterized quantum circuits...",
        authors=["Michael Brown", "Sarah Davis"],
        venue="arXiv",
        publication_date=date(2024, 12, 1),
        url="https://arxiv.org/abs/2024.11111",
        citation_count=12,
        influential_citation_count=3,
        has_github_link=False,
        core_score=78.0,
        impact_score=45.0,
        quadrant_category=QuadrantCategory.CORE_TRACK,
        routing_reason="Highly relevant to quantum circuit optimization but preprint with limited citations",
        analysis_summary="探索了多种无梯度优化方法在参数化量子电路中的应用，包括 CMA-ES 和 Powell 方法。实验表明在噪声环境下无梯度方法比传统梯度下降更稳定。",
        extracted_methods=[
            "CMA-ES optimization",
            "Powell's method adaptation",
            "Noise-robust cost landscape analysis"
        ]
    ))

    papers.append(AnalyzedPaper(
        paper_id="arXiv:2024.22222",
        title="Hybrid Quantum-Classical Neural Networks for Image Classification",
        abstract="We design hybrid architectures combining quantum and classical layers...",
        authors=["Jennifer Lee", "Kevin Park", "Linda Chen"],
        venue="QML Workshop",
        publication_date=date(2024, 10, 15),
        url="https://arxiv.org/abs/2024.22222",
        citation_count=8,
        influential_citation_count=2,
        has_github_link=True,
        core_score=72.5,
        impact_score=38.0,
        quadrant_category=QuadrantCategory.CORE_TRACK,
        routing_reason="Relevant to quantum machine learning domain, but workshop paper with modest impact",
        analysis_summary="提出了一种混合量子-经典神经网络架构，在 MNIST 和 CIFAR-10 数据集上进行了初步验证。量子层用于特征提取，经典层用于分类。",
        extracted_methods=[
            "Quantum convolution layer",
            "Parameterized quantum feature map",
            "Hybrid backpropagation scheme"
        ]
    ))

    # === IMPACT TRACK (Low Core + High Impact) ===
    papers.append(AnalyzedPaper(
        paper_id="arXiv:2024.33333",
        title="Large Language Models for Scientific Discovery: A Paradigm Shift",
        abstract="How LLMs are transforming scientific research workflows...",
        authors=["OpenAI Research Team", "DeepMind Scientists"],
        venue="Nature",
        publication_date=date(2024, 12, 10),
        url="https://arxiv.org/abs/2024.33333",
        citation_count=523,
        influential_citation_count=156,
        has_github_link=True,
        core_score=35.0,
        impact_score=95.0,
        quadrant_category=QuadrantCategory.IMPACT_TRACK,
        routing_reason="Low direct relevance to quantum computing, but extremely high impact (Nature, 500+ citations, OpenAI/DeepMind authors)",
        impact_briefing="LLM 在科学发现中的范式转变：可借鉴其 \"规模化 + 领域知识注入\" 的思路，用于量子算法设计和自动化实验参数调优。该方法论可能对量子计算研究产生跨界启发。"
    ))

    papers.append(AnalyzedPaper(
        paper_id="arXiv:2024.44444",
        title="Breakthrough in Protein Folding: AlphaFold 3 Architecture Revealed",
        abstract="The latest advancement in protein structure prediction...",
        authors=["John Jumper", "Demis Hassabis", "Pushmeet Kohli"],
        venue="Science",
        publication_date=date(2024, 11, 1),
        url="https://arxiv.org/abs/2024.44444",
        citation_count=892,
        influential_citation_count=312,
        has_github_link=True,
        core_score=22.0,
        impact_score=98.0,
        quadrant_category=QuadrantCategory.IMPACT_TRACK,
        routing_reason="Not quantum-related, but revolutionary impact on computational biology with potential cross-domain insights",
        impact_briefing="AlphaFold 3 的注意力机制创新和端到端学习方法，可作为量子分子模拟中「几何感知神经网络」的设计参考。其中的对称性编码技术值得借鉴。"
    ))

    # === REJECTED (Low Core + Low Impact) ===
    papers.append(AnalyzedPaper(
        paper_id="arXiv:2024.55555",
        title="A Survey of Classical Machine Learning Algorithms",
        abstract="This survey covers traditional ML algorithms like SVM, Random Forest...",
        authors=["Unknown Author"],
        venue="arXiv",
        publication_date=date(2024, 8, 1),
        url="https://arxiv.org/abs/2024.55555",
        citation_count=2,
        influential_citation_count=0,
        has_github_link=False,
        core_score=15.0,
        impact_score=12.0,
        quadrant_category=QuadrantCategory.REJECTED,
        routing_reason="Classical ML survey with no quantum relevance and minimal citations",
        rejection_note="经典机器学习综述，与量子计算无关，引用量极低"
    ))

    papers.append(AnalyzedPaper(
        paper_id="arXiv:2024.66666",
        title="Optimization of Delivery Routes Using Genetic Algorithms",
        abstract="We apply genetic algorithms to optimize delivery truck routes...",
        authors=["Tom Smith", "Jerry White"],
        venue="ICLR Workshop",
        publication_date=date(2024, 9, 15),
        url="https://arxiv.org/abs/2024.66666",
        citation_count=5,
        influential_citation_count=1,
        has_github_link=False,
        core_score=8.0,
        impact_score=25.0,
        quadrant_category=QuadrantCategory.REJECTED,
        routing_reason="Completely unrelated to quantum computing domain",
        rejection_note="物流优化问题，与量子计算领域无关"
    ))

    papers.append(AnalyzedPaper(
        paper_id="arXiv:2024.77777",
        title="Preliminary Study on Weather Prediction with Neural Networks",
        abstract="A simple neural network approach for weather forecasting...",
        authors=["Climate Research Group"],
        venue="arXiv",
        publication_date=date(2024, 7, 20),
        url="https://arxiv.org/abs/2024.77777",
        citation_count=0,
        influential_citation_count=0,
        has_github_link=False,
        core_score=5.0,
        impact_score=8.0,
        quadrant_category=QuadrantCategory.REJECTED,
        routing_reason="Weather prediction with no quantum relevance and no impact signals",
        rejection_note="天气预报研究，与领域无关，无影响力指标"
    ))

    return papers


def main():
    """Run the Report Agent test."""
    print("=" * 60)
    print("Report Agent Test - Mock Data Generation")
    print("=" * 60)

    # Create mock data
    print("\n[1] Creating mock AnalyzedPaper data...")
    papers = create_mock_papers()
    print(f"    Created {len(papers)} mock papers")

    # Count by quadrant
    from collections import Counter
    categories = Counter(p.quadrant_category for p in papers)
    print(f"    - Crown Jewels: {categories[QuadrantCategory.CROWN_JEWEL]}")
    print(f"    - Core Track: {categories[QuadrantCategory.CORE_TRACK]}")
    print(f"    - Impact Track: {categories[QuadrantCategory.IMPACT_TRACK]}")
    print(f"    - Rejected: {categories[QuadrantCategory.REJECTED]}")

    # Initialize Report Agent
    print("\n[2] Initializing Report Agent...")
    agent = ReportAgent()

    # Generate report
    print("\n[3] Generating report...")
    report, filepath = agent.run(
        papers=papers,
        report_date=date(2024, 12, 20),
        filename="Test_Mock_Report.md"
    )

    print(f"    Report saved to: {filepath}")
    print(f"    Report date: {report.report_date}")

    # Print summary
    print("\n[4] Report Summary:")
    print(f"    - Crown Jewels: {len(report.crown_jewels)}")
    print(f"    - Core Papers: {len(report.core_papers)}")
    print(f"    - Impact Papers: {len(report.impact_papers)}")
    print(f"    - Rejected Papers: {len(report.rejected_papers_log)}")

    print("\n" + "=" * 60)
    print("[OK] Test completed successfully!")
    print(f"Please review the generated report at:")
    print(f"   {filepath}")
    print("=" * 60)


if __name__ == "__main__":
    main()
