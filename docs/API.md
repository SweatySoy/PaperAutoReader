# API Documentation - PaperAutoReader Research Radar System

## Overview

PaperAutoReader is a multi-agent paper intelligence system that:
1. **Search** papers from arXiv based on domain keywords
2. **Filter** papers using dual-axis scoring (Core + Impact)
3. **Analyze** papers with LLM-based deep analysis
4. **Report** the results in a structured Markdown format

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Search     │────▶│   Filter    │────▶│   Analysis  │────▶│   Report    │
│   Agent      │     │   Agent      │     │   Agent      │     │   Agent     │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
CandidatePaper      ScoredPaper       AnalyzedPaper        FinalReport
       │                   │                   │                   │
   raw_papers/       scored_papers/    analysis_cache/         reports/
```

---

## Data Models

### CandidatePaper (State 1)
Raw paper fetched from arXiv before processing.

| Field | Type | Description |
|-------|------|-------------|
| `paper_id` | str | Unique identifier (e.g., arXiv ID) |
| `title` | str | Paper title |
| `abstract` | str | Paper abstract text |
| `authors` | list[str] | List of author names |
| `venue` | str | Publication venue (default: "arXiv") |
| `publication_date` | date | Publication date |
| `url` | str | URL to the paper |
| `citation_count` | int | Total citation count |
| `influential_citation_count` | int | Influential citation count |
| `has_github_link` | bool | Whether paper has GitHub link |

### ScoredPaper (State 2)
Paper after dual-axis scoring by Filter Agent.

| Field | Type | Description |
|-------|------|-------------|
| *(inherited)* | - | All CandidatePaper fields |
| `core_score` | float | Relevance score (0-100) |
| `impact_score` | float | Impact score (0-100) |
| `quadrant_category` | QuadrantCategory | CROWN_JEWEL / CORE_TRACK / IMPACT_TRACK / REJECTED |
| `routing_reason` | str | One-sentence explanation for classification |

### AnalyzedPaper (State 3)
Paper after deep analysis by Analysis Agent.

| Field | Type | Description |
|-------|------|-------------|
| *(inherited)* | - | All ScoredPaper fields |
| `analysis_summary` | str | Summary (for Crown/Core papers) |
| `extracted_methods` | list[str] | Extracted methodologies |
| `impact_briefing` | str | Cross-domain insights (for Impact papers) |
| `rejection_note` | str | Rejection reason (for Rejected papers) |

### QuadrantCategory (Enum)
Four-quadrant classification:

| Value | Description | Criteria |
|-------|-------------|----------|
| `CROWN_JEWEL` | Must-read classics | Core ≥ 70, Impact ≥ 70 |
| `CORE_TRACK` | Daily domain tracking | Core ≥ 70, Impact < 70 |
| `IMPACT_TRACK` | Cross-domain high-impact | Core < 70, Impact ≥ 70 |
| `REJECTED` | Filtered out | Core < 70, Impact < 70 |

---

## Module APIs

### SearchAgent (`src/agents/search_agent.py`)

```python
from src.agents import SearchAgent

agent = SearchAgent(
    max_papers: int = 100,
    date_from: str | None = None,  # "YYYY-MM-DD"
    date_to: str | None = None     # "YYYY-MM-DD"
)
papers: list[CandidatePaper] = agent.run()
```

**Key Methods:**
| Method | Description |
|--------|-------------|
| `run()` | Execute full search pipeline |
| `search_by_keyword(query, max_results)` | Search arXiv by keyword |
| `fetch_citations(paper_ids)` | Batch fetch citation data |
| `save_candidates(papers, filename)` | Save to JSON |

**Usage:**
```python
# Search without date range
agent = SearchAgent(max_papers=50)
papers = agent.run()

# Search with date range
agent = SearchAgent(max_papers=100, date_from="2024-01-15", date_to="2024-01-24")
papers = agent.run()
```

---

### FilterAgent (`src/agents/filter_agent.py`)

```python
from src.agents import FilterAgent

# Configure LLM and Embedding first
configure_llm(api_key="your_llm_key", api_url="https://api.minimaxi.com/anthropic", model="MiniMax-M2.7")
configure_embedding(api_key="your_embedding_key", api_url="https://dashscope.aliyuncs.com/compatible-mode/v1", model="text-embedding-v1")

agent = FilterAgent()
scored_papers: list[ScoredPaper] = agent.filter_papers(candidate_papers)
```

**Key Methods:**
| Method | Description |
|--------|-------------|
| `filter_papers(candidates)` | Score and classify all papers |
| `_calculate_core_score(paper)` | Compute relevance score |
| `_calculate_impact_score(paper)` | Compute impact score |
| `_determine_quadrant(core, impact)` | Route to quadrant |
| `save_scored_papers(papers, filename)` | Save to JSON |

**Scoring Formula:**
```
Core Score = 40% × 语义相似度 + 30% × 关键词匹配 + 30% × LLM任务相关性

Impact Score = 时间衰减权重 × (Venue/Author/Github/CitationVelocity)
```

---

### AnalysisAgent (`src/agents/analysis_agent.py`)

```python
from src.agents import AnalysisAgent

agent = AnalysisAgent()
analyzed_papers: list[AnalyzedPaper] = agent.analyze_papers(scored_papers)
```

**Key Methods:**
| Method | Description |
|--------|-------------|
| `analyze_papers(papers)` | Analyze all papers (calls LLM based on quadrant) |
| `_analyze_crown_or_core(paper)` | Deep analysis for Crown/Core |
| `_analyze_impact(paper)` | Impact briefing for Impact Track |
| `_reject_paper(paper)` | Short note for Rejected (no LLM call) |
| `save_analysis(papers, filename)` | Save to JSON |

**Analysis Strategy:**
- **CROWN_JEWEL / CORE_TRACK**: Calls LLM for `analysis_summary` + `extracted_methods`
- **IMPACT_TRACK**: Calls LLM for `impact_briefing`
- **REJECTED**: No LLM call (cost-saving)

---

### ReportAgent (`src/agents/report_agent.py`)

```python
from src.agents import ReportAgent

agent = ReportAgent(output_dir="reports/")
report, filepath = agent.run(papers=analyzed_papers, report_date=date.today())
```

**Key Methods:**
| Method | Description |
|--------|-------------|
| `generate_report(papers, report_date)` | Create FinalReport from AnalyzedPapers |
| `render_markdown(report)` | Render as Markdown string |
| `save_report(report, filename)` | Save to .md file |
| `run(papers, report_date, filename)` | Full pipeline |

**Report Output Format:**
```
📊 Research Radar Report
├── 👑 Crown Jewels (核心必读)
│   └── Detailed table + summary + methods
├── 🎯 Core Track (领域跟进)
│   └── Standard list format
├── 🔭 Emerging Impact (跨界高影响)
│   └── Compact format with impact_briefing
└── 🗑️ Rejected Pipeline (已滤除)
    └── Minimal table
```

---

## Unified Pipeline (`run_pipeline.py`)

```python
from run_pipeline import run_full_pipeline

# Run with date range
report_path = run_full_pipeline(
    date_from="2024-01-15",
    date_to="2024-01-24",
    max_papers=50,
    output_dir="reports/"
)
```

**Pipeline Steps:**
1. **Search**: Fetch papers from arXiv
2. **Filter**: Score with Core + Impact, classify into quadrants
3. **Analysis**: Deep analysis based on quadrant
4. **Report**: Generate Markdown report

---

## Configuration

### llm_key.json
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

### fields/Domain_Profile_QML.yaml
Domain-specific configuration including:
- Keywords (must_have, highly_relevant, relevant, exclude)
- Venues (tier_1_venues)
- Authors (vip_authors)
- Thresholds (core_threshold, impact_threshold)

---

## File Output Paths

| Stage | Default Path |
|-------|-------------|
| Raw Papers | `data/raw_papers/YYYY-MM-DD.json` |
| Scored Papers | `data/scored_papers/YYYY-MM-DD_HH-MM.json` |
| Analysis Cache | `data/analysis_cache/YYYY-MM-DD.json` |
| Reports | `reports/Research_Radar_YYYY-MM-DD.md` |
| Logs | `logs/system_YYYY-MM-DD.log` |

---

## Error Handling

All agents implement:
- **Timeout**: LLM calls timeout after 60 seconds
- **Retry**: Exponential backoff (max 3 retries)
- **Fallback**: Return graceful degradation on failure

---

## Dependencies

```yaml
python: 3.10+
anthropic: LLM client (MiniMax-M2.7)
requests: HTTP client for embeddings
pydantic: Data validation
pyyaml: Configuration
arxiv: arXiv API client
```
