"""markdown.py - parse, manipulate, and generate markdown.

structured markdown processing for docgen, changelog, scaffold, and RAG
chunking. pure python, no external parsing libraries. parses headings into
a tree, extracts code blocks / links / images, and supports section-level
CRUD operations.

in the world: text has structure even when it looks flat. this module
finds the bones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Section:
    """a heading and everything under it."""

    heading: str
    level: int
    content: str = ""
    children: list[Section] = field(default_factory=list)


@dataclass
class MarkdownDoc:
    """parsed markdown document."""

    title: str
    sections: list[Section] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    raw: str = ""


# ---------------------------------------------------------------------------
# frontmatter
# ---------------------------------------------------------------------------

_FRONT_RE = re.compile(r"\A---\n(.*?\n)---\n?", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """extract YAML-ish frontmatter. returns (metadata, remaining text)."""
    m = _FRONT_RE.match(text)
    if not m:
        return {}, text
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


# ---------------------------------------------------------------------------
# heading helpers
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def extract_headings(text: str) -> list[dict]:
    """extract all headings with level and line number."""
    results = []
    for i, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            results.append({
                "text": m.group(2).strip(),
                "level": len(m.group(1)),
                "line": i,
            })
    return results


# ---------------------------------------------------------------------------
# extraction utilities
# ---------------------------------------------------------------------------

_CODE_BLOCK_RE = re.compile(
    r"^```(\w*)\n(.*?)^```", re.MULTILINE | re.DOTALL
)


def extract_code_blocks(text: str) -> list[dict]:
    """extract fenced code blocks with language and line number."""
    results = []
    offset = 0
    for m in _CODE_BLOCK_RE.finditer(text):
        line = text[:m.start()].count("\n") + 1
        results.append({
            "language": m.group(1) or "",
            "content": m.group(2),
            "line": line,
        })
    return results


_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
_REF_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\[([^\]]*)\]")
_REF_DEF_RE = re.compile(r"^\[([^\]]+)\]:\s*(.+)$", re.MULTILINE)


def extract_links(text: str) -> list[dict]:
    """extract inline and reference-style links."""
    results = []
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        for m in _LINK_RE.finditer(line):
            results.append({"text": m.group(1), "url": m.group(2), "line": i})
    # resolve reference links
    refs: dict[str, str] = {}
    for m in _REF_DEF_RE.finditer(text):
        refs[m.group(1).lower()] = m.group(2).strip()
    for i, line in enumerate(lines, 1):
        for m in _REF_LINK_RE.finditer(line):
            key = (m.group(2) or m.group(1)).lower()
            if key in refs:
                results.append({
                    "text": m.group(1),
                    "url": refs[key],
                    "line": i,
                })
    return results


_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def extract_images(text: str) -> list[dict]:
    """extract image references."""
    results = []
    for i, line in enumerate(text.splitlines(), 1):
        for m in _IMAGE_RE.finditer(line):
            results.append({"alt": m.group(1), "url": m.group(2), "line": i})
    return results


# ---------------------------------------------------------------------------
# table of contents
# ---------------------------------------------------------------------------

def toc(text: str) -> str:
    """generate a markdown table of contents from headings."""
    headings = extract_headings(text)
    if not headings:
        return ""
    min_level = min(h["level"] for h in headings)
    lines = []
    for h in headings:
        indent = "  " * (h["level"] - min_level)
        lines.append(f"{indent}- {h['text']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# section tree builder
# ---------------------------------------------------------------------------

def _build_tree(headings_with_content: list[tuple[str, int, str]]) -> list[Section]:
    """build a nested section tree from flat heading list."""
    if not headings_with_content:
        return []

    sections: list[Section] = []
    stack: list[Section] = []

    for heading, level, content in headings_with_content:
        section = Section(heading=heading, level=level, content=content)

        # pop stack until we find a parent (lower level number)
        while stack and stack[-1].level >= level:
            stack.pop()

        if stack:
            stack[-1].children.append(section)
        else:
            sections.append(section)

        stack.append(section)

    return sections


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

def parse(text: str) -> MarkdownDoc:
    """parse markdown text into a structured document."""
    metadata, body = _parse_frontmatter(text)

    headings = extract_headings(body)
    title = ""
    for h in headings:
        if h["level"] == 1:
            title = h["text"]
            break

    # split body into sections by heading
    lines = body.splitlines()
    segments: list[tuple[str, int, list[str]]] = []
    preamble_lines: list[str] = []

    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            segments.append((m.group(2).strip(), len(m.group(1)), []))
        elif segments:
            segments[-1][2].append(line)
        else:
            preamble_lines.append(line)

    hwc = [(h, lvl, "\n".join(cl).strip()) for h, lvl, cl in segments]
    sections = _build_tree(hwc)

    return MarkdownDoc(
        title=title,
        sections=sections,
        metadata=metadata,
        raw=text,
    )


# ---------------------------------------------------------------------------
# to_string
# ---------------------------------------------------------------------------

def _section_to_lines(section: Section) -> list[str]:
    """render a section and its children to lines."""
    lines = [f"{'#' * section.level} {section.heading}"]
    if section.content:
        lines.append("")
        lines.append(section.content)
    for child in section.children:
        lines.append("")
        lines.extend(_section_to_lines(child))
    return lines


def to_string(doc: MarkdownDoc) -> str:
    """render a MarkdownDoc back to markdown text."""
    parts: list[str] = []

    if doc.metadata:
        parts.append("---")
        for k, v in doc.metadata.items():
            parts.append(f"{k}: {v}")
        parts.append("---")
        parts.append("")

    for i, section in enumerate(doc.sections):
        if i > 0:
            parts.append("")
        parts.extend(_section_to_lines(section))

    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# find / insert / remove / update
# ---------------------------------------------------------------------------

def _walk(sections: list[Section]):
    """yield all sections depth-first."""
    for s in sections:
        yield s
        yield from _walk(s.children)


def find_section(doc: MarkdownDoc, heading: str) -> Section | None:
    """find a section by heading text, case-insensitive."""
    target = heading.lower()
    for s in _walk(doc.sections):
        if s.heading.lower() == target:
            return s
    return None


def _flat(sections: list[Section]) -> list[Section]:
    """flatten section tree to ordered list."""
    result = []
    for s in sections:
        result.append(s)
        result.extend(_flat(s.children))
    return result


def insert_section(doc: MarkdownDoc, section: Section, after: str = "") -> MarkdownDoc:
    """insert a section after the named heading, or at end."""
    new_sections = list(doc.sections)
    if not after:
        new_sections.append(section)
    else:
        target = after.lower()
        idx = None
        for i, s in enumerate(new_sections):
            if s.heading.lower() == target:
                idx = i
                break
        if idx is not None:
            new_sections.insert(idx + 1, section)
        else:
            new_sections.append(section)
    return MarkdownDoc(
        title=doc.title,
        sections=new_sections,
        metadata=dict(doc.metadata),
        raw=doc.raw,
    )


def remove_section(doc: MarkdownDoc, heading: str) -> MarkdownDoc:
    """remove a section by heading (top-level only for simplicity)."""
    target = heading.lower()
    new_sections = [s for s in doc.sections if s.heading.lower() != target]
    # also remove from children
    for s in _walk(new_sections):
        s.children = [c for c in s.children if c.heading.lower() != target]
    return MarkdownDoc(
        title=doc.title,
        sections=new_sections,
        metadata=dict(doc.metadata),
        raw=doc.raw,
    )


def update_section(doc: MarkdownDoc, heading: str, new_content: str) -> MarkdownDoc:
    """update the content of a section found by heading."""
    target = heading.lower()
    # deep copy would be ideal but we mutate in place for simplicity
    for s in _walk(doc.sections):
        if s.heading.lower() == target:
            s.content = new_content
            break
    return doc


# ---------------------------------------------------------------------------
# strip + word count
# ---------------------------------------------------------------------------

def strip_markdown(text: str) -> str:
    """remove markdown formatting, return plain text."""
    # remove code blocks entirely
    out = _CODE_BLOCK_RE.sub("", text)
    # remove inline code
    out = re.sub(r"`([^`]+)`", r"\1", out)
    # remove images
    out = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", out)
    # remove links, keep text
    out = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", out)
    # remove bold/italic
    out = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", out)
    out = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", out)
    # remove headings markers
    out = re.sub(r"^#{1,6}\s+", "", out, flags=re.MULTILINE)
    # remove horizontal rules
    out = re.sub(r"^[-*_]{3,}\s*$", "", out, flags=re.MULTILINE)
    # remove blockquote markers
    out = re.sub(r"^>\s?", "", out, flags=re.MULTILINE)
    # collapse whitespace
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def word_count(text: str) -> int:
    """count words in markdown, excluding code blocks and formatting."""
    stripped = strip_markdown(text)
    return len(stripped.split())
