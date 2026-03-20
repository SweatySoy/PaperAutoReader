"""
Test SearchAgent with field configuration.
测试 SearchAgent 的 field 配置功能。
"""

import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.agents.search_agent import SearchAgent, ConfigAdapter

def test_config_field():
    """测试 ConfigAdapter 的 field 属性。"""
    print("=" * 60)
    print("Test 1: ConfigAdapter.field")
    print("=" * 60)

    config = ConfigAdapter()
    field = config.field

    print(f"\n配置文件中的 field: {field}")
    print(f"对应的查询格式: cat:{field}")

    print("\n" + "=" * 60)


def test_date_range_with_field():
    """测试日期范围模式 + field 过滤。"""
    print("\n" + "=" * 60)
    print("Test 2: Date Range Mode with Field Filter")
    print("=" * 60)

    agent = SearchAgent()

    # 获取 3 天的论文，使用 field 配置
    papers = agent.run(
        date_range=("2024-01-15", "2024-01-17"),
        max_results=20,  # 每天最多20篇
        use_field_filter=True,  # 使用 field 配置
        save_output=False
    )

    print(f"\n获取到 {len(papers)} 篇论文:")

    for i, p in enumerate(papers[:5], 1):
        print(f"\n{i}. {p.get('title', 'N/A')[:50]}...")
        print(f"   arXiv: {p.get('paper_id', 'N/A')}")
        print(f"   venue: {p.get('venue', 'N/A')}")

    print("\n" + "=" * 60)


def test_custom_query_override():
    """测试自定义查询覆盖 field 配置。"""
    print("\n" + "=" * 60)
    print("Test 3: Custom Query Override Field")
    print("=" * 60)

    agent = SearchAgent()

    # 使用自定义查询覆盖 field
    papers = agent.run(
        date_range=("2024-01-15", "2024-01-15"),
        max_results=10,
        search_query="cat:cs.LG",  # 覆盖 field 配置
        use_field_filter=False,
        save_output=False
    )

    print(f"\n获取到 {len(papers)} 篇机器学习论文:")

    for i, p in enumerate(papers[:3], 1):
        print(f"\n{i}. {p.get('title', 'N/A')[:50]}...")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_config_field()
    test_date_range_with_field()
    # test_custom_query_override()  # 取消注释测试自定义查询
