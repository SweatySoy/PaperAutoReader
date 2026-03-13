"""
Report Generation Agent (Agent 4) - Research Radar System
==========================================================

This agent is responsible for generating the final Markdown report
from analyzed papers, organized by quadrant classification.

Author: AI Coding Agent
Branch: feat/agent4-report
"""

from datetime import date
from pathlib import Path
from typing import List

# Handle both relative and absolute imports
try:
    from ..models import AnalyzedPaper, FinalReport, QuadrantCategory
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from models import AnalyzedPaper, FinalReport, QuadrantCategory


class ReportAgent:
    """
    Report Generation Agent for rendering final situational awareness reports.

    Takes a list of AnalyzedPaper objects, organizes them by quadrant,
    and generates a high-quality Markdown report.
    """

    def __init__(self, output_dir: Path | None = None):
        """
        Initialize the Report Agent.

        Args:
            output_dir: Directory to save reports. Defaults to reports/ under project root.
        """
        if output_dir is None:
            # Get project root (3 levels up from this file)
            project_root = Path(__file__).parent.parent.parent
            output_dir = project_root / "reports"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(self, papers: List[AnalyzedPaper],
                        report_date: date | None = None) -> FinalReport:
        """
        Generate a FinalReport from analyzed papers.

        Args:
            papers: List of AnalyzedPaper objects
            report_date: Date for the report. Defaults to today.

        Returns:
            FinalReport object with papers organized by quadrant
        """
        if report_date is None:
            report_date = date.today()

        # Organize papers by quadrant
        crown_jewels = []
        core_papers = []
        impact_papers = []
        rejected_papers = []

        for paper in papers:
            match paper.quadrant_category:
                case QuadrantCategory.CROWN_JEWEL:
                    crown_jewels.append(paper)
                case QuadrantCategory.CORE_TRACK:
                    core_papers.append(paper)
                case QuadrantCategory.IMPACT_TRACK:
                    impact_papers.append(paper)
                case QuadrantCategory.REJECTED:
                    rejected_papers.append(paper)

        return FinalReport(
            report_date=report_date,
            crown_jewels=crown_jewels,
            core_papers=core_papers,
            impact_papers=impact_papers,
            rejected_papers_log=rejected_papers
        )

    def render_markdown(self, report: FinalReport) -> str:
        """
        Render the FinalReport as a Markdown string.

        Args:
            report: FinalReport object to render

        Returns:
            Markdown formatted string
        """
        lines = []

        # === HEADER SECTION ===
        lines.append(self._render_header(report))

        # === CROWN JEWELS SECTION ===
        if report.crown_jewels:
            lines.append(self._render_crown_jewels(report.crown_jewels))

        # === CORE TRACK SECTION ===
        if report.core_papers:
            lines.append(self._render_core_track(report.core_papers))

        # === EMERGING IMPACT SECTION ===
        if report.impact_papers:
            lines.append(self._render_impact_track(report.impact_papers))

        # === REJECTED PIPELINE SECTION ===
        if report.rejected_papers_log:
            lines.append(self._render_rejected(report.rejected_papers_log))

        return "\n".join(lines)

    def _render_header(self, report: FinalReport) -> str:
        """Render the report header with statistics."""
        total = (
            len(report.crown_jewels) +
            len(report.core_papers) +
            len(report.impact_papers) +
            len(report.rejected_papers_log)
        )

        header = f"""# 📊 Research Radar Report
## 领域态势感知报告

**📅 生成日期**: {report.report_date.strftime('%Y-%m-%d')}

---

### 📈 统计概览

| 象限 | 数量 | 说明 |
|:---:|:---:|:---|
| 👑 Crown Jewels | {len(report.crown_jewels)} | 核心必读经典 |
| 🎯 Core Track | {len(report.core_papers)} | 日常领域跟进 |
| 🔭 Emerging Impact | {len(report.impact_papers)} | 跨界高影响 |
| 🗑️ Rejected | {len(report.rejected_papers_log)} | 已滤除记录 |
| **总计** | **{total}** | |

---

"""
        return header

    def _render_crown_jewels(self, papers: List[AnalyzedPaper]) -> str:
        """Render the Crown Jewels section with detailed formatting."""
        lines = ["## 👑 Crown Jewels (核心必读)\n"]
        lines.append("> 这些论文具有高相关度且高影响力，建议精读。\n")

        for i, paper in enumerate(papers, 1):
            lines.append(f"### {i}. {paper.title}")
            lines.append(f"\n| 属性 | 值 |")
            lines.append(f"|:---|:---|")
            lines.append(f"| 📄 来源 | {paper.venue} |")
            lines.append(f"| 👥 作者 | {', '.join(paper.authors[:5])}{'...' if len(paper.authors) > 5 else ''} |")
            lines.append(f"| 📅 日期 | {paper.publication_date} |")
            lines.append(f"| 🔗 链接 | [原文链接]({paper.url}) |")
            lines.append(f"| 🎯 Core Score | {paper.core_score:.1f} |")
            lines.append(f"| ⭐ Impact Score | {paper.impact_score:.1f} |")
            lines.append("")

            # Analysis Summary
            if paper.analysis_summary:
                lines.append("**📝 分析摘要**")
                lines.append(f"> {paper.analysis_summary}")
                lines.append("")

            # Extracted Methods
            if paper.extracted_methods:
                lines.append("**🔬 提取的方法论**")
                for method in paper.extracted_methods:
                    lines.append(f"- {method}")
                lines.append("")

            # Routing Reason
            lines.append(f"**🚀 分类理由**: {paper.routing_reason}")
            lines.append("\n---\n")

        return "\n".join(lines)

    def _render_core_track(self, papers: List[AnalyzedPaper]) -> str:
        """Render the Core Track section with standard formatting."""
        lines = ["## 🎯 Core Track (领域跟进)\n"]
        lines.append("> 这些论文相关度高但影响力一般，建议标准深度阅读。\n")

        for i, paper in enumerate(papers, 1):
            lines.append(f"### {i}. {paper.title}")
            lines.append(f"\n- **来源**: {paper.venue}")
            lines.append(f"- **作者**: {', '.join(paper.authors[:3])}{'...' if len(paper.authors) > 3 else ''}")
            lines.append(f"- **日期**: {paper.publication_date}")
            lines.append(f"- **链接**: [原文链接]({paper.url})")
            lines.append(f"- **评分**: Core {paper.core_score:.1f} / Impact {paper.impact_score:.1f}")
            lines.append("")

            if paper.analysis_summary:
                lines.append(f"> **摘要**: {paper.analysis_summary}")
                lines.append("")

            if paper.extracted_methods:
                lines.append(f"**方法**: {', '.join(paper.extracted_methods[:3])}")
                lines.append("")

            lines.append(f"**分类理由**: {paper.routing_reason}")
            lines.append("\n---\n")

        return "\n".join(lines)

    def _render_impact_track(self, papers: List[AnalyzedPaper]) -> str:
        """Render the Impact Track section with compact formatting."""
        lines = ["## 🔭 Emerging Impact (跨界高影响)\n"]
        lines.append("> 这些论文相关度不高但影响力大，关注其跨界启发。\n")

        for i, paper in enumerate(papers, 1):
            lines.append(f"### {i}. {paper.title}")
            lines.append(f"**{paper.venue}** | {paper.publication_date} | [链接]({paper.url})")
            lines.append(f"\n> ⚡ **影响力来源**: {paper.routing_reason}")

            if paper.impact_briefing:
                lines.append(f"\n> 💡 **跨界启发**: {paper.impact_briefing}")

            lines.append("\n---\n")

        return "\n".join(lines)

    def _render_rejected(self, papers: List[AnalyzedPaper]) -> str:
        """Render the Rejected section as a compact table."""
        lines = ["## 🗑️ Rejected Pipeline (已滤除记录)\n"]
        lines.append("> 这些论文相关度和影响力均较低，仅作记录便于复盘。\n")
        lines.append("| # | 标题 | 拒绝理由 |")
        lines.append("|:---:|:---|:---|")

        for i, paper in enumerate(papers, 1):
            rejection = paper.rejection_note or paper.routing_reason
            # Truncate title if too long
            title = paper.title if len(paper.title) <= 50 else paper.title[:47] + "..."
            lines.append(f"| {i} | {title} | {rejection} |")

        lines.append("")
        return "\n".join(lines)

    def save_report(self, report: FinalReport,
                    filename: str | None = None) -> Path:
        """
        Save the report as a Markdown file.

        Args:
            report: FinalReport object to save
            filename: Custom filename. Defaults to Research_Radar_YYYY-MM-DD.md

        Returns:
            Path to the saved file
        """
        if filename is None:
            filename = f"Research_Radar_{report.report_date.strftime('%Y-%m-%d')}.md"

        filepath = self.output_dir / filename
        markdown_content = self.render_markdown(report)

        filepath.write_text(markdown_content, encoding='utf-8')
        return filepath

    def run(self, papers: List[AnalyzedPaper],
            report_date: date | None = None,
            filename: str | None = None) -> tuple[FinalReport, Path]:
        """
        Full pipeline: generate, render, and save report.

        Args:
            papers: List of AnalyzedPaper objects
            report_date: Date for the report
            filename: Custom filename

        Returns:
            Tuple of (FinalReport, Path to saved file)
        """
        report = self.generate_report(papers, report_date)
        filepath = self.save_report(report, filename)
        return report, filepath
