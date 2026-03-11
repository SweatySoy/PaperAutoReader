"""
Search Agent - Data Ingestion Module
=====================================
负责从 arXiv 和 Semantic Scholar 抓取论文数据，生成 CandidatePaper 对象列表。

严格遵循:
- rules/System_Architecture_PRD.md
- rules/Data_Schemas_Contract.md
- rules/File_IO_and_Logging.md
"""

import logging
import json
import re
import time
import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

import requests
import arxiv

# 假设这些模块由另一个 Agent 开发，此处仅作类型导入
# 在实际运行时，如果模块不存在，测试脚本会提供 Mock
try:
    from src.models import CandidatePaper
    from src.config_loader import config
except ImportError:
    # 占位符，测试时会用 Mock 替换
    CandidatePaper = None
    config = None

# ============================================================================
# 日志配置 (遵循 File_IO_and_Logging.md)
# ============================================================================
def setup_logging() -> logging.Logger:
    """配置标准日志，同时输出到控制台和文件。"""
    logger = logging.getLogger("SearchAgent")
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台 Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "[%(name)s] %(levelname)s: %(message)s"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # 文件 Handler
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"system_{date.today().isoformat()}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s - [%(name)s] %(levelname)s: %(message)s"
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger

logger = setup_logging()

# ============================================================================
# 配置适配器 (从 YAML 配置动态读取)
# ============================================================================
class ConfigAdapter:
    """
    配置适配器，支持两种模式:
    1. 从真实 config_loader 加载 (生产环境)
    2. 从 YAML 文件直接加载 (独立测试环境)
    """

    def __init__(self, config_source: Optional[Any] = None):
        self._config = config_source
        self._yaml_config: Dict[str, Any] = {}

        if config_source is None:
            # 尝试从 YAML 文件直接加载
            self._load_from_yaml()

    def _load_from_yaml(self) -> None:
        """从 fields/ 目录加载 YAML 配置。"""
        import yaml

        project_root = Path(__file__).parent.parent.parent
        yaml_path = project_root / "fields" / "Domain_Profile_QML.yaml"

        if yaml_path.exists():
            with open(yaml_path, "r", encoding="utf-8") as f:
                self._yaml_config = yaml.safe_load(f)
            logger.info(f"从 YAML 文件加载配置: {yaml_path}")
        else:
            logger.warning(f"YAML 配置文件不存在: {yaml_path}，使用默认配置")
            self._yaml_config = self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        """默认配置 (兜底)。"""
        return {
            "keywords_scoring": {
                "must_have": ["quantum machine learning"],
                "highly_relevant": ["variational quantum algorithm", "VQA"],
                "relevant": ["quantum computing"],
                "exclude": []
            },
            "impact_entities": {
                "tier_1_venues": ["Nature", "Science", "PRL"],
                "tier_1_institutions": ["MIT", "IBM Quantum"],
                "vip_authors": []
            }
        }

    @property
    def keywords_scoring(self) -> Dict[str, Any]:
        """获取关键词评分配置。"""
        if self._config and hasattr(self._config, "keywords_scoring"):
            return self._config.keywords_scoring
        return self._yaml_config.get("keywords_scoring", {})

    @property
    def impact_entities(self) -> Dict[str, Any]:
        """获取影响力实体配置。"""
        if self._config and hasattr(self._config, "impact_entities"):
            return self._config.impact_entities
        return self._yaml_config.get("impact_entities", {})

    def build_search_queries(self) -> List[str]:
        """
        根据配置动态构建 arXiv 搜索查询。
        严禁硬编码任何关键词!
        """
        queries = []
        kw = self.keywords_scoring

        # Must-have 关键词 -> 独立查询
        must_have = kw.get("must_have", [])
        for term in must_have:
            if term:
                queries.append(f"ti:{term}")  # title 中包含
                queries.append(f"abs:{term}")  # abstract 中包含

        # Highly relevant -> 组合查询
        highly_relevant = kw.get("highly_relevant", [])
        if highly_relevant:
            # 取前3个组合
            for term in highly_relevant[:3]:
                queries.append(f"all:{term}")

        # 去重
        queries = list(set(queries))
        logger.debug(f"构建了 {len(queries)} 个搜索查询: {queries}")
        return queries

# ============================================================================
# Semantic Scholar API 客户端 (带指数退避重试)
# ============================================================================
class SemanticScholarClient:
    """
    Semantic Scholar API 客户端。
    实现指数退避重试机制处理 HTTP 429 限流。
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # 秒

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"x-api-key": api_key})

    def _exponential_backoff_retry(
        self,
        url: str,
        params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        带指数退避的请求重试。

        Args:
            url: 请求 URL
            params: 请求参数

        Returns:
            JSON 响应数据，或 None (失败时)
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    return response.json()

                elif response.status_code == 429:
                    # 限流 - 指数退避
                    delay = self.BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Semantic Scholar API 限流 (429)，"
                        f"第 {attempt + 1} 次重试，等待 {delay:.1f} 秒..."
                    )
                    time.sleep(delay)
                    continue

                elif response.status_code == 404:
                    logger.debug(f"Semantic Scholar: 论文未找到 (404): {url}")
                    return None

                else:
                    logger.error(
                        f"Semantic Scholar API 错误: HTTP {response.status_code}"
                    )
                    return None

            except requests.exceptions.Timeout:
                logger.warning(
                    f"Semantic Scholar API 超时，第 {attempt + 1} 次重试..."
                )
                time.sleep(self.BASE_DELAY * (attempt + 1))
                continue

            except requests.exceptions.RequestException as e:
                logger.error(f"Semantic Scholar API 请求异常: {e}")
                return None

        logger.error(f"Semantic Scholar API: 达到最大重试次数 {self.MAX_RETRIES}，放弃")
        return None

    def get_paper_by_arxiv_id(
        self,
        arxiv_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        通过 arXiv ID 查询论文的引用信息。

        Args:
            arxiv_id: arXiv 论文 ID (如 "2303.12345")

        Returns:
            包含 citationCount, influentialCitationCount 的字典
        """
        # Semantic Scholar 支持 ARXIV: 前缀查询
        url = f"{self.BASE_URL}/paper/ARXIV:{arxiv_id}"
        params = {
            "fields": "citationCount,influentialCitationCount,title,year"
        }

        data = self._exponential_backoff_retry(url, params)
        if data:
            return {
                "citation_count": data.get("citationCount", 0),
                "influential_citation_count": data.get("influentialCitationCount", 0),
                "title": data.get("title"),
                "year": data.get("year")
            }
        return None

    def search_by_title(
        self,
        title: str,
        limit: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        通过标题模糊搜索论文 (当 arXiv ID 查询失败时的备选方案)。
        """
        url = f"{self.BASE_URL}/paper/search"
        params = {
            "query": title,
            "limit": limit,
            "fields": "citationCount,influentialCitationCount,title,year,externalIds"
        }

        data = self._exponential_backoff_retry(url, params)
        if data and "data" in data and data["data"]:
            paper = data["data"][0]
            return {
                "citation_count": paper.get("citationCount", 0),
                "influential_citation_count": paper.get("influentialCitationCount", 0),
                "title": paper.get("title"),
                "year": paper.get("year")
            }
        return None

# ============================================================================
# GitHub 链接检测器
# ============================================================================
class GitHubLinkDetector:
    """检测论文中是否包含 GitHub 链接。"""

    GITHUB_PATTERN = re.compile(
        r'https?://(?:www\.)?github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+',
        re.IGNORECASE
    )

    @classmethod
    def detect(cls, text: str) -> bool:
        """
        检测文本中是否包含 GitHub 链接。

        Args:
            text: 论文摘要或正文

        Returns:
            是否包含 GitHub 链接
        """
        if not text:
            return False
        return bool(cls.GITHUB_PATTERN.search(text))

    @classmethod
    def extract_links(cls, text: str) -> List[str]:
        """提取所有 GitHub 链接。"""
        if not text:
            return []
        return cls.GITHUB_PATTERN.findall(text)

# ============================================================================
# 论文数据转换器
# ============================================================================
def extract_arxiv_id(paper: arxiv.Result) -> str:
    """从 arxiv.Result 提取 arXiv ID。"""
    # arxiv 库的 entry_id 格式: http://arxiv.org/abs/2303.12345v1
    entry_id = paper.entry_id
    # 提取 ID 部分 (去掉版本号)
    match = re.search(r'arxiv\.org/abs/([0-9.]+)', entry_id, re.IGNORECASE)
    if match:
        return match.group(1).split('v')[0]  # 去版本号
    # 备选: 使用 get_short_id
    return paper.get_short_id().split('v')[0]

def convert_arxiv_to_candidate(
    arxiv_paper: arxiv.Result,
    citation_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    将 arxiv.Result 转换为 CandidatePaper 兼容的字典。

    Args:
        arxiv_paper: arxiv 库返回的论文对象
        citation_data: Semantic Scholar 返回的引用数据

    Returns:
        候选论文字典 (待实例化为 CandidatePaper)
    """
    # 提取作者列表
    authors = [author.name for author in arxiv_paper.authors]

    # 检测 GitHub 链接
    abstract = arxiv_paper.summary or ""
    has_github = GitHubLinkDetector.detect(abstract)

    # 发布日期
    pub_date = arxiv_paper.published.date() if arxiv_paper.published else date.today()

    # 引用数据
    citation_count = 0
    influential_citation_count = 0
    if citation_data:
        citation_count = citation_data.get("citation_count", 0) or 0
        influential_citation_count = citation_data.get("influential_citation_count", 0) or 0

    # 提取 arXiv ID
    paper_id = extract_arxiv_id(arxiv_paper)

    # 提取 venue (从 comment 或 journal_ref)
    venue = "arXiv"
    if arxiv_paper.journal_ref:
        venue = arxiv_paper.journal_ref

    return {
        "paper_id": f"arXiv:{paper_id}",
        "title": arxiv_paper.title,
        "abstract": abstract,
        "authors": authors,
        "venue": venue,
        "publication_date": pub_date,
        "url": arxiv_paper.entry_id,
        "citation_count": citation_count,
        "influential_citation_count": influential_citation_count,
        "has_github_link": has_github
    }

# ============================================================================
# Search Agent 主类
# ============================================================================
class SearchAgent:
    """
    Search Agent: 数据抓取与元数据增强。

    职责:
    1. 从 arXiv 抓取最新论文
    2. 调用 Semantic Scholar 获取引用信息
    3. 检测 GitHub 链接
    4. 输出 List[CandidatePaper] 并持久化
    """

    def __init__(
        self,
        config_source: Optional[Any] = None,
        semantic_scholar_key: Optional[str] = None,
        max_papers_per_query: int = 50
    ):
        """
        初始化 Search Agent。

        Args:
            config_source: 配置源 (config_loader 或 None)
            semantic_scholar_key: Semantic Scholar API Key (可选)
            max_papers_per_query: 每个查询最大返回论文数
        """
        self.config = ConfigAdapter(config_source)
        self.ss_client = SemanticScholarClient(api_key=semantic_scholar_key)
        self.max_papers_per_query = max_papers_per_query

    def fetch_from_arxiv(
        self,
        days_back: int = 7,
        max_results: int = 100
    ) -> List[arxiv.Result]:
        """
        从 arXiv 抓取最近 N 天的论文。

        Args:
            days_back: 回溯天数
            max_results: 最大结果数

        Returns:
            arxiv.Result 对象列表
        """
        queries = self.config.build_search_queries()
        if not queries:
            logger.warning("没有构建出任何搜索查询，使用默认查询")
            queries = ["all:quantum"]

        all_papers: List[arxiv.Result] = []
        seen_ids: set = set()

        for query in queries:
            try:
                logger.info(f"[Search Agent] 正在查询 arXiv: {query}")

                # 构造搜索
                search = arxiv.Search(
                    query=query,
                    max_results=max_results,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending
                )

                # 执行搜索
                for paper in search.results():
                    # 去重
                    paper_id = extract_arxiv_id(paper)
                    if paper_id in seen_ids:
                        continue
                    seen_ids.add(paper_id)

                    # 日期过滤
                    if paper.published:
                        cutoff_date = datetime.now() - timedelta(days=days_back)
                        if paper.published < cutoff_date:
                            continue

                    all_papers.append(paper)

                    if len(all_papers) >= max_results:
                        break

            except Exception as e:
                logger.error(f"arXiv 查询失败 [{query}]: {e}")
                continue

        logger.info(f"[Search Agent] 成功从 arXiv 抓取 {len(all_papers)} 篇论文")
        return all_papers

    def enrich_with_citations(
        self,
        papers: List[arxiv.Result],
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        使用 Semantic Scholar 增强论文的引用数据。

        Args:
            papers: arXiv 论文列表
            progress_callback: 进度回调函数

        Returns:
            增强后的论文字典列表
        """
        enriched_papers: List[Dict[str, Any]] = []

        logger.info(f"[Search Agent] 正在获取 {len(papers)} 篇论文的引用数据...")

        for i, paper in enumerate(papers):
            arxiv_id = extract_arxiv_id(paper)

            # 尝试通过 arXiv ID 查询
            citation_data = self.ss_client.get_paper_by_arxiv_id(arxiv_id)

            # 如果失败，尝试标题搜索
            if not citation_data and paper.title:
                citation_data = self.ss_client.search_by_title(paper.title)

            # 转换为候选论文格式
            candidate_dict = convert_arxiv_to_candidate(paper, citation_data)
            enriched_papers.append(candidate_dict)

            # 进度回调
            if progress_callback:
                progress_callback(i + 1, len(papers), candidate_dict["title"])

            # 礼貌性延迟 (避免触发 Semantic Scholar 限流)
            time.sleep(0.1)

        logger.info(
            f"[Search Agent] 引用数据获取完成，"
            f"成功增强 {len(enriched_papers)} 篇论文"
        )
        return enriched_papers

    def save_checkpoint(
        self,
        papers: List[Dict[str, Any]],
        output_date: Optional[date] = None
    ) -> Path:
        """
        将论文列表持久化到 JSON 文件。
        遵循 File_IO_and_Logging.md 的断点机制。

        Args:
            papers: 论文字典列表
            output_date: 输出日期 (默认今天)

        Returns:
            保存的文件路径
        """
        if output_date is None:
            output_date = date.today()

        # 使用相对路径
        project_root = Path(__file__).parent.parent.parent
        output_dir = project_root / "data" / "raw_papers"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{output_date.isoformat()}.json"

        # 序列化 (处理 date 对象)
        def json_serializer(obj):
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(papers, f, ensure_ascii=False, indent=2, default=json_serializer)

        logger.info(f"[Search Agent] 论文已保存至: {output_file}")
        return output_file

    def run(
        self,
        days_back: int = 7,
        max_results: int = 100,
        save_output: bool = True
    ) -> List[Dict[str, Any]]:
        """
        执行完整的搜索流程。

        Args:
            days_back: 回溯天数
            max_results: 最大结果数
            save_output: 是否保存输出文件

        Returns:
            候选论文字典列表
        """
        logger.info("=" * 60)
        logger.info("[Search Agent] 开始执行数据抓取流程")
        logger.info(f"  - 回溯天数: {days_back}")
        logger.info(f"  - 最大结果数: {max_results}")
        logger.info("=" * 60)

        # Step 1: 从 arXiv 抓取
        arxiv_papers = self.fetch_from_arxiv(days_back, max_results)

        if not arxiv_papers:
            logger.warning("[Search Agent] 未抓取到任何论文，流程结束")
            return []

        # Step 2: 引用数据增强
        enriched_papers = self.enrich_with_citations(arxiv_papers)

        # Step 3: 持久化
        if save_output:
            self.save_checkpoint(enriched_papers)

        logger.info("[Search Agent] 数据抓取流程完成")
        return enriched_papers

# ============================================================================
# 便捷函数
# ============================================================================
def search_papers(
    days_back: int = 7,
    max_results: int = 100,
    config_source: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    便捷函数: 执行论文搜索。

    Args:
        days_back: 回溯天数
        max_results: 最大结果数
        config_source: 配置源

    Returns:
        候选论文字典列表
    """
    agent = SearchAgent(config_source=config_source)
    return agent.run(days_back=days_back, max_results=max_results)

# ============================================================================
# 主入口
# ============================================================================
if __name__ == "__main__":
    # 独立运行测试
    papers = search_papers(days_back=7, max_results=10)
    print(f"\n抓取到 {len(papers)} 篇论文:")
    for i, p in enumerate(papers[:5], 1):
        print(f"  {i}. {p['title'][:60]}...")
        print(f"     引用数: {p['citation_count']}, GitHub: {p['has_github_link']}")
