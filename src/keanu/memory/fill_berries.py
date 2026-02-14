#!/usr/bin/env python3
"""
fill_berries.py - Bulk and interactive memory ingestion for memberberry.

Three modes:
  1. interactive  - Walk through prompts to add memories one at a time
  2. bulk         - Import from a structured JSONL file
  3. parse        - Extract memories from markdown/text files (STATUS.md, notes, etc.)

Usage:
  python3 fill_berries.py interactive
  python3 fill_berries.py bulk memories.jsonl
  python3 fill_berries.py parse STATUS.md
  python3 fill_berries.py template > my_memories.jsonl
"""

import json
import sys
import re
from pathlib import Path
from keanu.memory.memberberry import Memory, MemberberryStore, MemoryType

VALID_TYPES = [e.value for e in MemoryType]
VALID_TYPES_STR = ", ".join(VALID_TYPES)

# ============================================================
# SEED PROFILES - the scaffolding questions that shape memory
# ============================================================

# Each memory type has prompt questions that help a person
# articulate memories they didn't know they had.
# These are type-specific because a "goal" lives in a different
# part of your brain than a "lesson."

SEED_PROMPTS = {
    "goal": [
        "What's the one thing you MUST ship/finish in the next 30 days?",
        "What would you build if fear wasn't a factor?",
        "What keeps showing up on your todo list but never gets done?",
        "What does 'done' look like for {project}?",
    ],
    "commitment": [
        "What's a non-negotiable in your weekly routine?",
        "What promise did you make to someone (including yourself) recently?",
        "What would you be ashamed to drop the ball on?",
    ],
    "decision": [
        "What did you recently say NO to?",
        "What's a fork in the road you already chose a side on?",
        "What did you stop doing that you used to do?",
    ],
    "insight": [
        "What's a pattern about yourself you keep noticing?",
        "What do you know now that you wish you knew 6 months ago?",
        "What's the uncomfortable truth about how you work?",
    ],
    "lesson": [
        "What mistake do you keep making?",
        "What's a rule you learned the hard way?",
        "What advice would you give someone starting {project}?",
    ],
    "fact": [
        "What's your current role/situation in one sentence?",
        "Who are the key people in your life relevant to {project}?",
        "What resources/tools/access do you have right now?",
    ],
    "preference": [
        "How do you like to receive information? (bullet points, prose, compressed, etc.)",
        "When are you most productive?",
        "What's your biggest pet peeve in how tools/people communicate with you?",
    ],
}

# Project archetypes with tag suggestions and focus areas.
# These help bootstrap relevant tags without the user having
# to invent a taxonomy from scratch.

PROJECT_ARCHETYPES = {
    "startup": {
        "tags": ["build", "product", "revenue", "users", "fundraising"],
        "focus_prompts": [
            "What's your core value prop in one sentence?",
            "Who is your customer and what pain are you solving?",
            "What's the one metric that matters most right now?",
        ],
    },
    "career": {
        "tags": ["career", "skills", "network", "promotion", "learning"],
        "focus_prompts": [
            "What role are you in and what role do you want?",
            "What skill gap is holding you back most?",
            "Who has the power to change your trajectory?",
        ],
    },
    "health": {
        "tags": ["health", "fitness", "nutrition", "sleep", "mental"],
        "focus_prompts": [
            "What does 'in shape' mean to you specifically?",
            "What's your biggest health obstacle right now?",
            "What worked before that you stopped doing?",
        ],
    },
    "creative": {
        "tags": ["creative", "art", "writing", "music", "craft"],
        "focus_prompts": [
            "What are you making and who is it for?",
            "What's blocking you from finishing?",
            "What's the version you'd be proud to show someone?",
        ],
    },
    "personal": {
        "tags": ["self", "relationships", "faith", "growth", "habits"],
        "focus_prompts": [
            "What area of your life needs the most attention right now?",
            "What relationship matters most to you this year?",
            "What version of yourself are you building toward?",
        ],
    },
    "engineering": {
        "tags": ["build", "code", "infra", "deploy", "debug"],
        "focus_prompts": [
            "What are you building and what's the stack?",
            "What's the hardest unsolved technical problem?",
            "What's your definition of 'shipped'?",
        ],
    },
    "custom": {
        "tags": [],
        "focus_prompts": [
            "Describe your project in one sentence.",
            "What does success look like?",
            "What's the biggest risk?",
        ],
    },
}


# ============================================================
# TEMPLATE GENERATOR (dynamic)
# ============================================================

def generate_template(person: str = "", project: str = "", archetype: str = ""):
    """Generate a dynamic JSONL template based on person and project context.

    If called with no args, generates a generic but useful template.
    If called with context, generates personalized seed prompts as comments
    and example memories shaped to the person/project.
    """
    # Build context string for prompt interpolation
    ctx = {
        "person": person or "the user",
        "project": project or "this project",
    }

    # Pick archetype
    arch = PROJECT_ARCHETYPES.get(archetype, PROJECT_ARCHETYPES["custom"])
    base_tags = arch["tags"]

    # Header comments (JSONL readers skip lines starting with # or //)
    lines = []
    lines.append(f"// memberberry seeds for: {ctx['person']}")
    lines.append(f"// project: {ctx['project']}")
    if archetype:
        lines.append(f"// archetype: {archetype} (suggested tags: {', '.join(base_tags)})")
    lines.append(f"// generated: {__import__('datetime').datetime.now().isoformat()[:19]}")
    lines.append("//")
    lines.append("// INSTRUCTIONS:")
    lines.append("// 1. Answer each prompt below by editing the 'content' field")
    lines.append("// 2. Adjust importance (1-10), tags, and context as needed")
    lines.append("// 3. Delete any lines you don't need")
    lines.append("// 4. Add more lines following the same JSON format")
    lines.append(f"// 5. Import: python3 fill_berries.py bulk <this_file>")
    lines.append("//")

    # Generate seed memories for each type
    for mtype in VALID_TYPES:
        prompts = SEED_PROMPTS.get(mtype, [])
        if not prompts:
            continue

        lines.append(f"// --- {mtype.upper()} ---")

        for i, prompt in enumerate(prompts):
            # Interpolate project name into prompts
            rendered_prompt = prompt.format(project=ctx["project"])
            lines.append(f"// Q: {rendered_prompt}")

            # Generate a placeholder memory
            seed = {
                "content": f"[ANSWER: {rendered_prompt}]",
                "memory_type": mtype,
                "tags": base_tags[:2] if base_tags else [mtype],
                "importance": 5,
                "context": "",
                "source": "seed"
            }

            # Bump importance for first item of goals and commitments
            if mtype in ("goal", "commitment") and i == 0:
                seed["importance"] = 8

            lines.append(json.dumps(seed))

        lines.append("//")

    # Add archetype-specific focus prompts
    if arch["focus_prompts"]:
        lines.append(f"// --- PROJECT FOCUS ({archetype or 'general'}) ---")
        for prompt in arch["focus_prompts"]:
            rendered = prompt.format(project=ctx["project"])
            lines.append(f"// Q: {rendered}")
            seed = {
                "content": f"[ANSWER: {rendered}]",
                "memory_type": "fact",
                "tags": base_tags[:3] if base_tags else ["project"],
                "importance": 7,
                "context": f"Project context for {ctx['project']}",
                "source": "seed"
            }
            lines.append(json.dumps(seed))

    for line in lines:
        print(line)


# ============================================================
# BULK IMPORT (JSONL)
# ============================================================

def bulk_import(filepath: str):
    """Import memories from a JSONL file (one JSON object per line)."""
    path = Path(filepath)
    if not path.exists():
        print(f"File not found: {filepath}")
        print("Generate a template with: python3 fill_berries.py template > my_memories.jsonl")
        sys.exit(1)

    store = MemberberryStore()
    imported = 0
    errors = 0

    with open(path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue  # skip blanks and comments

            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  Line {line_num}: JSON parse error: {e}")
                errors += 1
                continue

            # Validate
            content = data.get("content", "").strip()
            mtype = data.get("memory_type", "").strip()

            if not content:
                print(f"  Line {line_num}: Missing 'content', skipping")
                errors += 1
                continue

            if mtype not in VALID_TYPES:
                print(f"  Line {line_num}: Invalid type '{mtype}' (valid: {VALID_TYPES_STR}), skipping")
                errors += 1
                continue

            memory = Memory(
                content=content,
                memory_type=mtype,
                tags=data.get("tags", []),
                importance=min(max(int(data.get("importance", 5)), 1), 10),
                context=data.get("context", ""),
                source=data.get("source", "bulk_import"),
            )

            store.remember(memory)
            imported += 1
            print(f"  [{mtype[:4].upper()}] {content}")

    print(f"\nDone. Imported {imported} memories. {errors} errors.")


# ============================================================
# INTERACTIVE MODE
# ============================================================

def interactive():
    """Walk through adding memories one at a time."""
    store = MemberberryStore()

    print("\n  fill_berries interactive mode")
    print("  Let's set the context first.\n")

    person = input("  Your name (or enter to skip) > ").strip()
    project = input("  Project name (or enter to skip) > ").strip()

    # Pick archetype
    archetypes = list(PROJECT_ARCHETYPES.keys())
    print(f"  Project type: {', '.join(archetypes)}")
    archetype = input("  Pick one (or enter for custom) > ").strip().lower()
    if archetype not in PROJECT_ARCHETYPES:
        archetype = "custom"

    arch = PROJECT_ARCHETYPES[archetype]
    suggested_tags = arch["tags"]

    print(f"\n  Context: {person or 'anonymous'} / {project or 'general'} / {archetype}")
    if suggested_tags:
        print(f"  Suggested tags: {', '.join(suggested_tags)}")

    # Guided mode: walk through seed prompts per type
    print(f"\n  I'll walk you through prompts for each memory type.")
    print(f"  Types: {VALID_TYPES_STR}")
    print("  Enter 'skip' to skip a prompt, 'done' to finish early.\n")

    count = 0

    for mtype in VALID_TYPES:
        prompts = SEED_PROMPTS.get(mtype, [])
        if not prompts:
            continue

        print(f"  --- {mtype.upper()} ---")

        for prompt in prompts:
            rendered = prompt.format(project=project or "this project")
            content = input(f"  {rendered}\n  > ").strip()

            if content.lower() in ("done", "q", "quit"):
                print(f"\n  Done early. Added {count} memories.")
                store._save_memories()
                return
            if content.lower() in ("skip", "s", ""):
                continue

            # Quick tag selection
            if suggested_tags:
                tag_prompt = f"  Tags? ({', '.join(suggested_tags)}) or custom > "
            else:
                tag_prompt = "  Tags (comma-separated) > "
            tags_raw = input(tag_prompt).strip()
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else suggested_tags[:2]

            imp_raw = input("  Importance 1-10 [5] > ").strip()
            try:
                importance = min(max(int(imp_raw), 1), 10) if imp_raw else 5
            except ValueError:
                importance = 5

            memory = Memory(
                content=content,
                memory_type=mtype,
                tags=tags,
                importance=importance,
                context=f"{person or 'user'} / {project or 'general'}",
                source="interactive",
            )

            mid = store.remember(memory)
            count += 1
            print(f"  Stored! [{mtype}] id:{mid}\n")

    # Archetype focus prompts
    if arch.get("focus_prompts"):
        print(f"  --- PROJECT FOCUS ---")
        for prompt in arch["focus_prompts"]:
            rendered = prompt.format(project=project or "this project")
            content = input(f"  {rendered}\n  > ").strip()
            if content.lower() in ("done", "q", "quit"):
                break
            if content.lower() in ("skip", "s", ""):
                continue

            memory = Memory(
                content=content,
                memory_type="fact",
                tags=suggested_tags[:3] or ["project"],
                importance=7,
                context=f"Project context: {project or 'general'}",
                source="interactive",
            )
            store.remember(memory)
            count += 1
            print(f"  Stored! [fact] project context\n")

    print(f"\nDone. Added {count} memories.")
    s = store.stats()
    print(f"Total memories in store: {s['total_memories']}")


# ============================================================
# MARKDOWN PARSER
# ============================================================

# Heuristic patterns for extracting memories from markdown/text
GOAL_PATTERNS = [
    r"(?:goal|objective|target|aim|want to|need to|plan to|going to)\s*[:>-]?\s*(.+)",
    r"(?:TODO|NEXT|ACTION)\s*[:>-]?\s*(.+)",
]

DECISION_PATTERNS = [
    r"(?:decided|decision|chose|choosing|pivoting|moving to)\s*[:>-]?\s*(.+)",
    r"(?:will not|won't|stopped|quit|dropped)\s*[:>-]?\s*(.+)",
]

INSIGHT_PATTERNS = [
    r"(?:realized|insight|learned that|noticed|pattern|observation)\s*[:>-]?\s*(.+)",
    r"(?:key takeaway|the truth is|what I know)\s*[:>-]?\s*(.+)",
]

COMMITMENT_PATTERNS = [
    r"(?:committed to|commitment|promise|every day|every week|always|never)\s*[:>-]?\s*(.+)",
]

LESSON_PATTERNS = [
    r"(?:lesson|mistake|never again|don't|avoid)\s*[:>-]?\s*(.+)",
]


def classify_line(line: str) -> tuple:
    """Try to classify a line of text into a memory type.
    Returns (memory_type, content) or (None, None)."""

    clean = line.strip().lstrip("-*>#").strip()
    if len(clean) < 10 or len(clean) > 300:
        return None, None

    for pattern in GOAL_PATTERNS:
        m = re.search(pattern, clean, re.IGNORECASE)
        if m:
            return "goal", m.group(1).strip() or clean

    for pattern in DECISION_PATTERNS:
        m = re.search(pattern, clean, re.IGNORECASE)
        if m:
            return "decision", m.group(1).strip() or clean

    for pattern in INSIGHT_PATTERNS:
        m = re.search(pattern, clean, re.IGNORECASE)
        if m:
            return "insight", m.group(1).strip() or clean

    for pattern in COMMITMENT_PATTERNS:
        m = re.search(pattern, clean, re.IGNORECASE)
        if m:
            return "commitment", m.group(1).strip() or clean

    for pattern in LESSON_PATTERNS:
        m = re.search(pattern, clean, re.IGNORECASE)
        if m:
            return "lesson", m.group(1).strip() or clean

    return None, None


def extract_tags_from_headers(text: str) -> dict:
    """Build a mapping of line ranges to tags based on markdown headers."""
    lines = text.split("\n")
    tag_map = {}  # line_num -> [tags]
    current_tags = []

    for i, line in enumerate(lines):
        header_match = re.match(r"^#{1,3}\s+(.+)", line)
        if header_match:
            header_text = header_match.group(1).strip().lower()
            # Convert header to potential tags
            current_tags = [
                w for w in re.findall(r"[a-z]+", header_text)
                if len(w) > 2 and w not in ("the", "and", "for", "with", "from", "this", "that")
            ][:3]
        tag_map[i] = list(current_tags)

    return tag_map


def parse_markdown(filepath: str):
    """Extract memories from a markdown or text file."""
    path = Path(filepath)
    if not path.exists():
        print(f"File not found: {filepath}")
        sys.exit(1)

    text = path.read_text()
    lines = text.split("\n")
    tag_map = extract_tags_from_headers(text)

    store = MemberberryStore()
    candidates = []

    for i, line in enumerate(lines):
        mtype, content = classify_line(line)
        if mtype and content:
            tags = tag_map.get(i, [])
            candidates.append({
                "line": i + 1,
                "memory_type": mtype,
                "content": content,
                "tags": tags,
            })

    if not candidates:
        print(f"No extractable memories found in {filepath}.")
        print("Try using 'bulk' mode with a JSONL file instead.")
        return

    print(f"\n  Found {len(candidates)} candidate memories in {filepath}:\n")

    for c in candidates:
        tags_str = ", ".join(c["tags"]) if c["tags"] else "none"
        print(f"  L{c['line']} [{c['memory_type'][:4].upper()}] {c['content']}")
        print(f"    tags: {tags_str}")

    print(f"\n  Import all? (y/n/pick) ", end="")
    choice = input().strip().lower()

    if choice == "y":
        imported = 0
        for c in candidates:
            memory = Memory(
                content=c["content"],
                memory_type=c["memory_type"],
                tags=c["tags"],
                importance=5,
                source=f"parsed:{filepath}",
            )
            store.remember(memory)
            imported += 1
        print(f"  Imported {imported} memories.")

    elif choice == "pick":
        imported = 0
        for c in candidates:
            print(f"\n  [{c['memory_type'][:4].upper()}] {c['content']}")
            yn = input("  Import? (y/n/edit) > ").strip().lower()
            if yn == "y":
                memory = Memory(
                    content=c["content"],
                    memory_type=c["memory_type"],
                    tags=c["tags"],
                    importance=5,
                    source=f"parsed:{filepath}",
                )
                store.remember(memory)
                imported += 1
            elif yn == "edit":
                new_content = input("  New content > ").strip() or c["content"]
                new_type = input(f"  Type ({VALID_TYPES_STR}) [{c['memory_type']}] > ").strip() or c["memory_type"]
                new_tags = input(f"  Tags [{','.join(c['tags'])}] > ").strip()
                tags = [t.strip() for t in new_tags.split(",") if t.strip()] if new_tags else c["tags"]
                imp = input("  Importance 1-10 [5] > ").strip()
                importance = int(imp) if imp else 5

                memory = Memory(
                    content=new_content,
                    memory_type=new_type if new_type in VALID_TYPES else c["memory_type"],
                    tags=tags,
                    importance=min(max(importance, 1), 10),
                    source=f"parsed:{filepath}",
                )
                store.remember(memory)
                imported += 1
        print(f"\n  Imported {imported} memories.")
    else:
        print("  Cancelled.")


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    args = sys.argv[1:]

    if not args:
        archetypes = ", ".join(PROJECT_ARCHETYPES.keys())
        print(f"""
fill_berries.py - Load memories into memberberry

MODES:
  interactive              Guided prompts shaped by person, project, and archetype
  bulk <file.jsonl>        Import from a JSONL file (one JSON per line)
  parse <file.md>          Extract memories from markdown/text files
  template                 Print a dynamic JSONL template to stdout

TEMPLATE FLAGS:
  --person "Name"          Who are these memories for?
  --project "Project"      What project/goal is this about?
  --archetype TYPE         Project type: {archetypes}

QUICK START:
  python3 fill_berries.py template --person "Drew" --project "memberberry" --archetype engineering > seeds.jsonl
  # Edit seeds.jsonl, answer the prompts
  python3 fill_berries.py bulk seeds.jsonl

  # Or guided interactive:
  python3 fill_berries.py interactive

  # Or extract from existing docs:
  python3 fill_berries.py parse STATUS.md
        """)
        return

    mode = args[0].lower()

    if mode == "interactive":
        interactive()
    elif mode == "bulk" and len(args) > 1:
        bulk_import(args[1])
    elif mode == "parse" and len(args) > 1:
        parse_markdown(args[1])
    elif mode == "template":
        # Parse flags
        person = ""
        project = ""
        archetype = ""
        i = 1
        while i < len(args):
            if args[i] == "--person" and i + 1 < len(args):
                person = args[i + 1]
                i += 2
            elif args[i] == "--project" and i + 1 < len(args):
                project = args[i + 1]
                i += 2
            elif args[i] == "--archetype" and i + 1 < len(args):
                archetype = args[i + 1]
                i += 2
            else:
                i += 1
        generate_template(person=person, project=project, archetype=archetype)
    else:
        print(f"Unknown mode or missing argument: {' '.join(args)}")
        print("Run without args for help.")


if __name__ == "__main__":
    main()
