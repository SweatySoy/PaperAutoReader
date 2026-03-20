"""
Test SearchAgent with date range functionality.
测试 SearchAgent 的日期范围获取功能。
"""

import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.agents.search_agent import SearchAgent

def test_date_range_mode():
    """测试日期范围模式。"""
    print("=" * 60)
    print("Test: SearchAgent Date Range Mode")
    print("=" * 60)

    agent = SearchAgent()

    # 测试获取 3 天的论文
    papers = agent.run(
        date_range=("2024-01-15", "2024-01-17"),
        max_results=10,  # 每天最多10篇
        search_query="all:quantum",
        save_output=False
    )

    print(f"\n获取到 {len(papers)} 篇论文:")

    for i, p in enumerate(papers[:5], 1):
        print(f"\n{i}. {p.get('title', 'N/A')[:60]}...")
        print(f"   arXiv: {p.get('paper_id', 'N/A')}")
        print(f"   引用: {p.get('citation_count', 0)}")
        print(f"   venue: {p.get('venue', 'N/A')}")

    print("\n" + "=" * 60)
    print("测试完成!")


def test_days_back_mode():
    """测试回溯模式 (原有功能)。"""
    print("\n" + "=" * 60)
    print("Test: SearchAgent Days Back Mode (Legacy)")
    print("=" * 60)

    agent = SearchAgent()

    papers = agent.run(
        days_back=7,
        max_results=5,
        save_output=False
    )

    print(f"\n获取到 {len(papers)} 篇论文")

    for i, p in enumerate(papers[:3], 1):
        print(f"\n{i}. {p.get('title', 'N/A')[:60]}...")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_date_range_mode()
    # test_days_back_mode()  # 取消注释测试回溯模式
