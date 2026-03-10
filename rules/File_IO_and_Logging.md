# File I/O, State Management & Logging Rules
# 文件读写、状态管理与日志规范

所有的 AI Coding Agent 在编写涉及文件操作、API 调用和数据存储的代码时，必须严格遵守以下规范：

## 1. 绝对路径禁止 (No Absolute Paths)
代码中严禁出现如 `C:/Users/...` 或 `/Users/...` 的绝对路径。
必须使用 `pathlib.Path` 获取项目根目录，并基于根目录进行相对路径拼接（如 `PROJECT_ROOT / "data" / "raw_papers"`）。

## 2. 断点续传与状态缓存 (Checkpointing) -> 极其重要！
考虑到 LLM API 和 arXiv API 会产生费用和网络延迟，系统必须实现“断点机制”：
- **Agent 1 (Search)** 完成后，必须将 `List[CandidatePaper]` 序列化保存至 `data/raw_papers/YYYY-MM-DD.json`。
- **Agent 2 (Filter)** 读取上述文件，完成后将 `List[ScoredPaper]` 保存至 `data/scored_papers/YYYY-MM-DD.json`。
- **如果在 Agent 3 (Analysis) 阶段崩溃**，程序重启时必须能直接读取 `scored_papers/` 中的数据，**绝对禁止**重新去跑 Search 和 Filter。

## 3. 命名约定 (Naming Conventions)
- **数据文件**: 统一使用 ISO 时间格式前缀，例如：`data/scored_papers/2026-03-10_run_01.json`。
- **最终报告**: 生成的报告必须按日期命名，存入 `reports/` 目录。例如：`reports/Research_Radar_2026-03-10.md`。

## 4. 日志记录标准 (Logging Standards)
禁止在代码中大量使用基础的 `print()`。必须使用 Python 标准库 `logging` 或第三方库 `loguru`。
- **日志存储**: 所有日志必须同时输出到 Console (控制台) 和 `logs/system_YYYY-MM-DD.log` 文件。
- **日志级别要求**:
  - `INFO`: 记录流水线关键节点（如："Search Agent 抓取了 50 篇论文"）。
  - `DEBUG`: 记录详细分数（如："Paper [arXiv:1234] CoreScore=75, ImpactScore=80"）。
  - `ERROR`: 记录 API 超时、LLM 幻觉、JSON 解析失败，并必须包含完整的 Traceback。
- **异常捕获 (Try-Except)**: 对于任何外部网络请求（API, LLM 调用），必须加上 Try-Except 块，失败重试 (Retry) 最大次数设定为 3。