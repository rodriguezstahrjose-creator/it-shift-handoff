"""Small local TextRank implementation; scores are not severity/confidence."""

from collections import Counter
from math import sqrt
import re
from uuid import uuid4


def sentences(notes):
    result = []
    for note in notes:
        for match in re.finditer(r"[^.!?]+(?:[.!?]+|$)", note["text"]):
            raw = match.group()
            start = match.start() + len(raw) - len(raw.lstrip())
            end = match.end() - len(raw) + len(raw.rstrip())
            if start < end:
                result.append({"id": str(uuid4()), "note_id": note["id"],
                               "start": start, "end": end,
                               "text": note["text"][start:end]})
    return result


def extract(notes, max_sentences=3):
    if type(max_sentences) is not int or not 1 <= max_sentences <= 10:
        raise ValueError("max_sentences must be an integer from 1 to 10")
    if sum(len(n["text"]) for n in notes) > 10_000:
        raise ValueError("INPUT_LIMIT_EXCEEDED")
    source = sentences(notes)
    if len(source) > 200:
        raise ValueError("INPUT_LIMIT_EXCEEDED")
    if not source:
        return []
    # Weighted sentence graph: cosine similarity of lowercase word counts.
    vectors = [Counter(re.findall(r"\w+", s["text"].lower())) for s in source]
    norms = [sqrt(sum(x * x for x in v.values())) for v in vectors]
    size = len(source)
    weights = [[0.0] * size for _ in source]
    for i in range(size):
        for j in range(i + 1, size):
            dot = sum(count * vectors[j][word] for word, count in vectors[i].items())
            value = dot / (norms[i] * norms[j]) if norms[i] * norms[j] else 0
            weights[i][j] = weights[j][i] = value
    totals = [sum(row) for row in weights]
    scores = [1 / size] * size
    for _ in range(100):
        dangling = sum(scores[j] for j in range(size) if totals[j] == 0) / size
        updated = [(1 - 0.85) / size + 0.85 * (
            dangling + sum(scores[j] * weights[j][i] / totals[j]
                           for j in range(size) if totals[j])) for i in range(size)]
        delta = sum(abs(a - b) for a, b in zip(scores, updated))
        scores = updated
        if delta < 1e-8:
            break
    selected = sorted(sorted(range(size), key=lambda i: (-scores[i], i))[:max_sentences])
    if any(len(source[i]["text"]) > 2000 for i in selected):
        raise ValueError("SENTENCE_TOO_LONG")
    return [source[i] for i in selected]
