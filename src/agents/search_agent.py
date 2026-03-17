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
    BASE_API = "Zs5EfRHuFX9ZUZfdV4NFY6kUV6ezReKX3u1rkcpC"
    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # 秒

    def __init__(self, api_key: Optional[str] = BASE_API):
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

    def get_papers_batch(
        self,
        arxiv_ids: List[str],
        batch_size: int = 500
    ) -> Dict[str, Dict[str, Any]]:
        """
        批量查询论文引用数据 (Batch API)。
        **推荐使用** - 避免 N+1 API 浪费问题。

        Args:
            arxiv_ids: arXiv ID 列表 (如 ["2303.12345", "2401.00001"])
            batch_size: 每批最大数量 (S2 限制 500)

        Returns:
            字典: {arxiv_id: {citation_count, influential_citation_count, ...}}
        """
        if not arxiv_ids:
            return {}

        results: Dict[str, Dict[str, Any]] = {}

        # 分批处理 (S2 API 限制每批最多 500 个)
        for i in range(0, len(arxiv_ids), batch_size):
            batch_ids = arxiv_ids[i:i + batch_size]

            # 构造 S2 格式的 ID 列表
            s2_ids = [f"ARXIV:{aid}" for aid in batch_ids]

            logger.info(
                f"[Search Agent] 批量查询 Semantic Scholar: "
                f"第 {i//batch_size + 1} 批，共 {len(s2_ids)} 篇论文"
            )

            # POST 请求到 batch endpoint
            url = f"{self.BASE_URL}/paper/batch"
            params = {"fields": "citationCount,influentialCitationCount,title,year"}
            payload = {"ids": s2_ids}

            for attempt in range(self.MAX_RETRIES):
                try:
                    response = self.session.post(
                        url,
                        params=params,
                        json=payload,
                        timeout=60
                    )

                    if response.status_code == 200:
                        data = response.json()
                        # S2 Batch API 返回数组，顺序与请求顺序一致
                        # data[i] 对应 s2_ids[i] (若存在)，否则为 null
                        for idx, item in enumerate(data):
                            orig_id = batch_ids[idx]  # 原始 arXiv ID
                            if item is None:
                                # 论文未在 S2 中找到，设置默认值
                                results[orig_id] = {
                                    "citation_count": 0,
                                    "influential_citation_count": 0,
                                    "title": None,
                                    "year": None
                                }
                                logger.debug(f"论文 {orig_id} 在 Semantic Scholar 中未找到")
                            else:
                                results[orig_id] = {
                                    "citation_count": item.get("citationCount", 0) or 0,
                                    "influential_citation_count": item.get("influentialCitationCount", 0) or 0,
                                    "title": item.get("title"),
                                    "year": item.get("year")
                                }
                        break  # 成功，退出重试循环

                    elif response.status_code == 429:
                        delay = self.BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            f"Semantic Scholar Batch API 限流 (429)，"
                            f"第 {attempt + 1} 次重试，等待 {delay:.1f} 秒..."
                        )
                        time.sleep(delay)
                        continue

                    elif response.status_code == 400:
                        logger.error(f"Semantic Scholar Batch API 请求格式错误: {response.text}")
                        break

                    else:
                        logger.error(
                            f"Semantic Scholar Batch API 错误: HTTP {response.status_code}"
                        )
                        break

                except requests.exceptions.Timeout:
                    logger.warning(
                        f"Semantic Scholar Batch API 超时，第 {attempt + 1} 次重试..."
                    )
                    time.sleep(self.BASE_DELAY * (attempt + 1))
                    continue

                except requests.exceptions.RequestException as e:
                    logger.error(f"Semantic Scholar Batch API 请求异常: {e}")
                    # 失败时为所有论文设置默认值
                    for orig_id in batch_ids:
                        if orig_id not in results:
                            results[orig_id] = {
                                "citation_count": 0,
                                "influential_citation_count": 0,
                                "title": None,
                                "year": None
                            }
                    break

        logger.info(
            f"[Search Agent] 批量查询完成，"
            f"成功获取 {len([r for r in results.values() if r['citation_count'] > 0])} 篇论文的引用数据"
        )
        return results

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
# CrossRef API 客户端 (确认论文发表状态)
# ============================================================================
class CrossRefClient:
    """
    CrossRef API 客户端。
    用于确认 arXiv 论文是否已正式发表，并获取发表期刊名称。

    CrossRef 是免费的开放 API，无需 API Key。
    文档: https://api.crossref.org
    """

    BASE_URL = "https://api.crossref.org/works"
    MAX_RETRIES = 3
    BASE_DELAY = 1.0

    def __init__(self, mailto: Optional[str] = None):
        """
        初始化 CrossRef 客户端。

        Args:
            mailto: 邮箱地址 (CrossRef 建议提供，可提高速率限制)
        """
        self.session = requests.Session()
        headers = {"User-Agent": "PaperAutoReader/1.0 (https://github.com/paperautoreader)"}
        if mailto:
            headers["User-Agent"] += f" mailto:{mailto}"
        self.session.headers.update(headers)

    def _retry_request(
        self,
        url: str,
        params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """带重试的请求。"""
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.get(url, params=params, timeout=30)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    delay = self.BASE_DELAY * (2 ** attempt)
                    logger.warning(f"CrossRef API 限流 (429)，等待 {delay:.1f} 秒...")
                    time.sleep(delay)
                    continue
                else:
                    logger.debug(f"CrossRef API 返回 {response.status_code}: {url}")
                    return None

            except requests.exceptions.Timeout:
                logger.warning(f"CrossRef API 超时，第 {attempt + 1} 次重试...")
                time.sleep(self.BASE_DELAY * (attempt + 1))
                continue
            except requests.exceptions.RequestException as e:
                logger.error(f"CrossRef API 请求异常: {e}")
                return None

        return None

    def query_by_arxiv_id(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """
        通过 arXiv ID 查询 CrossRef。

        CrossRef 支持通过 DOI 前缀查询，但 arXiv 论文的 DOI 格式为:
        10.48550/arXiv.XXXX.XXXXX 或 10.5555/arXiv.XXXX.XXXXX

        Args:
            arxiv_id: arXiv ID (如 "2303.12345")

        Returns:
            包含 venue, DOI 等信息的字典，或 None
        """
        # 尝试多种 arXiv DOI 格式
        doi_candidates = [
            f"10.48550/arXiv.{arxiv_id}",  # 新格式
            f"10.5555/arXiv.{arxiv_id}",   # 旧格式
            f"10.48550/arxiv.{arxiv_id}",  # 小写变体
        ]

        for doi in doi_candidates:
            url = f"{self.BASE_URL}/{doi}"
            data = self._retry_request(url, {})

            if data and "message" in data:
                msg = data["message"]
                return self._parse_crossref_response(msg)

        return None

    def query_by_title(
        self,
        title: str,
        authors: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        通过标题模糊查询 CrossRef。

        Args:
            title: 论文标题
            authors: 作者列表 (用于提高匹配准确度)

        Returns:
            包含 venue, DOI 等信息的字典，或 None
        """
        if not title:
            return None

        # 构造查询参数
        params = {
            "query.title": title,
            "rows": 5  # 取前5个结果进行匹配
        }

        data = self._retry_request(self.BASE_URL, params)

        if not data or "message" not in data or "items" not in data["message"]:
            return None

        items = data["message"]["items"]
        if not items:
            return None

        # 寻找最佳匹配
        best_match = self._find_best_match(title, authors, items)
        if best_match:
            return self._parse_crossref_response(best_match)

        return None

    def _parse_crossref_response(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """解析 CrossRef 响应，提取发表信息。"""
        result = {
            "doi": msg.get("DOI"),
            "is_published": False,
            "venue": None
        }

        # 已知学术出版商白名单
        known_publishers = {
            "Elsevier", "Springer", "Wiley", "Taylor & Francis", "Oxford University Press",
            "Cambridge University Press", "IEEE", "ACM", "Nature Publishing Group",
            "Science", "AAAS", "APS", "AIP", "IOP Publishing", "World Scientific",
            "Sage Publications", "MDPI", "Frontiers", "PLoS", "BMC",
            "Association for Computational Linguistics", "ACL", "NeurIPS", "ICML",
            "OpenReview", "JMLR", "Proceedings of"
        }

        # 获取容器标题 (期刊名/会议名) - 这是主要判断依据
        container_title = msg.get("container-title", [])
        if container_title:
            if isinstance(container_title, list):
                result["venue"] = container_title[0]
            else:
                result["venue"] = container_title
            result["is_published"] = True

        # 备选: short-container-title
        if not result["venue"]:
            short_title = msg.get("short-container-title", [])
            if short_title:
                if isinstance(short_title, list):
                    result["venue"] = short_title[0]
                else:
                    result["venue"] = short_title
                result["is_published"] = True

        # 仅当 container-title 存在时才认为正式发表
        # publisher 字段不可靠 (很多是第三方存档机构)
        # 只有当 publisher 是已知学术出版商时才作为备选
        if not result["venue"]:
            publisher = msg.get("publisher", "")
            publisher_lower = publisher.lower()

            # 检查是否是已知学术出版商
            is_known_publisher = any(
                kp.lower() in publisher_lower or publisher_lower in kp.lower()
                for kp in known_publishers
            )

            if is_known_publisher and publisher_lower != "arxiv":
                result["venue"] = publisher
                result["is_published"] = True

        # 最终验证: 排除 arXiv 和可疑来源
        if result["venue"]:
            venue_lower = result["venue"].lower()
            if "arxiv" in venue_lower:
                result["is_published"] = False
                result["venue"] = None
            # 排除可疑的第三方存档机构
            suspicious_keywords = ["academy of", "institute of", "research center", "repository"]
            if any(kw in venue_lower for kw in suspicious_keywords):
                # 需要 container-title 确认才可信
                if not container_title:
                    result["is_published"] = False
                    result["venue"] = None

        return result

    def _find_best_match(
        self,
        title: str,
        authors: Optional[List[str]],
        items: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        从多个结果中找到最佳匹配。

        策略:
        1. 标题相似度 > 0.70 且至少1个作者匹配
        2. 标题相似度 > 0.90 且有作者信息 (极高置信度)

        注意: 作者匹配是强制性的，防止误匹配
        """
        title_lower = title.lower()
        title_words = set(title_lower.split())
        # 过滤掉常见停用词，提高匹配质量
        stopwords = {"a", "an", "the", "of", "for", "and", "or", "in", "on", "to", "is", "are", "we", "that", "this", "with", "by", "from", "as", "not", "be", "which", "it", "all", "new", "using", "based", "learning", "model", "models", "method", "methods"}
        title_words_filtered = title_words - stopwords

        best_match_item = None
        best_similarity = 0.0

        for item in items:
            item_titles = item.get("title", [])
            if not item_titles:
                continue

            item_title = item_titles[0] if isinstance(item_titles, list) else item_titles
            item_title_lower = item_title.lower()
            item_title_words = set(item_title_lower.split())
            item_title_words_filtered = item_title_words - stopwords

            # 计算 Jaccard 相似度 (使用过滤后的词集)
            if not title_words_filtered or not item_title_words_filtered:
                continue

            intersection = len(title_words_filtered & item_title_words_filtered)
            union = len(title_words_filtered | item_title_words_filtered)
            similarity = intersection / union if union > 0 else 0

            # 检查作者匹配数量
            author_match_count = 0
            item_author_names = []
            if authors:
                item_authors = item.get("author", [])
                item_author_names = [
                    a.get("family", "").lower()
                    for a in item_authors
                    if isinstance(a, dict)
                ]
                # 计算匹配的作者数量
                for author in authors[:5]:  # 检查前5个作者
                    author_lower = author.lower()
                    if any(author_lower in name or name in author_lower for name in item_author_names):
                        author_match_count += 1

            # 判断是否接受匹配 - 必须有作者匹配
            if similarity > 0.90 and len(item_author_names) > 0:
                # 极高相似度 + 有作者信息
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_item = item
            elif similarity > 0.70 and author_match_count >= 1:
                # 中等相似度 + 至少1个作者匹配
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_item = item

        if best_match_item:
            logger.debug(f"CrossRef 匹配成功: 相似度={best_similarity:.2f}")

        return best_match_item

    def get_publication_info(
        self,
        arxiv_id: str,
        title: str,
        authors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        获取论文发表信息的统一入口。

        优先通过 arXiv ID 查询，失败后通过标题查询。

        Args:
            arxiv_id: arXiv ID
            title: 论文标题
            authors: 作者列表

        Returns:
            {"is_published": bool, "venue": str/None, "doi": str/None}
        """
        # 策略1: 通过 arXiv DOI 查询
        result = self.query_by_arxiv_id(arxiv_id)
        if result and result.get("is_published"):
            logger.debug(f"CrossRef 通过 arXiv ID 确认发表: {arxiv_id} -> {result['venue']}")
            return result

        # 策略2: 通过标题查询
        result = self.query_by_title(title, authors)
        if result and result.get("is_published"):
            logger.debug(f"CrossRef 通过标题确认发表: {title[:50]}... -> {result['venue']}")
            return result

        # 未找到发表记录
        return {"is_published": False, "venue": None, "doi": None}

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
    3. 调用 CrossRef 确认论文是否已正式发表
    4. 检测 GitHub 链接
    5. 输出 List[CandidatePaper] 并持久化
    """

    def __init__(
        self,
        config_source: Optional[Any] = None,
        semantic_scholar_key: Optional[str] = None,
        crossref_mailto: Optional[str] = None,
        max_papers_per_query: int = 50
    ):
        """
        初始化 Search Agent。

        Args:
            config_source: 配置源 (config_loader 或 None)
            semantic_scholar_key: Semantic Scholar API Key (可选)
            crossref_mailto: CrossRef 联系邮箱 (可选，提高速率限制)
            max_papers_per_query: 每个查询最大返回论文数
        """
        self.config = ConfigAdapter(config_source)
        self.ss_client = SemanticScholarClient(api_key=semantic_scholar_key)
        self.crossref_client = CrossRefClient(mailto=crossref_mailto)
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

                    # Date filtering - use timezone-aware datetime
                    if paper.published:
                        from datetime import timezone
                        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
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
        使用 Semantic Scholar 批量 API 增强论文的引用数据。

        **优化**: 使用 Batch API 一次性查询所有论文，避免 N+1 API 浪费。

        Args:
            papers: arXiv 论文列表
            progress_callback: 进度回调函数

        Returns:
            增强后的论文字典列表
        """
        if not papers:
            return []

        enriched_papers: List[Dict[str, Any]] = []

        # Step 1: 提取所有 arXiv ID
        arxiv_ids = [extract_arxiv_id(paper) for paper in papers]
        logger.info(
            f"[Search Agent] 正在批量获取 {len(arxiv_ids)} 篇论文的引用数据..."
        )

        # Step 2: 批量查询 Semantic Scholar
        citation_data_map = self.ss_client.get_papers_batch(arxiv_ids)

        # Step 3: 组装结果
        for i, paper in enumerate(papers):
            arxiv_id = arxiv_ids[i]
            citation_data = citation_data_map.get(arxiv_id)

            # 转换为候选论文格式
            candidate_dict = convert_arxiv_to_candidate(paper, citation_data)
            enriched_papers.append(candidate_dict)

            # 进度回调
            if progress_callback:
                progress_callback(i + 1, len(papers), candidate_dict["title"])

        logger.info(
            f"[Search Agent] 引用数据获取完成，"
            f"成功增强 {len(enriched_papers)} 篇论文"
        )
        return enriched_papers

    def enrich_with_crossref(
        self,
        papers: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        使用 CrossRef API 确认论文是否已正式发表，并更新 venue 字段。

        对于已在期刊发表的 arXiv 论文，将 venue 从 "arXiv" 更新为实际期刊名。

        Args:
            papers: 论文字典列表
            progress_callback: 进度回调函数

        Returns:
            更新后的论文字典列表
        """
        if not papers:
            return papers

        logger.info(
            f"[Search Agent] 正在通过 CrossRef 确认 {len(papers)} 篇论文的发表状态..."
        )

        confirmed_count = 0

        for i, paper in enumerate(papers):
            # 提取 arXiv ID (去掉 "arXiv:" 前缀)
            paper_id = paper.get("paper_id", "")
            if paper_id.startswith("arXiv:"):
                arxiv_id = paper_id.replace("arXiv:", "")
            else:
                arxiv_id = paper_id

            title = paper.get("title", "")
            authors = paper.get("authors", [])

            try:
                pub_info = self.crossref_client.get_publication_info(
                    arxiv_id=arxiv_id,
                    title=title,
                    authors=authors
                )

                if pub_info.get("is_published") and pub_info.get("venue"):
                    # 更新 venue 为确认的期刊名
                    original_venue = paper.get("venue", "arXiv")
                    paper["venue"] = pub_info["venue"]
                    confirmed_count += 1
                    logger.info(
                        f"[Search Agent] CrossRef 确认发表: '{title[:40]}...' "
                        f"arXiv -> {pub_info['venue']}"
                    )

                # 保存 DOI (如果有)
                if pub_info.get("doi"):
                    paper["doi"] = pub_info["doi"]

            except Exception as e:
                logger.warning(f"CrossRef 查询失败 [{title[:30]}...]: {e}")

            # 进度回调
            if progress_callback:
                progress_callback(i + 1, len(papers), title)

        logger.info(
            f"[Search Agent] CrossRef 确认完成: "
            f"{confirmed_count}/{len(papers)} 篇论文已正式发表"
        )
        return papers

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

        # Step 3: CrossRef 确认发表状态
        enriched_papers = self.enrich_with_crossref(enriched_papers)

        # Step 4: 持久化
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
