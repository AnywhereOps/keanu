"""Tests for markdown.py - parse, manipulate, generate markdown."""

from keanu.tools.markdown import (
    MarkdownDoc, Section, parse, to_string,
    extract_code_blocks, extract_links, extract_images, extract_headings,
    toc, find_section, insert_section, remove_section, update_section,
    strip_markdown, word_count,
)


SAMPLE = """\
# My Doc

Some intro text.

## Section One

Content of section one.

### Nested

Nested content here.

## Section Two

Second section body.
"""

SAMPLE_WITH_FRONTMATTER = """\
---
title: Test Doc
author: drew
---

# Test Doc

Body here.
"""


class TestParse:
    def test_title_from_first_h1(self):
        doc = parse(SAMPLE)
        assert doc.title == "My Doc"

    def test_sections_at_top_level(self):
        doc = parse(SAMPLE)
        # h1 is the root, h2s are its children
        assert doc.sections[0].heading == "My Doc"
        children = doc.sections[0].children
        headings = [s.heading for s in children]
        assert "Section One" in headings
        assert "Section Two" in headings

    def test_nested_section(self):
        doc = parse(SAMPLE)
        # h2 "Section One" is child of h1, h3 "Nested" is child of h2
        s1 = find_section(doc, "Section One")
        assert s1 is not None
        assert len(s1.children) == 1
        assert s1.children[0].heading == "Nested"

    def test_frontmatter_parsed(self):
        doc = parse(SAMPLE_WITH_FRONTMATTER)
        assert doc.metadata["title"] == "Test Doc"
        assert doc.metadata["author"] == "drew"
        assert doc.title == "Test Doc"

    def test_raw_preserved(self):
        doc = parse(SAMPLE)
        assert doc.raw == SAMPLE


class TestExtractCodeBlocks:
    def test_with_language(self):
        text = "# Hi\n\n```python\nprint('hi')\n```\n"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert blocks[0]["language"] == "python"
        assert "print" in blocks[0]["content"]
        assert blocks[0]["line"] == 3

    def test_no_language(self):
        text = "```\nfoo\n```\n"
        blocks = extract_code_blocks(text)
        assert blocks[0]["language"] == ""

    def test_multiple_blocks(self):
        text = "```js\na()\n```\n\n```rust\nb()\n```\n"
        assert len(extract_code_blocks(text)) == 2


class TestExtractLinks:
    def test_inline_link(self):
        text = "see [docs](https://example.com) for info"
        links = extract_links(text)
        assert len(links) == 1
        assert links[0]["text"] == "docs"
        assert links[0]["url"] == "https://example.com"

    def test_reference_link(self):
        text = "see [docs][ref] for info\n\n[ref]: https://example.com\n"
        links = extract_links(text)
        urls = [l["url"] for l in links]
        assert "https://example.com" in urls

    def test_image_not_included(self):
        text = "![alt](img.png)\n[link](url.html)\n"
        links = extract_links(text)
        assert len(links) == 1
        assert links[0]["text"] == "link"


class TestExtractImages:
    def test_basic_image(self):
        text = "# Title\n\n![screenshot](./img.png)\n"
        imgs = extract_images(text)
        assert len(imgs) == 1
        assert imgs[0]["alt"] == "screenshot"
        assert imgs[0]["url"] == "./img.png"
        assert imgs[0]["line"] == 3


class TestExtractHeadings:
    def test_multiple_levels(self):
        text = "# H1\n## H2\n### H3\n#### H4\n"
        hs = extract_headings(text)
        assert len(hs) == 4
        assert hs[0]["level"] == 1
        assert hs[3]["level"] == 4
        assert hs[0]["text"] == "H1"

    def test_line_numbers(self):
        text = "intro\n\n# Title\n\n## Sub\n"
        hs = extract_headings(text)
        assert hs[0]["line"] == 3
        assert hs[1]["line"] == 5


class TestToc:
    def test_generates_toc(self):
        text = "# Title\n## A\n## B\n### B1\n"
        result = toc(text)
        assert "- Title" in result
        assert "  - A" in result
        assert "    - B1" in result

    def test_empty(self):
        assert toc("no headings here") == ""


class TestFindSection:
    def test_found(self):
        doc = parse(SAMPLE)
        s = find_section(doc, "section one")
        assert s is not None
        assert s.heading == "Section One"

    def test_not_found(self):
        doc = parse(SAMPLE)
        assert find_section(doc, "nonexistent") is None

    def test_case_insensitive(self):
        doc = parse(SAMPLE)
        assert find_section(doc, "NESTED") is not None


class TestInsertSection:
    def test_insert_after(self):
        text = "## A\n\nfirst\n\n## B\n\nsecond\n"
        doc = parse(text)
        new = Section(heading="New", level=2, content="new stuff")
        updated = insert_section(doc, new, after="A")
        headings = [s.heading for s in updated.sections]
        assert headings == ["A", "New", "B"]

    def test_insert_at_end(self):
        doc = parse(SAMPLE)
        new = Section(heading="End", level=2, content="tail")
        updated = insert_section(doc, new)
        assert updated.sections[-1].heading == "End"


class TestRemoveSection:
    def test_remove_top_level(self):
        doc = parse(SAMPLE)
        updated = remove_section(doc, "Section Two")
        headings = [s.heading for s in updated.sections]
        assert "Section Two" not in headings

    def test_remove_nested(self):
        doc = parse(SAMPLE)
        updated = remove_section(doc, "Nested")
        s1 = find_section(updated, "Section One")
        assert s1 is not None
        assert len(s1.children) == 0


class TestUpdateSection:
    def test_update_content(self):
        doc = parse(SAMPLE)
        update_section(doc, "Section One", "replaced")
        s = find_section(doc, "Section One")
        assert s.content == "replaced"


class TestStripMarkdown:
    def test_removes_bold(self):
        assert "bold" in strip_markdown("**bold** text")
        assert "**" not in strip_markdown("**bold** text")

    def test_removes_italic(self):
        assert "*" not in strip_markdown("*italic* text")

    def test_removes_links(self):
        result = strip_markdown("[click](http://x.com)")
        assert "click" in result
        assert "http" not in result

    def test_removes_code(self):
        result = strip_markdown("use `foo()` here")
        assert "foo()" in result
        assert "`" not in result

    def test_removes_headings(self):
        result = strip_markdown("## Heading\n\nBody")
        assert "##" not in result
        assert "Heading" in result


class TestWordCount:
    def test_basic(self):
        assert word_count("hello world") == 2

    def test_excludes_code_blocks(self):
        text = "one two\n\n```python\nthree four five\n```\n\nsix\n"
        assert word_count(text) == 3

    def test_excludes_formatting(self):
        text = "**bold** and *italic* [link](url)"
        count = word_count(text)
        assert count == 4  # bold and italic link


class TestToString:
    def test_roundtrip_has_headings(self):
        doc = parse(SAMPLE)
        result = to_string(doc)
        assert "# My Doc" in result
        assert "## Section One" in result
        assert "### Nested" in result
        assert "## Section Two" in result

    def test_frontmatter_roundtrip(self):
        doc = parse(SAMPLE_WITH_FRONTMATTER)
        result = to_string(doc)
        assert "---" in result
        assert "title: Test Doc" in result
        assert "# Test Doc" in result
