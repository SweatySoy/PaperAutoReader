"""
Test CrossRef integration in SearchAgent.
测试 CrossRef 发表确认功能。
"""

import sys
import os
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.agents.search_agent import CrossRefClient

def test_crossref_client():
    """测试 CrossRef 客户端基本功能。"""
    print("=" * 60)
    print("Test 1: CrossRef API Connection")
    print("=" * 60)

    client = CrossRefClient()

    # 测试已发表论文 (著名论文)
    # arXiv:1706.03762 = "Attention Is All You Need" (Transformer)
    # 已发表在 NeurIPS 2017
    print("\n[1] 测试已发表论文: Attention Is All You Need (arXiv:1706.03762)")

    result = client.query_by_arxiv_id("1706.03762")
    print(f"    arXiv ID 查询结果: {result}")

    if result and result.get("is_published"):
        print(f"    [OK] 确认发表: {result['venue']}")
    else:
        # 尝试标题查询
        result = client.query_by_title(
            "Attention Is All You Need",
            authors=["Vaswani", "Shazeer"]
        )
        print(f"    标题查询结果: {result}")
        if result and result.get("is_published"):
            print(f"    [OK] 确认发表: {result['venue']}")
        else:
            print("    [SKIP] 未找到发表记录 (可能 API 返回格式变化)")

    # 测试另一篇已发表论文
    # arXiv:1810.04805 = BERT, 发表在 NAACL 2019
    print("\n[2] 测试已发表论文: BERT (arXiv:1810.04805)")

    result = client.get_publication_info(
        arxiv_id="1810.04805",
        title="BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        authors=["Devlin", "Chang", "Lee", "Toutanova"]
    )
    print(f"    结果: {result}")

    if result.get("is_published"):
        print(f"    [OK] 确认发表: {result['venue']}")
    else:
        print("    [SKIP] 未找到发表记录 (可能仍在 arXiv 或查询失败)")

    # 测试未发表论文 (假设一篇新论文)
    print("\n[3] 测试未发表/新论文: 假设新论文")

    result = client.get_publication_info(
        arxiv_id="2401.00001",  # 假设 ID
        title="A Brand New Paper That Does Not Exist Yet",
        authors=["Unknown Author"]
    )
    print(f"    结果: {result}")

    if not result.get("is_published"):
        print("    [OK] 正确识别为未发表")
    else:
        print(f"    [WARN] 意外识别为已发表: {result['venue']}")

    print("\n" + "=" * 60)
    print("CrossRef 测试完成")
    print("=" * 60)


def test_search_agent_with_crossref():
    """测试完整 SearchAgent 流程 (包含 CrossRef)。"""
    print("\n" + "=" * 60)
    print("Test 2: SearchAgent with CrossRef Integration")
    print("=" * 60)

    from src.agents.search_agent import SearchAgent

    # 初始化 Agent
    agent = SearchAgent()

    # 模拟论文数据
    mock_papers = [
        {
            "paper_id": "arXiv:1706.03762",
            "title": "Attention Is All You Need",
            "authors": ["Vaswani", "Shazeer", "Natarajan", "Parmar"],
            "venue": "arXiv",
            "abstract": "The dominant sequence transduction models..."
        },
        {
            "paper_id": "arXiv:1810.04805",
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "authors": ["Devlin", "Chang", "Lee", "Toutanova"],
            "venue": "arXiv",
            "abstract": "We introduce a new language representation model..."
        }
    ]

    print(f"\n测试 {len(mock_papers)} 篇论文的 CrossRef 确认...")

    enriched = agent.enrich_with_crossref(mock_papers)

    print("\n结果:")
    for paper in enriched:
        print(f"  - {paper['title'][:50]}...")
        print(f"    venue: {paper.get('venue', 'N/A')}")
        if paper.get('doi'):
            print(f"    DOI: {paper['doi']}")

    print("\n" + "=" * 60)
    print("SearchAgent CrossRef 集成测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_crossref_client()
    test_search_agent_with_crossref()
