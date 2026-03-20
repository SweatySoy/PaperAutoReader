# Filter Agent Development Log
# Date: 2026-03-20

## Task Summary
1. 分析 `EmbeddingService` 和 `LLMScoringService` 的作用
2. 修改 `test_filter.py` 使用 `llm_key.json` 中的阿里云 API 配置
3. 修改 `save_checkpoint()` 避免同一天多次运行时文件覆盖

---

## 1. EmbeddingService 与 LLMScoringService 分析

### EmbeddingService
**不是通过大模型判断相关性**，而是通过**向量嵌入计算语义相似度**。

实现: `OpenAIEmbeddingService` (filter_agent.py:132-217)

- 工作原理: 文本 -> 高维向量 -> 余弦相似度
- 用途: Core Score 中的**语义匹配 (40%权重)**
- 特点:
  - 内置缓存减少 API 调用
  - 未配置 API key 时返回中性值 0.5
  - 比大模型更快、更便宜

### LLMScoringService
**这才是通过大模型判断文章相关性的服务**。

实现: `OpenAILLMScoringService` (filter_agent.py:243-390)

- `score_task_relevance()`: Core Score 中的**任务相关性评分 (30%权重)**
- `generate_routing_reason()`: 生成一句话分类解释

### Core Score 计算公式
```
Core Score = 40% × semantic_score (Embedding)
           + 30% × keyword_score (规则匹配)
           + 30% × task_score (LLM)
```

### 对比总结

| 特性 | EmbeddingService | LLMScoringService |
|------|------------------|-------------------|
| 方法 | 向量嵌入 + 余弦相似度 | 大模型直接打分 |
| 成本 | 低 | 较高 |
| 速度 | 快 | 较慢 |
| 能力 | 语义相似度 | 理解推理、判断任务相关性 |

---

## 2. test_filter.py 修改

### 新增 `load_llm_config()` 函数
```python
def load_llm_config() -> dict:
    """Load LLM configuration from llm_key.json."""
    project_root = Path(__file__).parent
    config_path = project_root / "llm_key.json"
    with open(config_path, "r", encoding="utf-8") as f:
        configs = json.load(f)
    if configs and len(configs) > 0:
        return configs[0]
    return {}
```

### main() 函数修改
- 从 `llm_key.json` 读取阿里云 DashScope API 配置
- 使用 `qwen3-32b` 作为 LLM 模型
- 使用 `text-embedding-v3` 作为 embedding 模型

### 路径修复
```python
# 修复前
json_file = data_dir + "/raw_papers_2026-03-11.json"

# 修复后
json_file = data_dir / "raw_papers_2026-03-11.json"
```

---

## 3. save_checkpoint() 文件去重

### 问题
同一天执行两次会覆盖文件。

### 解决方案
文件名格式变更:
- 旧: `YYYY-MM-DD.json`
- 新: `YYYY-MM-DD_HH-MM.json` (精确到分钟)

### 双重保护机制
1. 文件名包含小时和分钟
2. 同一分钟内多次运行，自动追加序号 `_01`, `_02`

### 示例输出
```
data/scored_papers/
├── 2026-03-20_10-30.json
├── 2026-03-20_14-45.json
├── 2026-03-20_14-45_01.json  # 同一分钟第二次运行
└── 2026-03-20_18-20.json
```

---

## 4. Embedding API 不可用时的降级机制

当 `embedding_service is None` 时:
- `compute_semantic_score()` 返回固定值 50.0
- 语义匹配贡献固定为 20分 (40% × 50)
- 评分依赖关键词匹配 (30%) 和 LLM 任务相关性 (30%)

### 改进建议
如果目标大模型不提供 Embedding API，可让 LLM 合并评估:
```python
prompt = """Evaluate this paper's relevance on two dimensions:
1. Semantic Relevance: Related concepts/terminology?
2. Task Relevance: Same core problem?

Provide a combined score (0-100)."""
```

然后调整权重:
```
Core Score = 60% × LLM_combined_score + 40% × keyword_score
```

---

## Notes
- 阿里云 DashScope 提供了 Embedding API (`text-embedding-v3`)
- 当前代码已支持阿里云 API，可直接运行测试
