# Data Schemas & Pipeline Contract
# 全局数据契约与流水线状态流转定义

所有的 Agent（Search, Filter, Analysis, Report）必须严格遵守以下定义在 `models.py` 中的 Pydantic 数据结构进行输入输出，严禁擅自更改键名（Keys）或数据类型（Types）。

## 1. 论文的生命周期 (The Data Pipeline)
一篇论文在系统中的流转，本质上是它的“状态（State）”不断被丰富的过程。类的继承关系完美契合这个逻辑：
`CandidatePaper` -> `ScoredPaper` -> `AnalyzedPaper`

## 2. 核心数据模型 (Pydantic Models)

请 AI 编程助手使用 `pydantic` 严格实现以下数据类：

### 状态 1: CandidatePaper (Search Agent 的输出 / Filter Agent 的输入)
代表从 arXiv 或 Semantic Scholar 刚抓取下来的、未经任何处理的原始论文。
- `paper_id`: str (例如 arXiv ID)
- `title`: str
- `abstract`: str
- `authors`: list[str]
- `venue`: str (期刊/会议名称，如果没有则为 "arXiv")
- `publication_date`: datetime.date (用于计算 age 和 time-decay weight)
- `url`: str
- `citation_count`: int (默认 0)
- `influential_citation_count`: int (默认 0)
- `has_github_link`: bool (默认 False)

### 状态 2: ScoredPaper (Filter Agent 的输出 / Analysis Agent 的输入)
继承自 `CandidatePaper`，由 Filter Agent 注入了打分信息和象限分类。
- 继承 `CandidatePaper` 的所有字段
- `core_score`: float (0.0 - 100.0)
- `impact_score`: float (0.0 - 100.0)
- `quadrant_category`: Enum (必须是四者之一：`CROWN_JEWEL`, `CORE_TRACK`, `IMPACT_TRACK`, `REJECTED`)
- `routing_reason`: str (Filter Agent 生成的一句话解释，例如："Impact 极高是因为作者来自 MIT 且发在 Nature")

### 状态 3: AnalyzedPaper (Analysis Agent 的输出 / Report Agent 的输入)
继承自 `ScoredPaper`，由 Analysis Agent 根据不同的象限，注入了深度解读内容。
- 继承 `ScoredPaper` 的所有字段
- `analysis_summary`: str (根据不同象限生成的摘要文本)
- `extracted_methods`: list[str] (主要针对 Core / Crown Jewel 提取的方法论)
- `impact_briefing`: str (主要针对 Impact Track 提取的跨界启发)
- `rejection_note`: str (主要针对 Rejected 提取的忽略理由)

### 状态 4: FinalReport (Report Agent 的输出)
用于渲染最终发送给用户的报告。
- `report_date`: datetime.date
- `crown_jewels`: list[AnalyzedPaper]
- `core_papers`: list[AnalyzedPaper]
- `impact_papers`: list[AnalyzedPaper]
- `rejected_papers_log`: list[AnalyzedPaper]