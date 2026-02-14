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

**`keanu detect`** interprets helix output through color theory. Maps readings to states: primary, secondary, or synthesis.

**`keanu converge`** takes a question, finds two orthogonal dualities, synthesizes each, then converges the syntheses into something neither could reach alone. Works with Ollama (local) or Claude API.

**`keanu connect`** finds common ground between two sources and surfaces the unique signal each one carries.

**`keanu compress`** applies COEF (Compressed Observation-Execution Framework). Don't send what the other side already knows. Content-addressable DNS, 9-verb instruction language, wire format: `clone:src=x | swap | rename:old=a new=b | verify:hash`

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
        engine.py       # vector pattern detection
    compress/           # Transmit (Shannon/COEF)
        dns.py          # content-addressable store
        instructions.py # 9-verb instruction language
        executor.py     # pipeline executor
    converge/           # Truth (duality synthesis)
        engine.py       # split -> 3 convergence passes
        connection.py   # cross-source alignment
    signal/             # Voice (human interface)
        protocol.py     # emoji codec, shorthand
    cli.py              # entry point
```

```
bake (train) -> scan (embed) -> detect (interpret) -> compress / converge
```

## Lineage

Grew out of 7 months, 208 commits, 35 frameworks, 0 deployed tools. Keanu is the part that actually works.

## License

AnywhereOps Source Available License v1.0. Free for personal use. Commercial use requires a separate license agreement. COEF is core IP. See [LICENSE](LICENSE) for details.

Copyright (c) 2024-2026, AnywhereOps
