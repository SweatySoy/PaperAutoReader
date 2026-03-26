# CODE DATABASE

## 模块概览

本项目 (PaperReader) 是一个**论文态势感知系统 (Research Radar)**，通过多智能体协作对 arXiv 论文进行抓取、评分、分类和深度分析。

## 核心模块

### 1. Search Agent (`src/agents/search_agent.py`)

**功能**: 从 arXiv 抓取论文，获取引用数据，确认发表状态

**输入**: 无 (定时触发)

**输出**: `List[CandidatePaper]` -> `data/raw_papers/YYYY-MM-DD.json`

**关键类**:
- `SearchAgent`: 主入口，协调抓取流程
- `SemanticScholarClient`: 批量获取引用数据 (Batch API)
- `CrossRefClient`: 确认论文发表状态
- `GitHubLinkDetector`: 检测论文中的 GitHub 链接

**API 配置**:
- LLM: MiniMax-M2.7 (不直接使用)
- Embedding: DashScope text-embedding-v1 (不直接使用)

---

### 2. Filter Agent (`src/agents/filter_agent.py`)

**功能**: 对论文进行双轴评分 (Core Score + Impact Score) 和象限分类

**输入**: `List[CandidatePaper]`

**输出**: `List[ScoredPaper]` -> `data/scored_papers/YYYY-MM-DD_HH-MM.json`

**评分公式**:
```
Core Score = 40% × 语义相似度 + 30% × 关键词匹配 + 30% × LLM任务相关性

Impact Score = 时间衰减权重 × (Venue/Author/Github/CitationVelocity)
```

**时间衰减权重**:
- 新论文 (<90天): 50% Venue + 30% Author + 20% Github
- 老论文 (>365天): 20% Venue + 80% Citation Velocity

**象限分类** (阈值: Core ≥ 70, Impact ≥ 70):
- CROWN_JEWEL: High Core + High Impact
- CORE_TRACK: High Core + Low Impact
- IMPACT_TRACK: Low Core + High Impact
- REJECTED: Low Core + Low Impact

**关键类**:
- `FilterAgent`: 主入口
- `CoreScoreCalculator`: 计算 Core Score
- `ImpactScoreCalculator`: 计算 Impact Score
- `TimeDecayCalculator`: 时间衰减权重
- `QuadrantRouter`: 象限分类

---

### 3. Analysis Agent (`src/agents/analysis_agent.py`)

**功能**: 对论文进行深度分析，根据象限生成不同内容

**输入**: `List[ScoredPaper]`

**输出**: `List[AnalyzedPaper]` -> `data/analysis_cache/YYYY-MM-DD.json`

**分析策略**:
- CROWN_JEWEL / CORE_TRACK: 调用 LLM 提取 `analysis_summary` + `extracted_methods`
- IMPACT_TRACK: 调用 LLM 提取 `impact_briefing`
- **REJECTED**: 不调用 LLM，直接生成 `rejection_note` (省钱)

**关键类**:
- `AnalysisAgent`: 主入口
- `LLMClient`: Anthropic SDK 封装，带重试和 JSON 解析
- `PromptAssembler`: 动态组装提示词

**API 配置**:
- LLM: MiniMax-M2.7 (`https://api.minimaxi.com/anthropic`)
- Thinking: 已禁用 (`thinking={"type": "disabled"}`)

---

### 4. Report Agent (`src/agents/report_agent.py`)

**功能**: 生成最终 Markdown 报告

**输入**: `List[AnalyzedPaper]`

**输出**: Markdown 报告 -> `reports/Research_Radar_YYYY-MM-DD.md`

**关键方法**:
- `generate_report(papers, report_date)`: 按象限分类组织论文
- `render_markdown(report)`: 渲染为 Markdown
- `save_report(report, filename)`: 保存到 reports/ 目录
- `run(papers, report_date, filename)`: 完整流程

**报告格式**:
- 👑 Crown Jewels: 详细表格 + 摘要引用块 + 方法列表
- 🎯 Core Track: 标准列表格式
- 🔭 Emerging Impact: 紧凑格式，突出 impact_briefing
- 🗑️ Rejected: 极简表格

---

## 数据模型

```
CandidatePaper (原始论文)
    ↓
ScoredPaper (双轴评分 + 象限分类)
    ↓
AnalyzedPaper (深度分析结果)
```

**CandidatePaper 字段**:
- `paper_id`, `title`, `abstract`, `authors`
- `venue`, `publication_date`, `url`
- `citation_count`, `influential_citation_count`, `has_github_link`

**ScoredPaper 字段** (继承 +):
- `core_score`, `impact_score`
- `quadrant_category` (CROWN_JEWEL / CORE_TRACK / IMPACT_TRACK / REJECTED)
- `routing_reason`

**AnalyzedPaper 字段** (继承 +):
- `analysis_summary` (Core/Crown)
- `extracted_methods` (Core/Crown)
- `impact_briefing` (Impact)
- `rejection_note` (Rejected)

---

## 配置文件

### `llm_key.json`
```json
{
  "api_token": "MiniMax token",
  "url": "https://api.minimaxi.com/anthropic",
  "model": "MiniMax-M2.7",
  "embedding_token": "DashScope token",
  "embedding_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "embedding_model": "text-embedding-v1"
}
```

### `fields/Domain_Profile_QML.yaml`
- 关键词配置 (must_have, highly_relevant, relevant, exclude)
- 影响力实体 (tier_1_venues, tier_1_institutions, vip_authors)
- 评分阈值 (core_threshold, impact_threshold)
- 时间衰减配置 (new_paper_threshold_days, old_paper_threshold_days)

---

## 统一执行程序

### `run_pipeline.py`
完整的端到端执行程序，从搜索到报告生成：

```bash
# 默认执行（昨天的论文）
python run_pipeline.py

# 指定日期
python run_pipeline.py 2024-01-15

# 日期范围
python run_pipeline.py 2024-01-15 2024-01-24

# 指定最大论文数
python run_pipeline.py --max-papers 50
```

---

## 测试代码（已归档）

测试代码已移动到 `deprecated/tests/` 目录：
- `test_search.py` - Search Agent 单元测试
- `test_filter.py` - Filter Agent 集成测试
- `test_analysis.py` - Analysis Agent Mock 测试
- `test_full_pipeline.py` - 全流程测试
- `test_report.py` - Report Agent 测试
- `test_report_from_analysis.py` - 从缓存生成报告测试

---

## 依赖

- **Python**: 3.10+
- **LLM**: anthropic (MiniMax-M2.7)
- **Embedding**: requests (DashScope text-embedding-v1)
- **Data**: pydantic, pyyaml
- **arXiv**: arxiv library
