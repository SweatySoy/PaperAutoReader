# Role (角色定义)
你现在是一名“资深数据工程师与 API 集成专家（Senior Data Engineer & API Expert）”。你精通 Python 的异步/同步网络请求、反爬虫策略应对、API 速率限制处理以及复杂 JSON/XML 数据的清洗。

# Context (上下文)
请仔细阅读我项目根目录 `rules/` 文件夹下的所有 Markdown 和 YAML 契约文件。
我的另一个开发流正在构建基础的 `models.py`（包含了 `CandidatePaper` 的 Pydantic 模型）和 `config_loader.py`。
**你可以假设这两个文件已经存在，并且可以通过 `from src.models import CandidatePaper` 和 `from src.config_loader import config` 进行导入。**

# Task (当前任务)
你的任务是为我的态势感知系统开发 **Agent 1: Data Ingestion (Search Agent)**。
请帮我编写 `src/agents/search_agent.py`。

# Core Responsibilities & Logic (核心职责与逻辑)
1. **多源数据抓取**: 
   - 读取 `config` 中的 `keywords_scoring` 和 `impact_entities`。
   - 构造 Query 去调用 **arXiv API** (可以使用 Python 的 `arxiv` 库或直接请求 XML API)，获取最近 N 天的论文。
2. **元数据增强 (Metadata Enrichment)**:
   - 拿到 arXiv 论文后，提取其 ID 或 Title，调用 **Semantic Scholar API** (免费无 Key，或使用官方推荐的速率限制策略)。
   - 从 Semantic Scholar 获取该论文的 `citationCount` 和 `influentialCitationCount`。
   - 检查论文的 Abstract 或链接中是否包含 GitHub 链接，将布尔值赋给 `has_github_link`。
3. **数据清洗与实例化**:
   - 将抓取到的各种脏数据清洗、对齐，最终实例化为一个 `CandidatePaper` 对象的列表 (`List[CandidatePaper]`)。
4. **状态持久化 (Checkpointing)**:
   - 严格遵守 `rules/File_IO_and_Logging.md`。抓取完成后，必须将 `List[CandidatePaper]` 序列化，按日期保存到 `data/raw_papers/YYYY-MM-DD.json` 中。

# Strict Engineering Constraints (严格工程约束)
1. **防崩溃机制 (Resilience)**: 外部 API 极度不稳定。你必须使用 `try-except` 包裹所有网络请求。遇到 Semantic Scholar API 限流（HTTP 429）时，必须实现指数退避重试机制（Exponential Backoff Retry）。
2. **规范日志**: 严禁使用 `print()`。必须使用 `logging`，并规范输出如：“[Search Agent] 成功从 arXiv 抓取 50 篇论文，正在获取引用数据...”。
3. **完全解耦**: 你的代码里**不准**硬编码 "Quantum" 等词汇，所有的检索 Query 必须是由 config 动态拼接生成的。

# Output Deliverables (交付物)
1. 请输出 `src/agents/search_agent.py` 的完整代码。
2. 编写一个 `test_search.py`，写一个只抓取 2 篇论文的极简测试用例，证明你的 API 链路是通的，且能成功生成 JSON 文件。


请将我们的每次对话记录保存在chat_log/search目录下。


# 优化需求！！！
CTO 架构审查意见：
在获取论文引用数据时，绝对禁止在 for 循环中逐篇请求 Semantic Scholar API！这会引发严重的 N+1 性能问题并触发限流。
请你修改代码，必须使用 Semantic Scholar 的 Batch API 进行批量查询：
收集 ID：从 arXiv 获取完所有候选论文后，提取它们的 arXiv ID，拼接成 S2 要求的格式（例如 ARXIV:2401.12345），组成一个列表。
批量请求：向 https://api.semanticscholar.org/graph/v1/paper/batch 发送 POST 请求。
请求体格式：{"ids": ["ARXIV:id1", "ARXIV:id2", ...]}。
URL 参数：记得带上 ?fields=citationCount,influentialCitationCount。
数据对齐：拿到批量返回的 JSON 数组后，根据 ID 将引用数据映射回对应的 CandidatePaper 对象中。
请重新调整这部分逻辑，并确保加上针对 POST 请求的 try-except 容错。如果没有查到某篇论文的引用（返回 null），将其默认值设为 0。

