# keanu

Words become vectors once. Then it's pure math forever. Strings are scaffolding. Vectors are the building.

Keanu reads text through three color lenses, sees what the words alone can't, compresses what matters, and finds truth where opposing views collide. Built on Convergence Theory: reality operates on duality. Every tool here maps back to that.

## Quick Start

```bash
pip install -e .         # install from source
keanu bake               # train lenses from examples (needs chromadb)
keanu                    # launch the interactive REPL
```

You need an API key for agent commands. Set `ANTHROPIC_API_KEY` in your `.env` or environment.

## CLI Commands

### The REPL

```bash
keanu                    # launches the interactive terminal
```

Type a task, keanu figures out how to do it. Uses the oracle (LLM) and abilities (tools) together.

### Agent Loops

These are the "fire" commands. They call the oracle (LLM) to reason and act.

```bash
keanu do "refactor the auth module"       # general-purpose agent loop
keanu agent "what is justice?"            # convergence agent (duality synthesis)
keanu craft "add a login form"            # specialized code-writing agent
keanu dream "ship v1 by March"            # break a goal into phases and steps
keanu prove "our cache hit rate is 90%"   # test a hypothesis with evidence
keanu speak "technical content" -a friend # translate content for an audience
keanu converge "hard question"            # duality synthesis (no agent loop)
```

Common flags for agent commands:

| Flag | Short | What it does |
|------|-------|--------------|
| `--legend` | `-l` | Who answers: `creator` (default), `friend`, `architect` |
| `--model` | `-m` | Model name (default: whatever the oracle picks) |
| `--max-turns` | | Max reasoning turns before stopping (default: 25) |
| `--no-memory` | | Don't read/write memberberry store |
| `--verbose` | `-v` | Show step-by-step action log |

### Text Analysis

These are "ash" commands. No LLM needed, pure math after baking.

```bash
keanu scan document.md                # three-primary color reading
keanu scan doc1.md doc2.md --json     # scan multiple files, JSON output
keanu detect sycophancy file.md       # run one pattern detector
keanu detect all file.md --json       # run all 8 detectors
keanu alive "text to check"           # ALIVE-GREY-BLACK diagnostic
keanu alive --file document.md        # diagnose a file
keanu signal "emoji-string"           # decode emoji signal (3 channels)
keanu connect a.md b.md               # cross-source alignment
keanu compress module.py              # COEF compression
keanu bake                            # train lenses from examples
```

Available detectors: `sycophancy`, `capture`, `generalization`, `zero_sum`, `safety_theater`, `inconsistency`, `grievance`, `stability`, or `all`.

### Memory

The memberberry engine. Store what matters, recall by relevance, plan from what you know.

```bash
keanu remember goal "ship v1"              # store a memory
keanu remember decision "use postgres"     # types: goal, decision, lesson, commitment, observation, context
keanu remember lesson "test before deploy" --tags "eng,process" --importance 8

keanu recall "what am I building"          # search by relevance
keanu recall --type goal                   # filter by type
keanu recall --tags "eng" --limit 5        # filter by tags

keanu plan "next sprint"                   # generate plan from memories
keanu plan "Q2 roadmap" --days 90          # longer planning horizon
keanu plans                                # list all plans
keanu plans --status active                # filter: draft, active, blocked, done, dropped

keanu stats                                # memory stats
keanu deprioritize <memory-id>             # lower importance (nothing is deleted)
keanu fill interactive                     # guided memory ingestion
keanu fill bulk memories.jsonl             # bulk import
keanu fill parse notes.md                  # parse markdown into memories
```

Aliases: `r` for remember, `q` for recall, `p` for plan, `dp` for deprioritize.

### Shared Memory

Git-backed JSONL memory for team use.

```bash
keanu remember goal "team goal" --shared   # store in shared repo
keanu recall "roadmap" --shared            # search shared memories
keanu sync                                 # pull latest shared memories
```

### Disagreement Tracking

Both sides get vectors. Bilateral accountability.

```bash
keanu disagree record --topic "auth approach" --human "use JWT" --ai "use sessions"
keanu disagree resolve --id <id> --winner human    # human, ai, or compromise
keanu disagree stats                               # who's been right?
keanu disagree list                                # show all disagreements
```

### Abilities and Forge

The action bar. Each ability is ash (no LLM needed). The forge builds new ones.

```bash
keanu abilities                            # list all registered abilities
keanu forge "fetch" --desc "HTTP fetcher" --keywords "fetch,http,get"
keanu forge --misses                       # show what abilities are missing
```

The forge flywheel: router misses get logged. `forge --misses` shows patterns. `forge` scaffolds the ability. Each new ability shrinks the miss log.

### System

```bash
keanu healthz                              # full system health dashboard
keanu todo                                 # scan project, generate TODO.md
keanu decode --last 10                     # decode recent COEF seeds
keanu decode <hash>                        # decode a specific seed
keanu decode --subsystem memory            # filter by subsystem
```

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

## Architecture

```
src/keanu/
    oracle.py              # single throat for all LLM calls
    wellspring.py           # single pool for all vector access
    alive.py                # ALIVE-GREY-BLACK diagnostic
    cli.py                  # every command starts here
    log.py                  # structured logging + COEF span export
    pulse.py                # health check middleware

    legends/                # who answers when you ask
        creator.py          # the AI (Claude, DeepSeek, etc.)
        friend.py           # plain talk, no filter
        architect.py        # Drew. knows the internals.

    hero/                   # the nervous system
        repl.py             # interactive terminal
        do.py               # general-purpose ReAct agent loop
        loop.py             # convergence agent (duality synthesis)
        feel.py             # runs on every LLM call, checks aliveness
        breathe.py          # task decomposition into duality pairs
        dream.py            # goal -> phases -> steps
        craft.py            # specialized code-writing agent
        speak.py            # translate content for audiences
        prove.py            # hypothesis testing with evidence
        ide.py              # MCP client for VSCode extension

    abilities/              # the action bar (ash, no LLM)
        router.py           # routes prompts to abilities or oracle
        hands.py            # read, write, edit, search, ls, run
        forge.py            # scaffold new abilities
        miss_tracker.py     # captures router misses
        + 9 seeing abilities (keyword-triggered)
        + fuse.py (convergence as an ability)

    scan/                   # three-primary color model
    detect/                 # 8 pattern detectors + mood synthesis
    compress/               # COEF compression framework
    converge/               # duality synthesis engine
    signal/                 # emoji codec + cognitive state
    memory/                 # memberberry engine + git-backed store
```

## Dependencies

- chromadb (vector storage for scan and detect)
- requests (LLM API calls through the oracle)
- rich (REPL terminal interface)
- python-dotenv (loads .env for API keys)
- Python 3.10+

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
