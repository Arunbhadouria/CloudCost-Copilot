"""Ranking, confidence scoring, and effort estimation for recommendations."""
from typing import Optional


def calculate_confidence(
    data_quality: str,
    is_prod: bool = False,
    cpu_cv: Optional[float] = None
) -> float:
    """Calculate recommendation confidence score.

    Rules:
        - Base: 0.9 (series) or 0.5 (snapshot)
        - -0.2 if is_prod
        - -0.1 if cpu_cv > 1.0
        - Floor: 0.2
    """
    conf = 0.9 if data_quality == "series" else 0.5

    if is_prod:
        conf -= 0.2

    if cpu_cv is not None and cpu_cv > 1.0:
        conf -= 0.1

    return round(max(0.2, conf), 2)


def calculate_effort(finding_type: str) -> int:
    """Return effort score: idle=1, underused=3, weak_signal=5."""
    if finding_type == "idle":
        return 1
    elif finding_type == "underused":
        return 3
    else:
        return 5


def calculate_priority(
    savings_mid: float,
    confidence: float,
    effort: int,
    finding_type: str
) -> float:
    """Calculate ranking priority score = (savings_mid * confidence) / effort.

    Weak signal recommendations always receive priority 0.
    """
    if finding_type == "weak_signal" or effort <= 0:
        return 0.0

    score = (savings_mid * confidence) / float(effort)
    return round(score, 2)

