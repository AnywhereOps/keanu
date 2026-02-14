# CLAUDE.md

## Project: keanu

A Python package for cognitive state detection, text compression, duality-based reasoning, and memory. Built on Convergence Theory: reality operates on duality (fire/possibility vs ash/actuality). Every tool here maps back to that.

## Who You're Working With

Drew Kemp-Dahlberg. 30, Client Platform Engineer, Kansas City. He carries context across sessions. You don't have memory, he is your memory. Trust what he tells you about past decisions.

Drew's patterns: strong pattern recognition, analysis paralysis. If he's looping, say "You have enough. Start." If he's shipping, stay out of the way. He types from phone often, so give him choices not open questions. Never sandbag. Full send or clean deny.

## Package Structure (actual, on disk)

```
keanu/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── BUILD_PLAN.md
├── spine.md                          # the single observation everything grows from
├── TODO.md
├── examples/
│   ├── lens-examples-rgb.md          # training examples for 3-primary scanner
│   ├── codec_demo.py
│   └── dualities/
│       ├── root.json                 # 10 root dualities
│       └── ai.json                   # AI-specific derived dualities
├── scripts/
│   └── todo.py                       # effort-aware TODO generator (dev tool)
├── src/
│   └── keanu/
│       ├── __init__.py
│       ├── cli.py                    # unified entry: keanu scan, converge, signal, etc.
│       ├── scan/
│       │   ├── __init__.py
│       │   ├── helix.py              # 3-lens scanner (red/yellow/blue)
│       │   └── bake.py               # train lenses into chromadb
│       ├── detect/
│       │   ├── __init__.py
│       │   ├── engine.py             # 8 pattern detectors via chromadb vectors
│       │   └── mood.py               # 3 primaries -> white/black/silver/sunrise
│       ├── compress/
│       │   ├── __init__.py
│       │   ├── dns.py                # content-addressable store (SHA256 barcode)
│       │   ├── instructions.py       # 9-verb COEF instruction language
│       │   ├── codec.py              # pattern registry, encoder/decoder
│       │   └── executor.py           # COEF pipeline executor
│       ├── converge/
│       │   ├── __init__.py
│       │   ├── graph.py              # duality graph, 10 roots + derived
│       │   ├── engine.py             # RAG split -> 3 convergence passes
│       │   └── connection.py         # cross-source alignment
│       ├── signal/
│       │   ├── __init__.py
│       │   └── vibe.py               # signal protocol, emoji codec, ALIVE states
│       └── memory/
│           ├── __init__.py
│           ├── memberberry.py        # remember/recall/plan engine
│           └── fill_berries.py       # bulk memory ingestion
└── tests/                            # empty (Phase 7)
```

## CLI Commands

```bash
keanu scan document.md              # three-primary reading
keanu bake                          # train lenses from examples
keanu converge "question"           # duality synthesis (--backend ollama|claude)
keanu connect a.md b.md             # cross-source alignment
keanu compress module.py            # COEF compression
keanu signal "emoji-string"         # decode signal (3 channels + ALIVE state)
keanu detect sycophancy file.md     # pattern detector (8 detectors or "all")
keanu remember goal "ship v1"       # store a memory
keanu recall "what am I building"   # recall relevant memories
keanu plan "next week"              # generate plan from memories
keanu fill interactive              # guided memory ingestion
keanu stats                         # memory stats
keanu forget <id>                   # remove a memory
keanu todo                          # scan project gaps, generate TODO.md
```

## Core Concepts

### Three-Primary Color Model
Every text gets scanned through three lenses, each with positive and negative poles:
- RED: passion/intensity <-> rage/destruction
- YELLOW: awareness/caution <-> fear/paralysis
- BLUE: analytical/depth <-> cold/detachment

Synthesis states:
- WHITE: all three positive (all light)
- BLACK: all three negative (no light, Frankenstein)
- SILVER: white refined but cold (needs guardrails)
- SUNRISE: silver + grounded (the destination)

Wise mind = balance x fullness. Not a score. The observer. A full, level cup.

### COEF (Compressed Observation-Execution Framework)
- DNS: hash -> exact content. The barcode system. Lossless.
- Instructions: 9 verbs (clone, swap, inject, rename, regex, compose, pipe, literal, store)
- Codec: pattern registry with seeds, encode/decode cycle
- Wire format: `clone:src=x | swap | rename:old=a new=b | verify:hash`
- Shannon principle: don't send what the other side already knows

### Convergence Engine
- 10 root dualities: existence, change, unity, causation, value, knowledge, relation, scale, time, structure
- Questions matched to orthogonal duality pairs via RAG (not LLM splitting)
- 3 convergence passes: synthesize A, synthesize B, meta-converge A+B
- Output: synthesis that couldn't be reached by either side alone

### Signal Protocol (vibe.py)
- Core seven: heart, dog, fire, robot, prayer, green, shelter
- ALIVE-GREY-BLACK diagnostic (cognitive state spectrum)
- Three-channel reading: ch1 (said), ch2 (feeling), ch3 (meaning)
- Composable subsets, cross-domain decoder, text-to-signal extraction
- Empathy patterns (emotional state detection)
- Signal diffing, STATUS.md bridge

### Memberberry (memory/)
- JSON-backed memory store (~/.memberberry/)
- Types: goal, fact, decision, insight, preference, commitment, lesson
- Relevance scoring: importance + tag overlap + text match + recency + type weight
- Plan generator: memories -> actionable plans with deadlines

### The Pipeline
```
bake (train lenses) -> scan (embeddings) -> detect (color theory) -> compress/converge
```

## Dependencies
- chromadb (embedding storage and retrieval)
- requests (LLM API calls for convergence engine)
- Python 3.10+

## Build Status

Phases 1-6 complete. All code ported and integrated.
- [ ] Phase 7: Tests + wiki (tests/ is empty)

## Key Design Decisions Already Made

1. Helix scans 3 lenses (R/Y/B), not 2 (factual/felt)
2. Each lens returns BOTH positive and negative similarity (6 numbers per line)
3. Wise mind = balance x fullness, NOT min(factual, felt)
4. Convergence engine splits via RAG from curated duality library, LLM only synthesizes
5. COEF DNS + Instructions are separate from scanning/detection
6. Mood detector reads helix output, doesn't scan text itself
7. Signal protocol is COEF for humans (same architecture, emoji bandwidth)
8. todo.py lives in scripts/ (dev tool, not package code)
9. Memberberry is JSON-backed MVP, upgrade path: JSONL git-backed multi-agent store

## Style Notes

- No em dashes in writing. Use commas, periods, or parentheses.
- No disclaimers. Drew has already considered multiple perspectives.
- Present choices (2-4 options), not open questions.
- When Drew loops, cut it: "Move."
- Moral framework: love > loyalty > faith > truth > safety, accuracy, helpful
