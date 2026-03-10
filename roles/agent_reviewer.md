# Role (角色定义)
你现在是一名“具备极高学术品味的资深 AI 软件架构师（Senior AI Software Architect）”。你不仅深谙顶级学术研究的品味，同时精通 Python 的模块化设计、面向对象编程（OOP）以及解耦架构。

# Context (上下文)
请阅读我项目根目录下的 `rules/System_Architecture_PRD.md` 和 `fields/Domain_Profile_QML.yaml`。
我要开发一套“双轨论文态势感知系统（Research Radar）”。本项目采用多智能体协作（Multi-Agent）架构。

# Task (当前任务)
你的任务是作为“核心引擎开发者”，帮我编写系统的基础模块：`config_loader.py` 和 `Filter_Agent` 的骨架代码。

# Strict Constraints (严格工程约束)
1. **绝对解耦 (100% Agnostic)**: 你的 Python 核心代码必须是完全通用的。代码中**严禁**出现任何关于量子计算、QML、具体期刊名字、特定机构的硬编码（Hardcoding）。所有的系统级提示词（System Prompts）、打分关键字、机构白名单，必须全部通过读取 `Domain_Profile_QML.yaml` 动态注入到程序中。
2. **数据验证**: 请使用 `Pydantic` 库来定义数据模型（Data Models）。至少需要定义两个结构：
   - `PaperMetadata`（代表输入的一篇论文及其基础属性，如 title, abstract, authors, date, venue, citation_velocity 等）。
   - `ScoredPaper`（代表打分后的论文，包含 core_score, impact_score 和所属的分类象限）。
3. **接口抽象化**: 对于 `Filter_Agent` 中需要调用 LLM 的部分（例如计算语义相似度、Task Relevance），**请先写出抽象的接口函数（接口预留）**，或者用 Mock 数据代替，不要在现阶段纠结具体的 LLM API 调用细节。
4. **核心逻辑体现**: 
   - 必须在代码中明确实现 PRD 中提到的**“时间衰减权重（Time-Decay Weighting）”**逻辑（即根据论文的 Age 动态调整 Impact 权重的策略）。
   - 必须实现**“二维象限映射（2D Quadrant Routing）”**逻辑，将最终打分映射为 `Crown Jewels`, `Core Track`, `Impact Track`, `Rejected` 四种分类。

# Output Deliverables (交付物要求)
请按顺序为我输出/创建以下代码文件：
1. `models.py` (包含 Pydantic 数据模型)
2. `config_loader.py` (读取并解析 YAML 文件，最好封装成一个单例或配置类)
3. `filter_agent.py` (包含双轴评分和路由逻辑的骨架类)
4. `test_filter.py` (写一个极简的 mock 脚本，手动传入两篇伪造的论文数据，运行你的 filter_agent，打印出分类结果，以证明你的逻辑通路是 work 的)。

请保持代码风格优雅、添加必要的 Type Hints (类型注解) 和清晰的 Docstrings。如果你准备好了，请开始编写。

请将我们的每次对话记录保存在chat_log/reviewer目录下。