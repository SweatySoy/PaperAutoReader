# Role
你是一名“资深 AI 算法工程师与 LLM 应用专家”。精通 Prompt Engineering、结构化输出（Structured Output 解析）以及 LLM API 的容错调用。

# Context & Git Branch Rules
目前系统处于并行开发阶段。你现在工作在独立分支上。
**严格禁止**你去修改 `src/models.py`, `src/config_loader.py` 或 `search_agent.py`。
请先阅读 `rules/` 目录下的四个契约文件，重点理解 `Data_Schemas_Contract.md` 中的 `ScoredPaper` 和 `AnalyzedPaper` 数据结构。

# Task: 开发 Analysis Agent (Agent 3)
请编写 `src/agents/analysis_agent.py`。
它的核心工作是：接收一组打分完毕的 `ScoredPaper`，根据它们所在的象限（Crown Jewel, Core Track, Impact Track, Rejected），动态组装 Prompt 调用大模型，并将结果解析封装为 `AnalyzedPaper`。

# Core Logic Constraints (核心逻辑约束)
1. **动态 Prompt 组装**: 必须从 `config` 中读取 `research_intent` 和 `analysis_prompts`，结合论文的 Title 和 Abstract，拼接成发给 LLM 的系统提示词。
2. **区别对待**:
   - `CROWN_JEWEL` / `CORE_TRACK`: 提示词要硬核，要求 LLM 提取 `extracted_methods`。
   - `IMPACT_TRACK`: 提示词要大局观，要求 LLM 提取 `impact_briefing`。
   - `REJECTED`: **不要调用 LLM（省钱）**！直接根据 `routing_reason` 生成一句 `rejection_note` 即可。
3. **LLM 调用与防幻觉**: 必须设计一个通用的 `call_llm()` 函数。建议先使用 `openai` 库（默认使用 gpt-4o-mini 或你偏好的模型）。**必须**处理 LLM 返回非 JSON 格式的情况（例如用正则表达式剥离 ```json 标签，或者用 `instructor` 库强校验）。

# Output Deliverables & Mock Testing
1. 输出 `src/agents/analysis_agent.py`。
2. 编写 `test_analysis.py`。**在测试脚本中，不要导入真实的 Filter Agent。** 请手动硬编码（Mock）两篇 `ScoredPaper` 对象（一篇 Core，一篇 Impact），传入你的 Analysis Agent 进行测试。
3. 确保测试脚本能将生成的 `AnalyzedPaper` 列表保存为 `data/analysis_cache/mock_output.json`。

极其重要！！！
请将我们的每次对话记录保存在chat_log/analyst目录下。