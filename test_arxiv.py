"""
Test arXiv API with date range queries.
按日期范围分批获取 arXiv 论文，每天一个批次。
"""

import sys
import os
import requests
import json
from datetime import datetime, timedelta
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')


def fetch_arxiv_by_date_range(
    start_date: str,
    end_date: str,
    max_results_per_day: int = 100,
    output_dir: str = "data/arxiv_by_date"
):
    """
    按日期范围获取 arXiv 论文，每天一个批次。

    Args:
        start_date: 开始日期 (格式: "2024-06-01")
        end_date: 结束日期 (格式: "2025-01-31")
        max_results_per_day: 每天最大获取数量
        output_dir: 输出目录
    """
    # 解析日期
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # 创建输出目录
    project_root = Path(__file__).parent
    output_path = project_root / output_dir
    output_path.mkdir(parents=True, exist_ok=True)

    # arXiv API endpoint
    arxiv_api_url = "http://export.arxiv.org/api/query"

    all_papers = []
    current_date = start

    print(f"开始获取 {start_date} 到 {end_date} 的论文...")
    print(f"每天最多获取 {max_results_per_day} 篇")
    print("=" * 60)

    while current_date <= end:
        # 计算当天的日期范围
        day_start = current_date
        day_end = current_date + timedelta(days=1) - timedelta(seconds=1)

        # 格式化为 arXiv API 要求的格式: YYYYMMDDHHMMSS
        date_from = day_start.strftime("%Y%m%d%H%M%S")
        date_to = day_end.strftime("%Y%m%d%H%M%S")

        # 构建查询参数
        params = {
            "search_query": f"submittedDate:[{date_from} TO {date_to}]",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": 0,
            "max_results": max_results_per_day
        }

        print(f"\n正在获取 {current_date.strftime('%Y-%m-%d')} 的论文...")
        print(f"  查询: submittedDate:[{date_from} TO {date_to}]")

        try:
            response = requests.get(arxiv_api_url, params=params, timeout=60)

            if response.status_code != 200:
                print(f"  错误: HTTP {response.status_code}")
                current_date += timedelta(days=1)
                continue

            # 解析 XML 响应
            papers = parse_arxiv_xml(response.text)

            if papers:
                print(f"  获取到 {len(papers)} 篇论文")
                all_papers.extend(papers)

                # 保存当天的论文
                day_file = output_path / f"{current_date.strftime('%Y-%m-%d')}.json"
                with open(day_file, "w", encoding="utf-8") as f:
                    json.dump(papers, f, ensure_ascii=False, indent=2)
                print(f"  已保存到: {day_file}")
            else:
                print(f"  当天无论文")

        except requests.exceptions.Timeout:
            print(f"  请求超时，跳过该天")
        except Exception as e:
            print(f"  错误: {e}")

        current_date += timedelta(days=1)

    # 保存所有论文汇总
    summary_file = output_path / f"summary_{start_date}_to_{end_date}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({
            "date_range": f"{start_date} to {end_date}",
            "total_papers": len(all_papers),
            "papers": all_papers
        }, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"完成! 总共获取 {len(all_papers)} 篇论文")
    print(f"汇总文件: {summary_file}")

    return all_papers


def parse_arxiv_xml(xml_text: str) -> list:
    """
    解析 arXiv API 返回的 XML 格式数据。

    Returns:
        论文列表，每个论文是一个字典
    """
    import xml.etree.ElementTree as ET

    papers = []

    try:
        root = ET.fromstring(xml_text)

        # arXiv API 使用 Atom 命名空间
        namespace = {"atom": "http://www.w3.org/2005/Atom",
                     "arxiv": "http://arxiv.org/schemas/atom"}

        entries = root.findall("atom:entry", namespace)

        for entry in entries:
            paper = {}

            # 标题
            title_elem = entry.find("atom:title", namespace)
            if title_elem is not None:
                paper["title"] = title_elem.text.strip() if title_elem.text else ""

            # 摘要
            summary_elem = entry.find("atom:summary", namespace)
            if summary_elem is not None:
                paper["abstract"] = summary_elem.text.strip() if summary_elem.text else ""

            # 作者
            authors = []
            for author_elem in entry.findall("atom:author", namespace):
                name_elem = author_elem.find("atom:name", namespace)
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text.strip())
            paper["authors"] = authors

            # 链接 (arXiv ID)
            for link_elem in entry.findall("atom:link", namespace):
                href = link_elem.get("href", "")
                if "arxiv.org/abs" in href:
                    paper["url"] = href
                    # 提取 arXiv ID
                    paper["arxiv_id"] = href.split("/abs/")[-1]
                    break

            # 发布日期
            published_elem = entry.find("atom:published", namespace)
            if published_elem is not None and published_elem.text:
                paper["published"] = published_elem.text.strip()

            # 更新日期
            updated_elem = entry.find("atom:updated", namespace)
            if updated_elem is not None and updated_elem.text:
                paper["updated"] = updated_elem.text.strip()

            # 类别/标签
            categories = []
            for cat_elem in entry.findall("atom:category", namespace):
                term = cat_elem.get("term")
                if term:
                    categories.append(term)
            paper["categories"] = categories

            # 期刊引用 (如果有)
            journal_ref = entry.find("arxiv:journal_ref", namespace)
            if journal_ref is not None and journal_ref.text:
                paper["journal_ref"] = journal_ref.text.strip()

            if paper.get("arxiv_id"):
                papers.append(paper)

    except ET.ParseError as e:
        print(f"  XML 解析错误: {e}")

    return papers


def test_single_day():
    """测试获取单天的论文。"""
    print("=" * 60)
    print("测试: 获取 2024-01-15 的论文")
    print("=" * 60)

    papers = fetch_arxiv_by_date_range(
        start_date="2024-01-15",
        end_date="2024-01-15",
        max_results_per_day=10,
        output_dir="data/arxiv_test"
    )

    if papers:
        print(f"\n前 3 篇论文:")
        for i, p in enumerate(papers[:3], 1):
            print(f"\n{i}. {p.get('title', 'N/A')[:60]}...")
            print(f"   arXiv: {p.get('arxiv_id', 'N/A')}")
            print(f"   作者: {', '.join(p.get('authors', [])[:3])}")


def test_date_range():
    """测试获取日期范围的论文。"""
    print("\n" + "=" * 60)
    print("测试: 获取 2024-01-01 到 2024-01-05 的论文")
    print("=" * 60)

    papers = fetch_arxiv_by_date_range(
        start_date="2024-01-01",
        end_date="2024-01-05",
        max_results_per_day=50,
        output_dir="data/arxiv_by_date"
    )


if __name__ == "__main__":
    # 运行测试
    test_single_day()
    # test_date_range()  # 取消注释以测试日期范围
