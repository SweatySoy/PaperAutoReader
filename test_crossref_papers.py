"""
Test CrossRef with various published papers.
"""

import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.agents.search_agent import CrossRefClient

def test_crossref():
    """测试多篇论文的 CrossRef 确认。"""
    print("=" * 60)
    print("CrossRef Publication Verification Test")
    print("=" * 60)

    client = CrossRefClient()

    test_cases = [
        # (arxiv_id, title, authors, expected_published)
        ("1706.03762", "Attention Is All You Need", ["Vaswani", "Shazeer"], "maybe"),
        ("1512.03385", "Deep Residual Learning for Image Recognition", ["He", "Zhang", "Ren", "Sun"], "maybe"),  # ResNet - CVPR
        ("1412.6980", "Adam: A Method for Stochastic Optimization", ["Kingma", "Ba"], "maybe"),  # Adam - ICLR
        ("1606.08415", "Variational Autoencoder", ["Kingma", "Welling"], "maybe"),  # VAE
        ("2401.00001", "Fake Paper Title", ["Nobody"], False),  # 不存在的论文
    ]

    for arxiv_id, title, authors, expected in test_cases:
        print(f"\n[{arxiv_id}] {title[:40]}...")

        result = client.get_publication_info(
            arxiv_id=arxiv_id,
            title=title,
            authors=authors
        )

        if result.get("is_published"):
            print(f"  -> PUBLISHED in: {result['venue']}")
            print(f"  -> DOI: {result.get('doi', 'N/A')}")
        else:
            print(f"  -> NOT PUBLISHED (still in arXiv or not found)")

        # 验证预期
        if expected == False and result.get("is_published"):
            print(f"  [WARN] Expected NOT published but got published!")
        elif expected == True and not result.get("is_published"):
            print(f"  [WARN] Expected published but not found!")

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_crossref()
