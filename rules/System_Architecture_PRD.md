# PaperAutoReader: Scientific Situational Awareness System
# 系统需求文档与 Agent 架构指南

## 1. System Overview (系统概述)
本项目不是一个简单的文献检索工具，而是一个**“领域态势感知系统（Research Radar）”**。
核心机制是通过双轴评分（Core Score 和 Impact Score）将每日/每周的最新论文（主要来源于 arXiv、Semantic Scholar 等）自动分类至四大象限，并生成结构化分析报告。

## 2. Dual-Axis Scoring Logic (双轴评分系统设计)
系统必须为每篇候选论文独立计算两个维度的分数（0-100）。

### 2.1 Core Score ($S_{core}$, 相关度, 0-100)
完全依赖大语言模型（LLM）的语义分析和向量检索。
- **语义匹配 (40%)**: 论文 Abstract 与 User Research Profile 的文本 Embedding 余弦相似度。
- **技术栈吻合度 (30%)**: 关键词匹配（如 Quantum 领域的特定算法/框架）。
- **任务目标重叠 (30%)**: LLM Prompt 打分（判断是否解决相同核心科学问题）。

### 2.2 Impact Score ($S_{impact}$, 影响力, 0-100)
由多维度元数据（Metadata）融合打分，支持随“论文发布时间”动态切换权重。
- **信号获取来源（自动化可行版）**:
  - $S_{venue}$: 匹配 YAML 配置文件中的顶级期刊/会议列表。
  - $S_{author}$: 匹配 YAML 配置文件中的顶级机构和 VIP 作者名单。
  - $S_{github}$: 论文内是否包含 GitHub 链接，且 Star 数量/增长如何（调用 GitHub API）。
  - $S_{citation}$: 调用 Semantic Scholar API 获取 `citationCount` 和 `influentialCitationCount`。

- **时间衰减权重 (Time-Decay Weighting)**:
  - **新论文（Age < 3个月）**: $S_{impact}$ = 50% Venue + 30% Author + 20% Github Traction
  - **老论文（Age > 1年）**: $S_{impact}$ = 20% Venue + 80% Citation Velocity (月均引用率)

## 3. Quadrant Routing System (论文分流与路由逻辑)
根据评分，将论文分发至对应的分析流（Threshold 默认设为 70，需在 config 中可配）：

| Core | Impact | Classification | Action Flow |
| :--- | :--- | :--- | :--- |
| High | High | 👑 **Crown Jewels** | **Deep Analysis (Max)**：精读方法、提取公式/代码思路，置于报告顶部。 |
| High | Low | 🎯 **Core Track** | **Deep Analysis (Std)**：分析 Method 和与现有工作的对比。 |
| Low | High | 🔭 **Impact Track** | **Impact Briefing**：仅提取核心突破点及对本领域的跨界启发（不看细节）。 |
| Low | Low | 🗑️ **Rejected** | **Short Note**：记录入库，生成一句话拒稿理由，便于未来复盘追溯。 |

## 4. Multi-Agent Architecture (多智能体协作架构)

建议在代码中使用类似 LangChain/CrewAI/AutoGen 的框架，或手写清晰的流程。

### Agent 1: Search & Fetch Agent (数据获取)
- **职责**: 定时（Cron）抓取 arXiv API, Semantic Scholar API。
- **输入**: Query 列表或关注的 Authors 列表。
- **输出**: 标准化 JSON 格式的 Candidate Papers (Title, Abstract, Authors, URL, Date)。

### Agent 2: Filter & Score Agent (双轴评分)
- **职责**: 执行上述的打分逻辑。
- **核心逻辑**:
  1. 调用 Embedding 模型计算 $S_{core}$ 的语义分。
  2. 请求 LLM 进行 Task/Method Match 评分。
  3. 解析 Metadata 计算 $S_{impact}$。
- **输出**: 附带 `core_score`, `impact_score` 及分类标签（Core/Impact/Rejected）的 Paper List。

### Agent 3: Analysis Agent (深度解析)
- **职责**: 根据 Agent 2 给出的标签，动态决定 Prompt 策略。
- **Prompts**:
  - If `Crown Jewels` / `Core`: 提示词侧重于“技术路线重构”、“创新点提炼”、“缺陷分析”。
  - If `Impact`: 提示词侧重于“用费曼技巧解释该突破”、“可能对当前领域产生的连锁反应”。
  - If `Rejected`: 提取 1 句话概述为什么该论文不值得读。

### Agent 4: Report Generation Agent (报告生成)
- **职责**: 聚合结果，生成最终的 Markdown / HTML / PDF 态势感知报告。
- **格式结构**:
  1. Crown Jewels (必读经典)
  2. Core Papers (日常领域跟进)
  3. Emerging Impact (跨界高影响)
  4. Rejected Pipeline (被滤除记录清单)

## 5. Configuration Strategy (配置驱动化)
整个系统必须是可配置的。要求 AI 编写一个 `config.yaml` 模板。
包含：
- 评分阈值（Core threshold, Impact threshold）
- 目标关键词表（Must-include, Must-exclude）
- 顶级机构白名单（Tier 1 Institutions）
- VIP 作者白名单（Tier 1 Authors）

## 6. Future Expansion: Trend Detection (趋势发现预留接口)
系统需要在数据库中保存所有记录。要求底层数据结构能支持按时间线聚合，通过计算特定 Keywords 或 Topic Cluster 下 $S_{impact}$ 突然飙升的模式，在未来实现趋势告警。

