# PaperReader 项目交接文档
# PaperAutoReader - Research Radar System
# 最后更新: 2026-03-26

---

## 一、项目概述

PaperReader 是一个**论文态势感知系统 (Research Radar)**，通过多智能体协作架构对 arXiv 论文进行全自动抓取、评分、分类和深度分析。

### 核心流程 (Search → Filter → Analysis)
```
arXiv API → Search Agent → CandidatePaper[]
                                    ↓
                    Filter Agent → ScoredPaper[]
                                    ↓
                    Analysis Agent → AnalyzedPaper[] → Report
```

### 数据生命周期
```
CandidatePaper (原始论文)
    ↓ Filter Agent (双轴评分 + 象限分类)
ScoredPaper (含 core_score, impact_score, quadrant_category)
    ↓ Analysis Agent (象限差异化分析)
AnalyzedPaper (含 analysis_summary / impact_briefing / rejection_note)
```

---

## 二、目录结构

```
PaperReader/
├── src/
│   ├── __init__.py
│   ├── models.py              # Pydantic 数据模型
│   ├── config_loader.py       # YAML 配置加载器
│   ├── filter_agent.py        # 评分 + 分类逻辑
│   └── agents/
│       ├── search_agent.py     # 数据抓取
│       └── analysis_agent.py   # 深度分析
├── fields/
│   └── Domain_Profile_QML.yaml # 领域配置 (关键词、阈值等)
├── data/
│   ├── arxiv_by_date/         # 按日期存储的原始论文
│   ├── raw_papers/            # Search Agent 输出
│   ├── scored_papers/         # Filter Agent 输出
│   └── analysis_cache/        # Analysis Agent 输出
├── chat_log/                  # 开发日志
│   ├── search/
│   ├── filter/
│   └── analyst/
├── test_*.py                 # 各模块测试
├── llm_key.json              # API 密钥配置
├── WORK_LOG.md               # 工作记录
└── CODE_DATABASE.md          # 代码知识库
```

---

## 三、API 配置

### 3.1 LLM (MiniMax)
```json
{
  "api_token": "sk-cp-qIzaPt7uZRFvCYVdBKKfmeXnskav_...",
  "url": "https://api.minimaxi.com/anthropic",
  "model": "MiniMax-M2.7"
}
```
- **用途**: Filter Agent 的 LLM 评分、Analysis Agent 的深度分析
- **关键**: MiniMax-M2.7 返回 `ThinkingBlock`，需要禁用 thinking

### 3.2 Embedding (DashScope)
```json
{
  "embedding_token": "sk-aa0df20068414ebe84e327dc2035ec0f",
  "embedding_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "embedding_model": "text-embedding-v1"
}
```
- **用途**: Filter Agent 的语义相似度计算
- **注意**: 模型名是 `text-embedding-v1`，不是 `qwen3-vl-embedding`

### 3.3 配置文件位置
- `PaperReader/llm_key.json` - API 密钥
- `PaperReader/fields/Domain_Profile_QML.yaml` - 领域配置

---

## 四、核心模块详解

### 4.1 Search Agent (`src/agents/search_agent.py`)

**职责**: 从 arXiv 抓取论文，获取引用数据，确认发表状态

**关键类**:
- `SearchAgent`: 主入口
- `SemanticScholarClient.get_papers_batch()`: **批量**获取引用数据 (Batch API，POST `/paper/batch`)
- `CrossRefClient`: 确认论文是否正式发表
- `GitHubLinkDetector`: 检测 GitHub 链接

**输出**: `data/raw_papers/YYYY-MM-DD.json`

### 4.2 Filter Agent (`src/filter_agent.py`)

**职责**: 双轴评分 + 象限分类

**评分公式**:
```
Core Score = 40% × 语义相似度 (Embedding) + 30% × 关键词匹配 + 30% × LLM任务相关性
Impact Score = 时间衰减权重 × 各维度
```

**时间衰减权重**:
| 论文年龄 | Venue | Author | Github | Citation Velocity |
|---------|-------|--------|--------|------------------|
| <90天 (新) | 50% | 30% | 20% | 0% |
| >365天 (老) | 20% | 0% | 0% | 80% |
| 中间 | 线性插值 | | | |

**象限分类** (阈值默认 70):
| 象限 | 条件 |
|------|------|
| CROWN_JEWEL | Core ≥ 70 AND Impact ≥ 70 |
| CORE_TRACK | Core ≥ 70 AND Impact < 70 |
| IMPACT_TRACK | Core < 70 AND Impact ≥ 70 |
| REJECTED | Core < 70 AND Impact < 70 |

**输出**: `data/scored_papers/YYYY-MM-DD_HH-MM.json`

### 4.3 Analysis Agent (`src/agents/analysis_agent.py`)

**职责**: 深度分析，基于象限差异化处理

**关键优化 - REJECTED 短路**:
```python
if category == QuadrantCategory.REJECTED:
    # 不调用 LLM，直接生成 rejection_note (省钱!)
    analysis_result = {
        "rejection_note": self._generate_rejection_note(paper)
    }
```

**象限差异化 Prompt**:
- CROWN_JEWEL / CORE_TRACK: 提取 `analysis_summary` + `extracted_methods`
- IMPACT_TRACK: 提取 `impact_briefing`
- REJECTED: 直接生成 `rejection_note`

**输出**: `data/analysis_cache/YYYY-MM-DD.json`

---

## 五、运行命令

### 5.1 环境
```bash
conda run -n QML python <script.py>
conda run -n QML pytest
```

### 5.2 测试
```bash
# 单元测试
conda run -n QML pytest test_search.py
conda run -n QML pytest test_analysis.py

# 集成测试 (108篇论文，会很慢)
conda run -n QML python test_filter.py

# 日期范围抓取
conda run -n QML python test_search_date_range.py
```

### 5.3 数据
```bash
# 查看原始论文
ls data/arxiv_by_date/
ls data/raw_papers/

# 查看已评分论文
ls data/scored_papers/

# 查看分析结果
ls data/analysis_cache/
```

---

## 六、已知问题与限制

### 6.1 API 问题
1. **MiniMax Thinking**: MiniMax-M2.7 返回 ThinkingBlock，必须使用 `thinking={"type": "disabled"}` 禁用
2. **DashScope Embedding 模型名**: 必须是 `text-embedding-v1`，`qwen3-vl-embedding` 在 OpenAI 兼容模式下不支持

### 6.2 业务限制
1. **REJECTED 论文打分偏低**: 由于 Core Score 计算依赖 Embedding 和关键词匹配，部分量子物理相关论文可能因配置不当被误判
2. **Citation Velocity**: 老论文 (>1年) 的 Impact Score 主要依赖引用，但新论文引用数少会影响评分

### 6.3 测试环境
1. 运行 `test_filter.py` 处理 108 篇论文时较慢 (每篇调用 LLM/Embedding)
2. 测试环境需要安装: `pydantic`, `requests`, `arxiv`, `anthropic`, `pyyaml`

---

## 七、代码规范 (来自 CLAUDE.md)

1. **TDD 工作流**: 先写测试 → 验证失败 → 编写实现 → 重构
2. **代码格式化**: `black .`
3. **类型检查**: `mypy .`
4. **Docstring**: Google 风格，必须包含
5. **绝对导入**: 避免隐式相对导入
6. **日志规范**: 使用 `logging` 而非 `print()`

---

## 八、文档位置

| 文档 | 路径 | 用途 |
|------|------|------|
| WORK_LOG | `WORK_LOG.md` | 工作记录，每次修改后追加 |
| CODE_DATABASE | `CODE_DATABASE.md` | 代码知识库，核心类说明 |
| chat_log | `chat_log/*/` | 各 Agent 开发日志 |
| 本文档 | `HANDOVER.md` | 项目交接 |

---

## 九、最近修改 (2026-03-25/26)

### MiniMax LLM 集成
- **变更**: LLM 从阿里云 DashScope 切换到 MiniMax-M2.7
- **原因**: 阿里云 API 欠费
- **文件**:
  - `llm_key.json`: 更新 API 配置
  - `src/agents/analysis_agent.py`: Anthropic SDK + ThinkingBlock 处理
  - `src/filter_agent.py`: 同上
  - `test_filter.py`, `test_analysis.py`: 测试更新

### 关键修复
1. **Thinking 禁用**: `thinking={"type": "disabled"}`
2. **Embedding 模型**: `text-embedding-v1` (不是 `qwen3-vl-embedding`)
3. **REJECTED 短路**: 已验证工作正常

### 测试结果
- `pytest test_search.py`: 5 passed
- `pytest test_analysis.py`: 1 passed
- 完整流程测试 (5篇): PASSED

---

## 十、给下一个 Agent 的话

你好！接手这个项目时请注意：

1. **API 配置在 `llm_key.json`**，不要硬编码
2. **运行测试前先安装依赖**: `conda run -n QML pip install pydantic requests arxiv anthropic pyyaml`
3. **MiniMax 需要禁用 thinking**，否则返回的内容包含思考过程
4. **Embedding 用 `text-embedding-v1`**，这是 DashScope OpenAI 兼容模式的正确模型名
5. **REJECTED 论文不调用 LLM**，这是设计好的省钱机制
6. **如果遇到 404 on embeddings**，先测试 endpoint 是否正确

祝顺利！
