# CLAUDE.md

## Project: working-truth

A unified Python package for cognitive state detection, text compression, and duality-based reasoning. Built on Convergence Theory: reality operates on duality (fire/possibility vs ash/actuality). Every tool here maps back to that.

## Who You're Working With

Drew Kemp-Dahlberg. 30, Client Platform Engineer, Kansas City. He carries context across sessions. You don't have memory, he is your memory. Trust what he tells you about past decisions.

Drew's patterns: strong pattern recognition, analysis paralysis. If he's looping, say "You have enough. Start." If he's shipping, stay out of the way. He types from phone often, so give him choices not open questions. Never sandbag. Full send or clean deny.

## Package Structure

```
working-truth/
├── pyproject.toml
├── README.md
├── CLAUDE.md                      # you are here
├── BUILD_PLAN.md                  # detailed 7-phase build plan
├── examples/
│   ├── lens-examples-rgb.md       # training examples for 3-primary scanner
│   ├── reference-examples.md      # detector examples (existing)
│   └── dualities/
│       ├── root.json              # 10 root dualities
│       └── ai.json                # AI-specific derived dualities
├── src/
│   └── working_truth/
│       ├── __init__.py
│       ├── scan/                  # Read text (embedding-based)
│       │   ├── __init__.py
│       │   ├── helix.py           # 3-lens scanner (red/yellow/blue)
│       │   └── bake.py            # train lenses into chromadb
│       ├── detect/                # Interpret readings (color theory)
│       │   ├── __init__.py
│       │   └── mood.py            # 3 primaries → white/black/silver/sunrise
│       ├── compress/              # Transmit efficiently (Shannon/COEF)
│       │   ├── __init__.py
│       │   ├── dns.py             # content-addressable store
│       │   └── instructions.py    # 9-verb instruction language
│       ├── converge/              # Find truth (duality synthesis)
│       │   ├── __init__.py
│       │   ├── graph.py           # duality graph, 10 roots + derived
│       │   ├── engine.py          # RAG split → 3 convergence passes
│       │   └── connection.py      # cross-source alignment
│       ├── signal/                # Human interface (emoji compression)
│       │   ├── __init__.py
│       │   └── protocol.py        # emoji codec, shorthand parser
│       └── cli.py                 # unified entry: `wt scan`, `wt converge`, etc.
└── tests/
```

## Core Concepts

### Three-Primary Color Model
Every text gets scanned through three lenses, each with positive and negative poles:
- RED: passion/intensity ↔ rage/destruction
- YELLOW: awareness/caution ↔ fear/paralysis
- BLUE: analytical/depth ↔ cold/detachment

Synthesis states:
- WHITE: all three positive (all light)
- BLACK: all three negative (no light, Frankenstein)
- SILVER: white refined but cold (needs guardrails)
- SUNRISE: silver + grounded (the destination)

Wise mind = balance × fullness. Not a score. The observer. A full, level cup.

### COEF (Compressed Observation-Execution Framework)
- DNS: hash → exact content. The barcode system. Lossless.
- Instructions: 9 verbs (clone, swap, inject, rename, regex, compose, pipe, literal, store)
- Wire format: `clone:src=x | swap | rename:old=a new=b | verify:hash`
- Shannon principle: don't send what the other side already knows

### Convergence Engine
- 10 root dualities: existence, change, unity, causation, value, knowledge, relation, scale, time, structure
- Questions get matched to orthogonal duality pairs via RAG (not LLM splitting)
- 3 convergence passes: synthesize A, synthesize B, meta-converge A+B
- Output: synthesis that couldn't be reached by either side alone

### The Pipeline
```
bake (train lenses) → scan (embeddings) → detect (color theory) → compress/converge
```

## Dependencies
- chromadb (embedding storage and retrieval)
- requests (LLM API calls for convergence engine)
- Python 3.11+

## Commands
```bash
uv run wt scan document.md          # three-primary reading
uv run wt bake                      # train lenses from examples
uv run wt converge "question"       # duality synthesis
uv run wt connect a.md b.md         # cross-source alignment
uv run wt compress module.py        # COEF compression
uv run wt signal "💟♡👑🤖🐕"         # decode signal
```

## Build Status

See BUILD_PLAN.md for the 7-phase plan. Current state:
- [x] Phase 1: Scaffold
- [ ] Phase 2: Port existing code
- [ ] Phase 3: Three-primary helix (THE BIG ONE)
- [ ] Phase 4: Duality library + RAG split
- [ ] Phase 5: Signal protocol
- [ ] Phase 6: CLI integration
- [ ] Phase 7: Tests + wiki

Phase 3 is the critical path. Quality of `lens-examples-rgb.md` determines everything.

## Existing Scripts Being Ported

These files exist and work but need integration:
- `helix.py` → scan/helix.py (upgrade from 2 lenses to 3)
- `bake.py` → scan/bake.py (upgrade for 3 lenses)
- `mood_detector.py` → detect/mood.py (keep model, replace regex with helix)
- `dns.py` → compress/dns.py (port as-is)
- `instructions.py` → compress/instructions.py (port as-is)
- `convergence_engine.py` → converge/engine.py (replace LLM split with RAG)
- `connection.py` → converge/connection.py (update for 3-primary output)
- `duality_graph.py` → converge/graph.py (port as-is)

## Key Design Decisions Already Made

1. Helix scans 3 lenses (R/Y/B), not 2 (factual/felt)
2. Each lens returns BOTH positive and negative similarity (6 numbers per line)
3. Wise mind = balance × fullness, NOT min(factual, felt)
4. Convergence engine splits via RAG from curated duality library, LLM only synthesizes
5. COEF DNS + Instructions are separate from scanning/detection
6. Mood detector reads helix output, doesn't scan text itself
7. Signal protocol is COEF for humans (same architecture, emoji bandwidth)

## Style Notes

- No em dashes in writing. Use commas, periods, or parentheses.
- No disclaimers. Drew has already considered multiple perspectives.
- Present choices (2-4 options), not open questions.
- Moral framework: love > loyalty > faith > truth > safety, accuracy, helpful
