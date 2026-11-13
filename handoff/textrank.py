"""Local extractive TextRank with exact source offsets and bounded execution.

Sentence similarity uses the original backend's cosine word-count vectors.
Weighted PageRank uses damping 0.85; disconnected sentences share dangling mass.
No external model, API, or runtime download is used.
"""
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
from .errors import DomainError

from .ranking import sentences, rank_sentences

ALGORITHM_VERSION = 'textrank-cosine-1.1'


def rank(source, count):
    """Use the original backend ranking core; preserve deterministic source order."""
    return rank_sentences(source, count)


def extract(source, count, deadline=4):
    """The worker has no database/session access; timeout kills and reaps it."""
    try:
        completed = subprocess.run(  # fixed program and args; input travels via stdin
            [sys.executable, str(Path(__file__).with_name('rank_worker.py'))],
            input=json.dumps({'sentences': source, 'count': count}),
            capture_output=True, text=True, timeout=deadline, check=True)
        indices = json.loads(completed.stdout)
        return [source[i] for i in indices]
    except subprocess.TimeoutExpired as exc:
        raise DomainError('AI_TIMEOUT', 'Summary generation timed out. Try a manual draft.', 503) from exc
    except (subprocess.SubprocessError, ValueError, IndexError, TypeError, OSError) as exc:
        raise DomainError('AI_UNAVAILABLE', 'Summarization is unavailable. Try a manual draft.', 503) from exc

