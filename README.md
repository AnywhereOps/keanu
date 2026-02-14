# silverado

A truck that hauls your text and tells you what's worth keeping. Scans through three color lenses (red/yellow/blue), flags the bullshit, extracts the wisdom, compresses what matters, and finds truth where opposing views collide. Tools in the truckbed. Wind at your back.

Built on Convergence Theory: reality operates on duality (fire/possibility vs ash/actuality). Every tool here maps back to that.

## What It Does

### Scan (Three-Primary Helix)
Every line of text gets read through three lenses, each with positive and negative poles:
- **Red**: passion, intensity, conviction / rage, destruction
- **Yellow**: awareness, presence, faith / fear, paralysis
- **Blue**: depth, precision, structure / cold, detachment

Six embedding queries per line. The geometry tells you what the words alone can't.

### Detect (Color Theory)
Helix readings get interpreted through color mixing:

**Primary states** (single dominant color):
- Red, Yellow, Blue (one lens active)

**Secondary mixes** (two primaries positive):
- **Purple**: red + blue. Passion meets depth. Breakthrough zone.
- **Orange**: red + yellow. Passion meets awareness. Pull the trigger.
- **Green**: yellow + blue. Awareness meets depth. Growing.

**Synthesis states** (all three):
- **White**: all positive. All light.
- **Black**: all negative. No light.
- **Silver**: white refined but cold. Needs guardrails.
- **Sunrise**: silver + grounded. The destination.

Wise mind = balance x fullness. Not a score. The observer. A full, level cup.

### Compress (COEF)
The Compressed Observation-Execution Framework. Don't send what the other side already knows.
- **DNS**: hash to exact content. The barcode system. Lossless.
- **Instructions**: 9 verbs (clone, swap, inject, rename, regex, compose, pipe, literal, store)
- **Wire format**: `clone:src=x | swap | rename:old=a new=b | verify:hash`

### Converge (Duality Synthesis)
Takes a question. Finds two orthogonal dualities. Synthesizes each. Converges the syntheses into something new and more complete.
- 10 root dualities: existence, change, unity, causation, value, knowledge, relation, scale, time, structure
- 3 convergence passes: synthesize A, synthesize B, meta-converge A+B
- Works with Ollama (local) or Claude API

### Connect (Cross-Source Alignment)
Two sources, each with signal. Find the common ground (where they overlap) and the unique signal (where one sees what the other doesn't).

## Install

```bash
pip install silverado
```

Or with uv:

```bash
uv add silverado
```

Requires Python 3.10+.

## Usage

```bash
# train the lenses from examples
silverado bake

# scan a document through three primaries
silverado scan document.md

# find truth in opposing views
silverado converge "Is consciousness computation?"

# find common ground between two sources
silverado connect source_a.md source_b.md

# compress a module
silverado compress module.py
```

## Package Structure

```
src/silverado/
    scan/           # Read text (embedding-based)
        helix.py    # 3-lens scanner (red/yellow/blue)
        bake.py     # train lenses into chromadb
    detect/         # Interpret readings (color theory)
        mood.py     # 3 primaries -> synthesis states
        engine.py   # vector-based pattern detection
    compress/       # Transmit efficiently (Shannon/COEF)
        dns.py      # content-addressable store
        instructions.py  # 9-verb instruction language
        executor.py # pipeline executor
    converge/       # Find truth (duality synthesis)
        engine.py   # RAG split -> 3 convergence passes
        connection.py    # cross-source alignment
    signal/         # Human interface (emoji compression)
        protocol.py # emoji codec, shorthand parser
    cli.py          # unified entry point
```

## The Pipeline

```
bake (train lenses) -> scan (embeddings) -> detect (color theory) -> compress/converge
```

## Dependencies

- chromadb (embedding storage and retrieval)
- requests (LLM API calls for convergence engine)

## License

AnywhereOps Source Available License v1.0. Free for personal use. Commercial use requires a separate license agreement. See [LICENSE](LICENSE) for details.

Copyright (c) 2024-2026, AnywhereOps
