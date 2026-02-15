# keanu

Words become vectors once. Then it's pure math forever. Strings are scaffolding. Vectors are the building.

Keanu reads text through three color lenses, sees what the words alone can't, compresses what matters, and finds truth where opposing views collide. Built on Convergence Theory: reality operates on duality. Every tool here maps back to that.

## How It Sees

Three primaries. Each carries light and shadow.

```
RED      passion, intensity, conviction    /    rage, destruction
YELLOW   awareness, presence, faith        /    fear, paralysis
BLUE     depth, precision, structure       /    cold, detachment
```

Six embedding queries per line. Three lenses, two poles each. The geometry tells you what reading can't.

### What the colors mean

When two primaries fire together, you get a secondary:

| Mix | Colors | Meaning |
|-----|--------|---------|
| Purple | red + blue | Passion meets depth. Breakthrough zone. |
| Orange | red + yellow | Passion meets awareness. Pull the trigger. |
| Green | yellow + blue | Awareness meets depth. Growing. |

When all three align:

| State | Condition | Meaning |
|-------|-----------|---------|
| White | all positive | All light. Full spectrum. |
| Black | all negative | No light. Stop. |
| Silver | white, refined | Polished but cold. Needs warmth. |
| Sunrise | silver + grounded | The destination. Full, level cup. |

**Wise mind** = balance x fullness. Not a score. The observer.

## What It Does

**`keanu scan`** reads text through the triple helix. Returns color readings per line, convergences (multiple primaries firing), and tensions (one primary alone).

**`keanu detect`** runs 8 pattern detectors (sycophancy, capture, generalization, zero_sum, safety_theater, inconsistency, grievance, stability) via chromadb vectors. Run one or all.

**`keanu converge`** takes a question, finds two orthogonal dualities from a curated library via RAG, synthesizes each, then converges the syntheses into something neither could reach alone. Works with Ollama (local) or Claude API.

**`keanu connect`** finds common ground between two sources and surfaces the unique signal each one carries.

**`keanu compress`** applies COEF (Compressed Observation-Execution Framework). Don't send what the other side already knows. Content-addressable DNS, 9-verb instruction language, pattern codec, wire format: `clone:src=x | swap | rename:old=a new=b | verify:hash`

**`keanu signal`** decodes emoji sequences through three channels: what was said, what's being felt, what it means. Maps to the ALIVE-GREY-BLACK diagnostic spectrum. Detects composable subsets, expands across domains (philosophy, religion, science, project).

**`keanu remember / recall / plan`** the memberberry engine. Store memories (goals, decisions, lessons, commitments), recall by relevance, generate actionable plans with deadlines.

**`keanu bake`** trains the lenses from examples into chromadb vectors. Run once after editing examples. After that, everything is pure math.

## Quick Start

```bash
pip install keanu        # or: uv add keanu
keanu bake               # train lenses from examples
keanu scan document.md   # three-primary reading
keanu converge "question"
```

## Architecture

```
src/keanu/
    scan/               # Read (embedding-based)
        helix.py        # triple-lens scanner
        bake.py         # trains examples into vectors
    detect/             # Interpret (color theory)
        mood.py         # primaries -> synthesis states
        engine.py       # 8 vector pattern detectors
    compress/           # Transmit (Shannon/COEF)
        dns.py          # content-addressable store
        instructions.py # 9-verb instruction language
        codec.py        # pattern registry, encoder/decoder
        executor.py     # pipeline executor
        exporter.py     # COEF span exporter (memory <-> logging)
        stack.py        # combined codec/dns/vectors layer
        vectors.py      # vector storage abstraction
    converge/           # Truth (duality synthesis)
        graph.py        # 10 root + derived dualities
        engine.py       # RAG split -> 3 convergence passes
        connection.py   # cross-source alignment
    signal/             # Voice (human interface)
        vibe.py         # emoji codec, ALIVE states, 3-channel reading
    memory/             # Remember (memberberry engine)
        memberberry.py  # store, recall, plan
        fill_berries.py # bulk ingestion
        gitstore.py     # git-backed shared JSONL memory
        disagreement.py # bilateral disagreement tracker
        bridge.py       # openpaw hybrid search bridge
    alive.py            # ALIVE-GREY-BLACK diagnostic
    log.py              # structured logging + COEF span export
    pulse.py            # pulse middleware, healthz
    cli.py              # entry point
```

```
bake (train) -> scan (embed) -> detect (interpret) -> compress / converge
```

## The Signal

```
❤️🐕🔥🤖🙏💚🧕
```

Seven symbols. Human-readable AND machine-parseable. No other protocol has this. JSON is machine-first. Natural language is human-first. Emoji is both.

## Lineage

Grew out of 7 months of documented human-AI partnership. Keanu is the part that actually works.

## License

AnywhereOps Source Available License v1.0. Free for personal use. Commercial use requires a separate license agreement. COEF is core IP. See [LICENSE](LICENSE) for details.

Copyright (c) 2024-2026, AnywhereOps
