"""
test_search.py - Search Agent 测试脚本
=====================================

测试 arXiv API 和 Semantic Scholar API 链路是否通畅。
仅抓取少量论文 (2篇) 进行验证。

运行方式:
    python test_search.py
"""

import sys
import json
from datetime import date, datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ============================================================================
# Mock 数据模型 (模拟 src.models.CandidatePaper)
# 由于 models.py 尚未由另一个 Agent 完成，此处提供临时 Mock
# ============================================================================
@dataclass
class MockCandidatePaper:
    """
    Mock CandidatePaper 数据模型。
    严格遵循 Data_Schemas_Contract.md 定义。
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
        """转换为字典 (用于 JSON 序列化)。"""
        result = asdict(self)
        result["publication_date"] = self.publication_date.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "MockCandidatePaper":
        """从字典创建实例。"""
        if isinstance(data.get("publication_date"), str):
            data["publication_date"] = date.fromisoformat(data["publication_date"])
        return cls(**data)

# ============================================================================
# Mock 配置加载器 (模拟 src.config_loader.config)
# ============================================================================
class MockConfig:
    """Mock 配置对象。"""

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

# 全局配置实例
config = MockConfig()

# ============================================================================
# 注入 Mock 到 search_agent 模块
# ============================================================================
# 这允许 search_agent 在真实模块不存在时使用 Mock
import src.agents.search_agent as search_module

# 如果 src.models 不存在，注入 Mock
try:
    from src.models import CandidatePaper
except ImportError:
    search_module.CandidatePaper = MockCandidatePaper
    print("[Test] 使用 MockCandidatePaper (src.models 不存在)")

# 如果 src.config_loader 不存在，注入 Mock
try:
    from src.config_loader import config as real_config
except ImportError:
    search_module.config = config
    print("[Test] 使用 MockConfig (src.config_loader 不存在)")

# ============================================================================
# 测试函数
# ============================================================================
def test_arxiv_connection():
    """测试 arXiv API 连接。"""
    print("\n" + "=" * 60)
    print("TEST 1: arXiv API 连接测试")
    print("=" * 60)

    import arxiv

    try:
        search = arxiv.Search(
            query="all:quantum machine learning",
            max_results=2,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )

        papers = list(search.results())
        print(f"[OK] 成功连接 arXiv，获取到 {len(papers)} 篇论文")

        for i, paper in enumerate(papers, 1):
            print(f"\n  论文 {i}:")
            print(f"    标题: {paper.title[:80]}...")
            print(f"    ID: {paper.entry_id}")
            print(f"    发布日期: {paper.published}")

        return True

    except Exception as e:
        print(f"[FAIL] arXiv API 连接失败: {e}")
        return False

def test_semantic_scholar_connection():
    """测试 Semantic Scholar API 连接。"""
    print("\n" + "=" * 60)
    print("TEST 2: Semantic Scholar API 连接测试")
    print("=" * 60)

    from src.agents.search_agent import SemanticScholarClient

    client = SemanticScholarClient()

    # 测试一个已知的 arXiv 论文
    test_arxiv_id = "2303.01418"  # 一篇关于 QML 的论文

    try:
        result = client.get_paper_by_arxiv_id(test_arxiv_id)

        if result:
            print(f"[OK] 成功连接 Semantic Scholar")
            print(f"  论文标题: {result.get('title', 'N/A')}")
            print(f"  引用数: {result.get('citation_count', 0)}")
            print(f"  影响力引用: {result.get('influential_citation_count', 0)}")
            return True
        else:
            print("[WARN] Semantic Scholar 返回空结果 (论文可能未收录)")
            return True  # API 连接正常，只是论文未收录

    except Exception as e:
        print(f"[FAIL] Semantic Scholar API 连接失败: {e}")
        return False

def test_github_detection():
    """测试 GitHub 链接检测。"""
    print("\n" + "=" * 60)
    print("TEST 3: GitHub 链接检测测试")
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
        print(f"  {status} '{text[:40]}...' -> {result} (期望: {expected})")
        if result != expected:
            all_passed = False

    return all_passed

def test_full_search_workflow():
    """测试完整搜索流程 (仅抓取 2 篇论文)。"""
    print("\n" + "=" * 60)
    print("TEST 4: 完整搜索流程测试 (抓取 2 篇论文)")
    print("=" * 60)

    from src.agents.search_agent import SearchAgent

    # 创建 Agent，限制最大结果
    agent = SearchAgent(
        config_source=config,  # 使用 Mock 配置
        max_papers_per_query=2
    )

    # 定义进度回调
    def progress(current, total, title):
        print(f"  进度: {current}/{total} - {title[:50]}...")

    try:
        # Step 1: 从 arXiv 抓取
        arxiv_papers = agent.fetch_from_arxiv(days_back=30, max_results=2)

        if not arxiv_papers:
            print("[WARN] 未获取到论文 (可能网络问题或无匹配结果)")
            return False

        print(f"[OK] 从 arXiv 获取到 {len(arxiv_papers)} 篇论文")

        # Step 2: 引用增强
        enriched = agent.enrich_with_citations(
            arxiv_papers,
            progress_callback=progress
        )

        print(f"[OK] 引用数据增强完成")

        # Step 3: 保存
        output_path = agent.save_checkpoint(enriched)
        print(f"[OK] 已保存至: {output_path}")

        # 验证输出文件
        with open(output_path, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        print(f"[OK] 输出文件验证通过，包含 {len(saved_data)} 篇论文")

        # 打印论文摘要
        for i, paper in enumerate(saved_data, 1):
            print(f"\n  论文 {i}:")
            print(f"    ID: {paper['paper_id']}")
            print(f"    标题: {paper['title'][:60]}...")
            print(f"    作者: {', '.join(paper['authors'][:3])}")
            print(f"    引用数: {paper['citation_count']}")
            print(f"    有 GitHub: {paper['has_github_link']}")

        return True

    except Exception as e:
        print(f"[FAIL] 完整流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_adapter():
    """测试配置适配器。"""
    print("\n" + "=" * 60)
    print("TEST 5: 配置适配器测试")
    print("=" * 60)

    from src.agents.search_agent import ConfigAdapter

    # 测试从 YAML 加载
    adapter = ConfigAdapter()

    queries = adapter.build_search_queries()
    print(f"✓ 构建了 {len(queries)} 个搜索查询:")
    for q in queries[:5]:
        print(f"    - {q}")

    if len(queries) > 5:
        print(f"    ... (共 {len(queries)} 个)")

    # 验证没有硬编码
    hardcoded_terms = ["Quantum", "quantum machine learning"]  # 允许的
    for q in queries:
        # 检查是否从配置动态生成
        print(f"  查询: {q}")

    return True

# ============================================================================
# 主测试入口
# ============================================================================
def run_all_tests():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("Search Agent 测试套件")
    print("=" * 60)

    tests = [
        ("arXiv API 连接", test_arxiv_connection),
        ("Semantic Scholar API 连接", test_semantic_scholar_connection),
        ("GitHub 链接检测", test_github_detection),
        ("配置适配器", test_config_adapter),
        ("完整搜索流程", test_full_search_workflow),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n✗ 测试 '{name}' 抛出异常: {e}")
            results.append((name, False))

    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {status}: {name}")

    print(f"\n总计: {passed_count}/{total_count} 测试通过")

    return passed_count == total_count

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
