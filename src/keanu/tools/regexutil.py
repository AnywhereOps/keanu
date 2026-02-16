"""regexutil.py - regex pattern analysis and testing utilities.

test patterns, explain them in plain english, suggest patterns from examples,
validate syntax, search files. pure python, no LLM needed.

in the world: ash. regex is structure, structure is pattern, pattern is sight.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class MatchInfo:
    """one match result with position and group details."""

    full_match: str
    groups: tuple
    named_groups: dict
    start: int
    end: int
    line_number: Optional[int] = None


@dataclass
class RegexMatch:
    """full result of testing a pattern against text."""

    pattern: str
    text: str
    matches: list[MatchInfo] = field(default_factory=list)
    flags: int = 0


def check_pattern(pattern: str, text: str, flags: int = 0) -> RegexMatch:
    """test a regex against text, return all matches with details."""
    compiled = re.compile(pattern, flags)
    result = RegexMatch(pattern=pattern, text=text, flags=flags)

    # build line offset map for line_number lookup
    line_starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            line_starts.append(i + 1)

    for m in compiled.finditer(text):
        # binary search for line number
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= m.start():
                lo = mid
            else:
                hi = mid - 1
        line_num = lo + 1  # 1-indexed

        result.matches.append(
            MatchInfo(
                full_match=m.group(0),
                groups=m.groups(),
                named_groups=m.groupdict(),
                start=m.start(),
                end=m.end(),
                line_number=line_num,
            )
        )
    return result


# token explanations for explain_pattern
_TOKEN_MAP = [
    # lookahead / lookbehind (must come before generic group patterns)
    (r"\(\?=", "positive lookahead (match if followed by ...)"),
    (r"\(\?!", "negative lookahead (match if NOT followed by ...)"),
    (r"\(\?<=", "positive lookbehind (match if preceded by ...)"),
    (r"\(\?<!", "negative lookbehind (match if NOT preceded by ...)"),
    # named group
    (r"\(\?P<([^>]+)>", "named capture group '{0}'"),
    # non-capturing group
    (r"\(\?:", "non-capturing group"),
    # capturing group
    (r"\(", "start capturing group"),
    (r"\)", "end group"),
    # quantifiers
    (r"\{(\d+),(\d+)\}", "between {0} and {1} times"),
    (r"\{(\d+),\}", "{0} or more times"),
    (r"\{(\d+)\}", "exactly {0} times"),
    (r"\*\?", "zero or more (lazy)"),
    (r"\+\?", "one or more (lazy)"),
    (r"\?\?", "zero or one (lazy)"),
    (r"\*", "zero or more"),
    (r"\+", "one or more"),
    (r"\?", "zero or one (optional)"),
    # anchors
    (r"\^", "start of string/line"),
    (r"\$", "end of string/line"),
    # character classes
    (r"\\d", "digit [0-9]"),
    (r"\\D", "non-digit"),
    (r"\\w", "word character [a-zA-Z0-9_]"),
    (r"\\W", "non-word character"),
    (r"\\s", "whitespace"),
    (r"\\S", "non-whitespace"),
    (r"\\b", "word boundary"),
    (r"\\B", "non-word boundary"),
    (r"\\n", "newline"),
    (r"\\t", "tab"),
    # escaped literal
    (r"\\(.)", "literal '{0}'"),
    # dot
    (r"\.", "any character (except newline)"),
    # alternation
    (r"\|", "OR"),
]


def explain_pattern(pattern: str) -> list[str]:
    """break a regex into human-readable token explanations. pure python."""
    explanations = []
    i = 0
    while i < len(pattern):
        matched = False
        for token_re, template in _TOKEN_MAP:
            m = re.match(token_re, pattern[i:])
            if m:
                if m.groups():
                    desc = template.format(*m.groups())
                else:
                    desc = template
                explanations.append(f"{m.group(0)} -> {desc}")
                i += len(m.group(0))
                matched = True
                break

        if not matched:
            # character class bracket
            if pattern[i] == "[":
                end = pattern.find("]", i + 1)
                if end == -1:
                    end = len(pattern) - 1
                cls = pattern[i : end + 1]
                # check for negation
                if len(cls) > 2 and cls[1] == "^":
                    explanations.append(f"{cls} -> any character NOT in {cls[2:-1]}")
                else:
                    explanations.append(f"{cls} -> any character in {cls[1:-1]}")
                i = end + 1
            else:
                explanations.append(f"{pattern[i]} -> literal '{pattern[i]}'")
                i += 1

    return explanations


def suggest_pattern(
    examples: list[str], non_examples: list[str] | None = None
) -> str:
    """heuristic pattern generator from positive (and optional negative) examples.

    finds shared structure: common prefix, suffix, length range, character
    classes per position. simple approach, not perfect.
    """
    if not examples:
        return ".*"

    # find common prefix
    prefix = examples[0]
    for ex in examples[1:]:
        while not ex.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                break

    # find common suffix
    suffix = examples[0]
    for ex in examples[1:]:
        while not ex.endswith(suffix):
            suffix = suffix[1:]
            if not suffix:
                break

    # avoid overlap
    if prefix and suffix and len(prefix) + len(suffix) > len(examples[0]):
        suffix = ""

    # characterize the middle
    middles = []
    for ex in examples:
        start = len(prefix)
        end = len(ex) - len(suffix) if suffix else len(ex)
        middles.append(ex[start:end])

    def _char_class(chars: set[str]) -> str:
        """pick the tightest character class for a set of chars."""
        if not chars:
            return ""
        if chars <= set("0123456789"):
            return r"\d"
        if chars <= set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            return "[a-zA-Z]"
        if chars <= set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
        ):
            return r"\w"
        return "."

    mid_pattern = ""
    if middles and any(middles):
        lengths = [len(m) for m in middles]
        min_len, max_len = min(lengths), max(lengths)

        if min_len == max_len and min_len > 0:
            # fixed length, try per-position class
            parts = []
            for pos in range(min_len):
                chars = {m[pos] for m in middles if pos < len(m)}
                parts.append(_char_class(chars))
            mid_pattern = "".join(parts)
        elif max_len > 0:
            # variable length
            all_chars = {ch for m in middles for ch in m}
            cc = _char_class(all_chars)
            if min_len == max_len:
                mid_pattern = f"{cc}{{{min_len}}}"
            else:
                mid_pattern = f"{cc}{{{min_len},{max_len}}}"

    pat = re.escape(prefix) + mid_pattern + re.escape(suffix)

    # validate against non-examples if provided
    if non_examples and pat:
        try:
            compiled = re.compile(f"^{pat}$")
            hits = [ne for ne in non_examples if compiled.match(ne)]
            if hits:
                # pattern is too broad, just return what we have with a note
                pass
        except re.error:
            pass

    return pat if pat else ".*"


def validate_pattern(pattern: str) -> tuple[bool, str]:
    """check if a regex compiles. returns (valid, error_message)."""
    try:
        re.compile(pattern)
        return (True, "")
    except re.error as e:
        return (False, str(e))


def find_in_files(
    pattern: str, paths: list[str], flags: int = 0
) -> dict[str, list[MatchInfo]]:
    """test pattern against multiple files. returns path -> matches."""
    compiled = re.compile(pattern, flags)
    results: dict[str, list[MatchInfo]] = {}

    for path_str in paths:
        p = Path(path_str)
        if not p.is_file():
            continue
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue

        line_starts = [0]
        for i, ch in enumerate(text):
            if ch == "\n":
                line_starts.append(i + 1)

        file_matches = []
        for m in compiled.finditer(text):
            lo, hi = 0, len(line_starts) - 1
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if line_starts[mid] <= m.start():
                    lo = mid
                else:
                    hi = mid - 1

            file_matches.append(
                MatchInfo(
                    full_match=m.group(0),
                    groups=m.groups(),
                    named_groups=m.groupdict(),
                    start=m.start(),
                    end=m.end(),
                    line_number=lo + 1,
                )
            )

        if file_matches:
            results[path_str] = file_matches

    return results


def escape_for_literal(text: str) -> str:
    """escape text so it matches literally in a regex."""
    return re.escape(text)


def common_patterns() -> dict[str, str]:
    """dict of common useful regex patterns."""
    return {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "url": r"https?://[^\s<>\"']+",
        "ipv4": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        "phone_us": r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "date_iso": r"\d{4}-\d{2}-\d{2}",
        "date_us": r"\d{1,2}/\d{1,2}/\d{2,4}",
        "uuid": r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "semver": r"\bv?\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?(?:\+[a-zA-Z0-9.]+)?\b",
        "hex_color": r"#[0-9a-fA-F]{3,8}\b",
        "ipv6": r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}",
        "mac_address": r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    }
