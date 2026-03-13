# Search Agent Development Log
# Date: 2026-03-11

## Task Summary
Develop `src/agents/search_agent.py` - Data Ingestion Module for PaperAutoReader system.

## Contract Documents Reviewed
1. `rules/System_Architecture_PRD.md` - System architecture and agent responsibilities
2. `rules/Data_Schemas_Contract.md` - CandidatePaper data model definition
3. `rules/File_IO_and_Logging.md` - Checkpoint and logging standards
4. `fields/Domain_Profile_QML.yaml` - Domain configuration (QML)

## Implementation Details

### Core Components
1. **ConfigAdapter**: Dynamically builds search queries from YAML config
   - Reads `keywords_scoring` for must_have, highly_relevant, relevant terms
   - Generates arXiv query strings (ti:, abs:, all: prefixes)
   - NO hardcoded keywords - fully configuration-driven

2. **SemanticScholarClient**: API client with exponential backoff retry
   - MAX_RETRIES = 3
   - BASE_DELAY = 1.0 seconds
   - Handles HTTP 429 (rate limit), 404, timeout errors
   - Queries by arXiv ID, fallback to title search

3. **GitHubLinkDetector**: Regex-based GitHub link detection
   - Pattern: `https?://(?:www\.)?github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+`

4. **SearchAgent**: Main orchestrator
   - `fetch_from_arxiv()`: Multi-query search with date filtering
   - `enrich_with_citations()`: Semantic Scholar metadata enhancement
   - `save_checkpoint()`: JSON serialization to `data/raw_papers/YYYY-MM-DD.json`

### Key Engineering Decisions
- Used `logging` module (not `print()`) with dual output (console + file)
- Timezone-aware datetime for arXiv date filtering (fixed offset-naive comparison)
- Path construction via `pathlib.Path` (no absolute paths)
- Try-except wrapping around all network requests

## Test Results
```
Total: 5/5 tests passed
- arXiv API Connection: PASS
- Semantic Scholar API Connection: PASS
- GitHub Link Detection: PASS
- Config Adapter: PASS
- Full Search Workflow: PASS
```

## Output Files
- `src/agents/search_agent.py` - Main implementation
- `test_search.py` - Test script with Mock classes
- `src/agents/__init__.py` - Module init
- `data/raw_papers/2026-03-11.json` - Generated checkpoint file

## Notes for Other Agents
- Imports `CandidatePaper` and `config` from `src.models` and `src.config_loader`
- If those modules don't exist, test script provides Mock implementations
- Output schema follows `Data_Schemas_Contract.md` CandidatePaper definition

---

## CTO 架构审查优化 (Batch API)

### 问题发现
CTO 审查意见：原代码在 for 循环中逐篇请求 Semantic Scholar API，存在 **N+1 API 浪费问题**：
- 每篇论文发起 1 次 HTTP 请求
- 极易触发 HTTP 429 限流
- 效率极低

### 优化方案
改用 **Semantic Scholar Batch API**:
- Endpoint: `POST https://api.semanticscholar.org/graph/v1/paper/batch`
- Payload: `{"ids": ["ARXIV:id1", "ARXIV:id2", ...]}`
- Params: `?fields=citationCount,influentialCitationCount`
- 限制: 每批最多 500 篇论文

### 优化后效果
| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| API 调用次数 | N 次 | 1 次 |
| 限流风险 | 极高 | 低 |
| 响应时间 | O(N) | O(1) |

### 代码变更
1. 新增 `SemanticScholarClient.get_papers_batch()` 方法
2. 重写 `enrich_with_citations()` 使用批量查询
3. 按顺序映射返回结果 (S2 返回数组顺序与请求一致)
4. 为未找到的论文设置默认值 (citation_count=0)
