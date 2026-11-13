"""Separate process entry point for the bounded TextRank adapter."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from handoff.textrank import rank  # noqa: E402

if __name__ == '__main__':
    data = json.load(sys.stdin)
    print(json.dumps(rank(data['sentences'], data['count'])))

