"""
Debug CrossRef API responses.
"""

import sys
import os
from pathlib import Path
import requests

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def debug_crossref_search(title: str):
    """直接查询 CrossRef API 查看返回结果。"""
    print(f"\n{'='*60}")
    print(f"Debug CrossRef query: {title}")
    print(f"{'='*60}")

    url = "https://api.crossref.org/works"
    params = {
        "query.title": title,
        "rows": 5
    }
    headers = {"User-Agent": "PaperAutoReader/1.0 (debug)"}

    response = requests.get(url, params=params, headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"Error: HTTP {response.status_code}")
        return

    data = response.json()
    items = data.get("message", {}).get("items", [])

    print(f"Found {len(items)} results:\n")

    for i, item in enumerate(items, 1):
        print(f"--- Result {i} ---")
        print(f"Title: {item.get('title', ['N/A'])[0] if item.get('title') else 'N/A'}")
        print(f"DOI: {item.get('DOI', 'N/A')}")
        print(f"Container: {item.get('container-title', ['N/A'])}")
        print(f"Publisher: {item.get('publisher', 'N/A')}")
        print(f"Year: {item.get('published-print', {}).get('date-parts', [['N/A']])[0][0]}")

        authors = item.get('author', [])
        author_names = [f"{a.get('given', '')} {a.get('family', '')}" for a in authors[:5]]
        print(f"Authors: {', '.join(author_names) if author_names else 'N/A'}")
        print()


if __name__ == "__main__":
    debug_crossref_search("Attention Is All You Need")
    debug_crossref_search("BERT Pre-training Deep Bidirectional Transformers")
