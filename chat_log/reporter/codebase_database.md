# PaperReader4 Codebase Database

## 项目信息
- **分支**: main (PaperReader4 worktree)
- **更新时间**: 2026-03-25
- **Python 路径**: `/home/xxf/vibe-coding-workspace/PaperReader4`

---

## 目录结构

```
PaperReader4/
├── src/
│   ├── __init__.py
│   ├── models.py                    # 数据模型
│   ├── config_loader.py             # 配置管理
│   ├── filter_agent.py              # Filter Agent (双轴评分)
│   ├── test_filter.py                # Filter 测试
│   └── agents/
│       ├── __init__.py
│       ├── search_agent.py          # Search Agent (数据获取)
│       └── report_agent.py          # Report Agent (报告生成)
├── fields/
│   └── Domain_Profile_QML.yaml      # 领域配置文件
├── rules/
│   ├── Data_Schemas_Contract.md     # 数据契约
│   ├── File_IO_and_Logging.md       # 文件IO文档
│   └── System_Architecture_PRD.md   # 系统架构文档
├── chat_log/                        # 开发日志
├── chatlog_reports/                  # 代码数据库 (本目录)
├── reports/                          # 生成的报告输出
├── test_search.py                    # Search Agent 测试
└── test_report.py                   # Report Agent 测试
```

---

## 数据模型 (models.py)

| 类名 | 继承 | 用途 | 关键字段 |
|------|------|------|----------|
| `QuadrantCategory` | Enum | 四象限分类枚举 | CROWN_JEWEL, CORE_TRACK, IMPACT_TRACK, REJECTED |
| `CandidatePaper` | BaseModel | 原始论文（arXiv/Semantic Scholar） | paper_id, title, abstract, authors, venue, url, citation_count, influential_citation_count, has_github_link |
| `ScoredPaper` | CandidatePaper | 经 Filter Agent 双轴评分后的论文 | core_score, impact_score, quadrant_category, routing_reason |
| `AnalyzedPaper` | ScoredPaper | 经深度分析的论文 | analysis_summary, extracted_methods, impact_briefing, rejection_note |
| `FinalReport` | BaseModel | 最终报告 | report_date, crown_jewels, core_papers, impact_papers, rejected_papers_log |

---

## 配置管理 (config_loader.py)

### Class: `Config` (单例模式)

| 方法/属性 | 用途 |
|-----------|------|
| `get_instance(config_path)` | 获取单例实例 |
| `_load_config()` | 从 YAML 加载配置 |
| `reload(config_path)` | 强制重载配置 |
| `to_dict()` | 导出配置为字典 |
| `profile_name` | 研究档案名称 |
| `core_threshold` | Core Score 阈值 (默认 70) |
| `impact_threshold` | Impact Score 阈值 (默认 70) |
| `must_have_keywords` | 必须包含关键词 |
| `highly_relevant_keywords` | 高相关关键词 (权重 1.0) |
| `relevant_keywords` | 相关关键词 (权重 0.5) |
| `exclude_keywords` | 排除关键词 (权重 -100) |
| `tier_1_venues`, `tier_2_venues` | 期刊/会议分级 |
| `tier_1_institutions` | 一级研究机构 |
| `vip_authors` | 重要作者 |
| `get_all_venues()` | 获取所有期刊 |
| `is_tier_1_venue(venue)` | 检查是否为一区期刊 |
| `is_vip_author(author)` | 检查是否为 VIP 作者 |

---

## Search Agent (search_agent.py)

### 函数

| 函数 | 用途 |
|------|------|
| `setup_logging()` | 配置日志（控制台 + 文件） |
| `extract_arxiv_id(paper)` | 从 arxiv.Result 提取 arXiv ID |
| `convert_arxiv_to_candidate(arxiv_paper, citation_data)` | 转换 arxiv.Result 为 CandidatePaper |
| `search_papers(days_back, max_results, config_source)` | 便捷搜索函数 |

### Class: `ConfigAdapter`

| 方法 | 用途 |
|------|------|
| `__init__(config_source)` | 初始化适配器 |
| `_load_from_yaml()` | 从 YAML 加载配置 |
| `_default_config()` | 返回默认配置 |
| `keywords_scoring` (property) | 获取关键词评分配置 |
| `impact_entities` (property) | 获取影响实体配置 |
| `build_search_queries()` | 从配置构建 arXiv 搜索查询 |

### Class: `SemanticScholarClient`

| 方法 | 用途 |
|------|------|
| `__init__(api_key)` | 初始化客户端 |
| `_exponential_backoff_retry(url, params)` | 指数退避重试（处理 429 限流） |
| `get_paper_by_arxiv_id(arxiv_id)` | 按 arXiv ID 查询论文引用信息 |
| `search_by_title(title, limit)` | 按标题搜索论文（备选） |

### Class: `GitHubLinkDetector`

| 方法 | 用途 |
|------|------|
| `detect(text)` (classmethod) | 检测文本是否包含 GitHub 链接 |
| `extract_links(text)` (classmethod) | 从文本提取所有 GitHub 链接 |

### Class: `SearchAgent`

| 方法 | 用途 |
|------|------|
| `__init__(config_source, semantic_scholar_key, max_papers_per_query)` | 初始化 |
| `fetch_from_arxiv(days_back, max_results)` | 从 arXiv 获取近期论文 |
| `enrich_with_citations(papers, progress_callback)` | 用 Semantic Scholar 引用数据丰富论文 |
| `save_checkpoint(papers, output_date)` | 将论文持久化到 JSON 文件 |
| `run(days_back, max_results, save_output)` | 执行完整搜索工作流 |

---

## Filter Agent (filter_agent.py)

### Protocols (接口)

| Protocol | 方法 | 用途 |
|----------|------|------|
| `EmbeddingService` | `compute_similarity(text1, text2)` | 计算文本间余弦相似度 |
| `LLMScoringService` | `score_task_relevance(abstract, research_intent)` | 评分论文与研究意图的相关性 |
| `LLMScoringService` | `generate_routing_reason(core_score, impact_score, category, paper)` | 生成路由解释 |

### Class: `TimeDecayCalculator`

| 方法 | 用途 |
|------|------|
| `__init__(config)` | 用配置初始化 |
| `get_paper_age_days(publication_date, current_date)` | 计算论文年龄（天） |
| `get_impact_weights(paper_age_days)` | 基于论文年龄获取影响权重（时间衰减） |
| `compute_citation_velocity(citation_count, paper_age_days)` | 计算月引用速度 |

### Class: `CoreScoreCalculator`

| 方法 | 用途 |
|------|------|
| `__init__(config, embedding_service, llm_service)` | 初始化计算器 |
| `_compute_keyword_score(title, abstract)` | 计算关键词得分 |
| `compute_semantic_score(abstract)` | 计算与研究意图的语义相似度 |
| `compute_task_relevance(abstract)` | 用 LLM 计算任务相关性 |
| `compute_core_score(paper, use_llm)` | 计算总体 Core Score (40%语义 + 30%关键词 + 30%任务) |

### Class: `ImpactScoreCalculator`

| 方法 | 用途 |
|------|------|
| `__init__(config)` | 用配置初始化 |
| `_compute_venue_score(venue)` | 计算期刊得分 (一区=100, 二区=70, 其他=30) |
| `_compute_author_score(authors)` | 计算作者得分 (VIP=100, 其他=50) |
| `_compute_github_score(has_github)` | 计算 GitHub 存在得分 (有=80, 无=20) |
| `_compute_citation_velocity_score(citation_count, paper_age_days)` | 计算引用速度得分 |
| `compute_impact_score(paper, current_date)` | 用时间衰减权重计算总体 Impact Score |

### Class: `QuadrantRouter`

| 方法 | 用途 |
|------|------|
| `__init__(config)` | 用配置初始化 |
| `route(core_score, impact_score)` | 基于双轴分数路由论文到象限 |

### Class: `FilterAgent` (主编排器)

| 方法 | 用途 |
|------|------|
| `__init__(config, embedding_service, llm_service)` | 初始化 Filter Agent |
| `_generate_routing_reason(paper, core_score, impact_score, category)` | 生成路由决策的解释 |
| `score_paper(paper, use_llm)` | 对单篇论文评分并确定象限 |
| `score_papers(papers, use_llm)` | 批量对多篇论文评分 |
| `get_papers_by_category(scored_papers, category)` | 按象限过滤论文 |

---

## Report Agent (report_agent.py)

### Class: `ReportAgent`

| 方法 | 用途 |
|------|------|
| `__init__(output_dir)` | 用输出目录初始化 |
| `generate_report(papers, report_date)` | 从 AnalyzedPaper 列表生成 FinalReport |
| `render_markdown(report)` | 将 FinalReport 渲染为 Markdown 字符串 |
| `_render_header(report)` | 渲染带统计信息的报告头 |
| `_render_crown_jewels(papers)` | 渲染 Crown Jewels 章节（详细格式） |
| `_render_core_track(papers)` | 渲染 Core Track 章节（标准格式） |
| `_render_impact_track(papers)` | 渲染 Impact Track 章节（紧凑格式） |
| `_render_rejected(papers)` | 渲染 Rejected 章节（表格格式） |
| `save_report(report, filename)` | 将报告保存为 Markdown 文件 |
| `run(papers, report_date, filename)` | 完整流程：生成、渲染、保存报告 |

---

## 测试文件

### test_search.py

| 类/函数 | 用途 |
|---------|------|
| `MockCandidatePaper` | 测试用 Mock 数据模型 |
| `MockConfig` | 测试用 Mock 配置对象 |
| `test_arxiv_connection()` | 测试 arXiv API 连接 |
| `test_semantic_scholar_connection()` | 测试 Semantic Scholar API 连接 |
| `test_github_detection()` | 测试 GitHub 链接检测 |
| `test_full_search_workflow()` | 测试完整搜索工作流 |
| `test_config_adapter()` | 测试配置适配器 |
| `run_all_tests()` | 运行所有测试并打印摘要 |

### test_report.py

| 函数 | 用途 |
|------|------|
| `create_mock_papers()` | 为所有象限创建 Mock AnalyzedPaper 数据 |
| `main()` | 运行报告 Agent 测试 |

### test_filter.py (src/test_filter.py)

| 函数 | 用途 |
|------|------|
| `create_mock_papers()` | 创建用于测试的 Mock CandidatePaper 对象 |
| `main()` | 用 Mock 数据运行 Filter Agent 测试 |

---

## 统计汇总

| 类别 | 数量 |
|------|------|
| 源代码文件 | 7 个 Python 文件 (src/) |
| 数据模型类 | 5 个 (QuadrantCategory + 4 个 Paper 模型 + FinalReport) |
| Agent 数量 | 3 个 (SearchAgent, FilterAgent, ReportAgent) |
| Protocol 接口 | 2 个 (EmbeddingService, LLMScoringService) |
| Calculator 类 | 4 个 (TimeDecayCalculator, CoreScoreCalculator, ImpactScoreCalculator, QuadrantRouter) |
| 测试文件 | 3 个 |
| 配置文件 | 1 个 YAML (Domain_Profile_QML.yaml) |
| 文档文件 | 3 个 Markdown |

---

## 配置文件

### Domain_Profile_QML.yaml

位于 `fields/Domain_Profile_QML.yaml`，定义量子机器学习(QML)领域的研究档案，包括：
- 关键词配置（must_have, highly_relevant, relevant, exclude）
- 影响实体（一区/二区期刊, VIP 作者, 一区机构）
- 时间衰减配置（新论文/旧论文阈值）
- 搜索查询模板