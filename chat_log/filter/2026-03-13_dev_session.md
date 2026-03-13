# Filter Agent Development Log
# Date: 2026-03-13

## Task Summary
将 filter 相关程序代码变成可用状态，实现 EmbeddingService 和 LLMScoringService。

## Implementation Details

### 1. LLM Service Configuration (Global Variables)

使用全局变量配置 LLM 和 Embedding 服务，减少初始化工作量:

```python
# Global configuration for LLM services
LLM_API_KEY: str = ""
LLM_API_URL: str = "https://api.openai.com/v1"
LLM_MODEL: str = "gpt-3.5-turbo"

EMBEDDING_API_KEY: str = ""
EMBEDDING_API_URL: str = "https://api.openai.com/v1"
EMBEDDING_MODEL: str = "text-embedding-ada-002"
```

配置函数:
- `configure_llm(api_key, api_url, model)` - 配置 LLM 服务
- `configure_embedding(api_key, api_url, model)` - 配置 Embedding 服务

### 2. OpenAIEmbeddingService Implementation

具体实现了 `EmbeddingService` Protocol:

- `compute_similarity(text1, text2) -> float` - 计算两段文本的余弦相似度
- 内置 embedding 缓存，减少 API 调用
- 自动截断超长文本 (max 8000 chars)
- 未配置 API key 时返回中性值 0.5

### 3. OpenAILLMScoringService Implementation

具体实现了 `LLMScoringService` Protocol:

- `score_task_relevance(abstract, research_intent) -> float` - LLM 评分相关性 (0-100)
- `generate_routing_reason(...) -> str` - 生成分类理由说明
- 未配置 API key 时使用 mock 逻辑生成理由

### 4. FilterAgent Enhancements

新增方法:
- `save_checkpoint(scored_papers, output_path, date_str)` - 保存到 `data/scored_papers/YYYY-MM-DD.json`
- `load_checkpoint(input_path)` - 从 checkpoint 加载 (classmethod)

### 5. Factory Function

```python
def create_filter_agent(
    llm_api_key: str = "",
    llm_api_url: str = "https://api.openai.com/v1",
    llm_model: str = "gpt-3.5-turbo",
    embedding_api_key: str = "",
    embedding_api_url: str = "https://api.openai.com/v1",
    embedding_model: str = "text-embedding-ada-002",
    config: Config | None = None
) -> FilterAgent
```

推荐的生产环境使用方式。

### 6. Test Script Updates

`test_filter.py` 支持:
- `--real` - 使用真实 LLM/Embedding 服务
- `--llm-api-key` - LLM API key
- `--embedding-api-key` - Embedding API key
- `--llm-url` - LLM API URL
- `--embedding-url` - Embedding API URL
- `--llm-model` - LLM 模型名
- `--embedding-model` - Embedding 模型名

## Test Results

```
Loaded 23493 real papers from data/raw_papers/
Summary by Category:
  CROWN_JEWEL: 0 paper(s)
  CORE_TRACK: 0 paper(s)
  IMPACT_TRACK: 1 paper(s)
  REJECTED: 23492 paper(s)
Saved to: data/scored_papers/2026-03-13.json
```

## Notes

- 大部分论文被 REJECTED 是因为 Mock 模式下 semantic_score 和 task_score 都是中性值 50.0
- 需要配置真实的 LLM/Embedding API key 才能得到更准确的分类
- 已遵循 `File_IO_and_Logging.md` 的断点续传规范
