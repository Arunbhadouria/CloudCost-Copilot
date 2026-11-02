"""Faithfulness verification and number checker for copilot responses."""
import re
from typing import Dict, Any, List, Set, Optional


def extract_numbers_from_text(text: str, question: Optional[str] = None) -> List[float]:
    """Extract all relevant numerical values from text, stripping currency and percentages.

    Ignores:
        - Years (e.g. 1990 - 2099)
        - Small integers (<= 10) mentioned in the question (e.g. top 3, top 5)
        - Ordinals (e.g. 1st, 2nd, 3rd)
    """
    if not text:
        return []

    # Find small integers in the question to ignore (e.g. "top 3", "top 5")
    ignore_ints: Set[float] = set()
    if question:
        q_matches = re.findall(r"\b(\d+)\b", question)
        for qm in q_matches:
            val = float(qm)
            if val <= 10:
                ignore_ints.add(val)

    # Clean text to remove ordinals: 1st, 2nd, 3rd, 4th...
    cleaned = re.sub(r"\b\d+(?:st|nd|rd|th)\b", "", text, flags=re.IGNORECASE)

    # Clean text to remove dates (YYYY-MM-DD and DD-MM-YYYY)
    cleaned = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", cleaned)
    cleaned = re.sub(r"\b\d{2}-\d{2}-\d{4}\b", "", cleaned)

    # Match numbers with optional $, commas, decimals, and k/M suffixes (word boundary) or %
    # Must not be part of hyphenated identifiers like res-1 or europe-north1
    pattern = r"(?<![a-zA-Z0-9_\-])[-+]?[\$]?\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)(?:\s*([kKmM])(?![a-zA-Z])|\s*(%))?(?![a-zA-Z0-9_\-])"
    matches = re.finditer(pattern, cleaned)

    numbers: List[float] = []
    for m in matches:
        num_str = m.group(1).replace(",", "")
        suffix = m.group(2)
        pct = m.group(3)

        try:
            val = float(num_str)
        except ValueError:
            continue

        # Ignore 4-digit years between 1990 and 2099
        if 1990 <= val <= 2099 and not suffix and not pct and "." not in m.group(1):
            continue

        # Ignore small integers originating from question
        if val in ignore_ints and not suffix and not pct and "." not in m.group(1):
            continue

        if suffix in ("k", "K"):
            val *= 1000.0
        elif suffix in ("m", "M"):
            val *= 1_000_000.0
        # If percentage (e.g. 15%), we record 15.0 (and check both 15.0 and 0.15)

        numbers.append(round(val, 4))

    return numbers


def extract_numbers_from_tool_data(tool_data: Any) -> List[float]:
    """Recursively extract all numbers present in tool output rows and dictionaries."""
    numbers: List[float] = []

    def _walk(obj: Any):
        if isinstance(obj, (int, float)):
            if not isinstance(obj, bool):
                numbers.append(float(obj))
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for v in obj:
                _walk(v)
        elif isinstance(obj, str):
            # Check for numeric strings inside tool output
            cleaned = obj.replace("$", "").replace(",", "").strip()
            # If string is range like "$10 - $20"
            for part in cleaned.split("-"):
                try:
                    numbers.append(float(part.strip()))
                except ValueError:
                    pass

    _walk(tool_data)
    return numbers


def check_faithfulness(
    answer: str,
    tool_data: Any,
    question: Optional[str] = None,
    relative_tolerance: float = 0.005
) -> Dict[str, Any]:
    """Verify that every number in answer appears in tool data within tolerance.

    Tolerance is 0.5% relative tolerance or +/- 0.05 absolute tolerance.
    """
    answer_numbers = extract_numbers_from_text(answer, question=question)
    tool_numbers = extract_numbers_from_tool_data(tool_data)

    unmatched: List[float] = []
    matched: List[float] = []

    for num in answer_numbers:
        is_matched = False
        for tn in tool_numbers:
            # Check exact or relative tolerance (allowing absolute value match for negative deltas)
            diff = min(abs(num - tn), abs(abs(num) - abs(tn)))
            rel_diff = diff / (abs(tn) + 1e-6)

            # Match either direct or percent representation (e.g. 15 vs 0.15)
            if diff <= 0.05 or rel_diff <= relative_tolerance:
                is_matched = True
                break
            if abs(num - (tn * 100.0)) <= 0.1 or abs(num - (tn / 100.0)) <= 0.01:
                is_matched = True
                break

        if is_matched:
            matched.append(num)
        else:
            unmatched.append(num)

    passed = (len(unmatched) == 0)
    return {
        "passed": passed,
        "answer_numbers": answer_numbers,
        "unmatched_numbers": unmatched,
        "matched_numbers": matched
    }
