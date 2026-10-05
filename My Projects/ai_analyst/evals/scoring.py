"""Check an agent answer against expectations computed from the data.

Answers are free text, so checks are deliberately forgiving about format:
'1,140,726.75', '1.14M', '€1.140.726,75' and '1.1 million' all count as the
same number (within a tolerance), and text checks ignore case.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6, "millones": 1e6,
          "b": 1e9, "bn": 1e9, "billion": 1e9}
_NUMBER_RE = re.compile(
    r"(?<![\w.])-?\d[\d.,\u00a0\u202f ]*\d|(?<![\w.])-?\d",
)
_SCALE_RE = re.compile(r"^\s*(k|thousand|mn|m|million|millones|bn|b|billion)\b", re.I)


def _parse_one(raw: str) -> list[float]:
    """One numeric token can be read US-style or EU-style; return the readings."""
    token = re.sub(r"[\u00a0\u202f ]", "", raw)
    readings = set()
    for thousands, decimal in ((",", "."), (".", ",")):
        # '1,234' could be 1234 (US) or 1.234 (EU): keep both readings.
        t = token.replace(thousands, "").replace(decimal, ".")
        try:
            readings.add(float(t))
        except ValueError:
            pass
    return sorted(readings)


def extract_numbers(text: str) -> list[float]:
    numbers: list[float] = []
    for m in _NUMBER_RE.finditer(text):
        values = _parse_one(m.group(0).strip(" .,"))
        scale = _SCALE_RE.match(text[m.end():])
        factor = _SCALE[scale.group(1).lower()] if scale else 1.0
        numbers.extend(v * factor for v in values)
    return numbers


def contains_number(text: str, expected: float, rel_tol: float = 0.01, abs_tol: float = 0.0) -> bool:
    tolerance = max(abs(expected) * rel_tol, abs_tol)
    return any(abs(n - expected) <= tolerance for n in extract_numbers(text))


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class CaseScore:
    case_id: str
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)


def score(case: dict[str, Any], expected: dict[str, Any], result: dict[str, Any]) -> CaseScore:
    """`expected` comes from the case's `expect(df)` function; `result` is an AgentResult dict."""
    answer = result.get("answer", "")
    lower = answer.lower()
    tools = [t["name"] for t in result.get("tool_calls", []) if t.get("ok")]
    checks: list[CheckResult] = [
        CheckResult("answered", result.get("stop_reason") == "answered",
                    f"stop_reason={result.get('stop_reason')}")]

    for value in expected.get("numbers", []):
        rel = expected.get("rel_tol", 0.01)
        absolute = expected.get("abs_tol", 0.0)
        checks.append(CheckResult(f"number≈{value:,.2f}", contains_number(answer, value, rel, absolute)))
    for word in expected.get("mentions", []):
        checks.append(CheckResult(f"mentions '{word}'", word.lower() in lower))
    if expected.get("mentions_any"):
        options = expected["mentions_any"]
        checks.append(CheckResult(f"mentions one of {options}",
                                  any(o.lower() in lower for o in options)))
    if expected.get("uses_tools_any"):
        options = expected["uses_tools_any"]
        checks.append(CheckResult(f"uses one of {options}", any(t in tools for t in options),
                                  f"used {tools}"))
    if "chart" in expected:
        has_chart = bool(result.get("charts"))
        checks.append(CheckResult("chart" if expected["chart"] else "no chart",
                                  has_chart == expected["chart"]))
    return CaseScore(case["id"], all(c.passed for c in checks), checks)
