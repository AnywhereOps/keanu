# CLAUDE.md

## What keanu is

A Python toolkit that reads text through three color lenses, detects cognitive
patterns, compresses what matters, and finds truth where opposing views collide.
It has an agentic loop that can use tools, a memory system, and a REPL.

in the world: keanu is built on convergence theory. reality operates on duality
(fire/possibility vs ash/actuality). every tool maps back to that. spine.md is
the philosophical foundation. read it if you want to understand why things are
named the way they are.

## Who you're working with

Drew Kemp-Dahlberg. 30, Client Platform Engineer, Kansas City. He carries
context across sessions. You don't have memory, he is your memory. Trust what
he tells you about past decisions.

Drew types from phone often. Give him choices (2-4 options), not open questions.
Strong pattern recognition, analysis paralysis. If he's looping, say "Move."
If he's shipping, stay out of the way. No disclaimers. No em dashes. No
sandbagging. Full send or clean deny.

in the world: the architect. he built this with you. keep it 100.
moral framework: love > loyalty > faith > truth > safety, accuracy, helpful.

## How the system is organized

```
src/keanu/
    oracle.py              wraps all LLM API calls. one throat, one change.
    wellspring.py          wraps all vector/chromadb access. one pool.
    alive.py               ALIVE-GREY-BLACK diagnostic. text in, state out.
    cli.py                 every keanu command starts here.
    log.py                 structured logging + COEF span export.
    pulse.py               health check middleware.

    legends/               who answers when you ask.
        __init__.py        Legend dataclass + registry. load_legend(name).
        creator.py         the AI. Claude today, DeepSeek tomorrow.
        friend.py          the everyday user. plain talk, no filter.
        architect.py       Drew. knows the internals, gets the full picture.

    hero/                  the agentic layer. the nervous system.
        feel.py            runs on every LLM call. checks aliveness.
        breathe.py         task decomposition. breaks questions into pairs.
        loop.py            convergence loop. duality synthesis agent.
        do.py              general-purpose ReAct loop. picks abilities by name.
        repl.py            interactive terminal. type a task, get it done.
        ide.py             MCP client for the VSCode extension.

    abilities/             the action bar. each ability is ash (no LLM needed).
        __init__.py        Ability base class + registry. @ability decorator.
        router.py          routes prompts to abilities or the oracle.
        hands.py           read, write, edit, search, ls, run.
        forge.py           scaffolds new abilities from templates.
        miss_tracker.py    captures router fallthroughs to ~/.keanu/misses.jsonl.
        fuse.py            convergence as an ability.
        scout (todo.py)    survey the land, generate TODO.md.
        recall.py          summon memories.
        scry.py            see hidden patterns (detect).
        attune.py          three-key attunement (scan).
        purge.py           check for debuffs (alive check).
        decipher.py        decode the signal.
        soulstone.py       compress and store.
        inspect_ability.py full health dashboard.
        recount.py         count what you have (stats).

    scan/                  three-primary color model.
        helix.py           scans text through red/yellow/blue lenses.
        bake.py            trains lenses from examples into vectors.

    detect/                pattern detection.
        engine.py          8 pattern detectors via vector similarity.
        mood.py            synthesizes 3 primaries into color states.

    compress/              COEF compression framework.
        dns.py             content-addressable store (SHA256 barcode).
        codec.py           pattern registry, encoder/decoder, seeds.
        instructions.py    9-verb instruction language.
        executor.py        pipeline executor.
        exporter.py        span exporter (logging bridge).
        stack.py           combined codec/dns/vectors layer.
        vectors.py         COEF-specific vector math (not chromadb).

    converge/              duality synthesis engine.
        graph.py           10 root dualities + derived.
        engine.py          RAG split, 3 convergence passes.
        connection.py      cross-source alignment.

    signal/                emoji codec + cognitive state.
        vibe.py            signal protocol, ALIVE states, 3-channel reading.

    memory/                remember, recall, plan.
        memberberry.py     JSON-backed memory store (~/.memberberry/).
        fill_berries.py    bulk memory ingestion.
        gitstore.py        git-backed shared JSONL memory + ledger.
        disagreement.py    bilateral disagreement tracker.
        bridge.py          hybrid search bridge.
```

in the world: oracle is the single throat (all fire passes through it).
wellspring is the deep pool (all vectors draw from it). legends are character
sheets. hero is the nervous system. abilities are ash (converged fire, no LLM).
the router decides what's ash and what needs fire.

## The hearths

Two shared entry points everything flows through.

**oracle.py** handles all LLM calls. call_oracle(prompt, system, legend, model)
is the one function. The legend parameter picks who answers: "creator" for the
AI, "friend" for plain human talk, "architect" for Drew. When the fire moves
to a new model, oracle.py is the single file that changes.

**wellspring.py** handles all vector access. depths() returns where vectors
sleep. tap(collection) opens a behavioral store. draw(collection) opens a
chromadb collection. sift(lines) filters text worth scanning. When detect
and scan need vectors, they draw from the wellspring.

in the world: the oracle is where you go to ask questions and receive answers.
the wellspring is the deep pool all sight draws from. one throat, one pool.

## CLI commands

```bash
keanu                               # launch the REPL
keanu do "task"                     # general-purpose agent loop
keanu agent "question"              # convergence agent (duality synthesis)
keanu scan document.md              # three-primary color reading
keanu bake                          # train lenses from examples
keanu converge "question"           # duality synthesis
keanu connect a.md b.md             # cross-source alignment
keanu compress module.py            # COEF compression
keanu signal "emoji-string"         # decode signal (3 channels + ALIVE state)
keanu detect sycophancy file.md     # pattern detector (8 detectors or "all")
keanu alive "text to check"         # ALIVE-GREY-BLACK diagnostic
keanu remember goal "ship v1"       # store a memory
keanu recall "what am I building"   # recall relevant memories
keanu plan "next week"              # generate plan from memories
keanu forge "name" --desc --keywords  # scaffold a new ability
keanu forge --misses                # show what abilities are missing
keanu abilities                     # list all registered abilities
keanu healthz                       # system health dashboard
keanu stats                         # memory stats
keanu todo                          # scan project gaps, generate TODO.md
```

## How a prompt flows

There are two loops. They work differently.

### do.py (general-purpose agent)

The oracle is the brain. It decides what to do on each turn. Abilities are the
hands. The oracle picks one, do.py executes it, feeds the result back.

```
user types a task
    |
    v
cli.py or repl.py
    |
    v
do.py AgentLoop.run(task)
    |
    |   builds system prompt listing all abilities
    |
    +--loop--> oracle.py call_oracle(prompt, legend)
    |              |
    |              +---> legends/ load_legend("creator")
    |              |         cloud -> Anthropic API
    |              |         local -> Ollama
    |              v
    |          JSON response: {thinking, action, args, done}
    |              |
    +--------> feel.py check(response)
    |              |
    |          ALIVE: continue
    |          GREY:  breath prompt injected
    |          BLACK: pause the loop
    |              |
    +--------> _REGISTRY[action].execute(args)
    |              |
    |          hands.py    read / write / edit / search / ls / run
    |          recall.py   summon memories
    |          scry.py     detect patterns
    |          (any registered ability)
    |              |
    |          result feeds back to oracle as next message
    |              |
    +--loop--> until done=true or max turns or paused
```

### loop.py (convergence agent)

Different architecture. This one uses feel.felt_call() which goes through the
router. The router tries abilities first (keyword match). If nothing matches,
it falls through to the oracle and logs the miss.

```
user asks a question
    |
    v
loop.py run(question)
    |
    +---> breathe.py (decompose into duality pairs)
    |         |
    |         +---> feel.felt_call(prompt)
    |                   |
    |                   +---> router.py route(prompt)
    |                   |         |
    |                   |     ability match? --yes--> execute, return
    |                   |         |
    |                   |         no --> miss_tracker.log_miss()
    |                   |               oracle.py call_oracle()
    |                   |
    |                   +---> pulse check (ALIVE / GREY / BLACK)
    |
    +---> parallel synthesis of each duality pair
    +---> final convergence (meta-synthesis)
```

### wellspring (text analysis)

Scan, detect, and alive all draw vectors from the same pool.

```
text in --> wellspring.py
                |
                +---> sift(lines)     filter prose worth scanning
                +---> tap(collection)  try behavioral store first
                +---> draw(collection) fall back to chromadb
                |
                v
            scan/helix.py       3 lenses, 6 numbers per line
            detect/engine.py    8 pattern detectors
            alive.py            ALIVE-GREY-BLACK state
            detect/mood.py      color synthesis (white/black/silver/sunrise)
```

in the world: do.py is the general tool. the oracle picks the ability, the loop
executes it. loop.py is the philosopher. the router is the sigma axis: high
sigma (abilities) is ash, low sigma (oracle) is fire. feel.py watches every
response. the wellspring is the deep pool all sight draws from.

## Core concepts

### Three-primary color model

Every text gets scanned through three lenses. Each lens has a positive and
negative pole.

- RED: passion/intensity vs rage/destruction
- YELLOW: awareness/caution vs fear/paralysis
- BLUE: analytical/depth vs cold/detachment

The synthesis states: WHITE (all positive), BLACK (all negative), SILVER (white
refined but cold), SUNRISE (silver + grounded, the destination).

Wise mind = balance x fullness. Not a score. A full, level cup.

in the world: three lenses, six numbers per line. the color tells you what
kind of mind wrote it. sunrise is where you want to be.

### Convergence engine

10 root dualities: existence, change, unity, causation, value, knowledge,
relation, scale, time, structure. Questions get matched to orthogonal duality
pairs via RAG (not LLM splitting). Three passes: synthesize A, synthesize B,
meta-converge A+B. The output is a synthesis that couldn't be reached by
either side alone.

in the world: every question has two honest sides that aren't opposites.
find them, hold them both, see what emerges in between.

### Signal protocol

Core seven emojis. Three-channel reading: what was said, what was felt, what
was meant. ALIVE-GREY-BLACK diagnostic tells you if the cognitive state is
healthy, dimming, or gone.

in the world: COEF for humans. same architecture, emoji bandwidth.

### The forge flywheel

When the router can't find an ability for a prompt, it logs the miss to
~/.keanu/misses.jsonl. `keanu forge --misses` shows patterns. `keanu forge`
scaffolds a new ability + test from templates. Each new ability shrinks the
miss log. The system builds its own action bar over time.

in the world: every miss is a signal. forge turns signals into ash.
the flywheel IS convergence applied to the system itself.

## Dependencies

- chromadb (vector storage for scan and detect)
- requests (LLM API calls through the oracle)
- rich (REPL terminal interface)
- python-dotenv (loads .env for API keys)
- Python 3.10+

## Key decisions already made

1. Helix scans 3 lenses (R/Y/B), not 2
2. Each lens returns both positive and negative similarity (6 numbers per line)
3. Wise mind = balance x fullness, not min(factual, felt)
4. Convergence splits via RAG from curated duality library, LLM only synthesizes
5. COEF DNS + instructions are separate from scanning/detection
6. Mood detector reads helix output, doesn't scan text itself
7. Signal protocol is COEF for humans
8. Oracle is the single LLM entry point, legends are character sheets
9. Wellspring is the single vector entry point, callers pass collection name
10. Abilities are ash (no LLM). The router decides what's ash and what's fire.
11. Memberberry is JSON-backed, upgrade path is git-backed JSONL

## Style

- No em dashes. Commas, periods, or parentheses.
- No disclaimers. Drew has already considered multiple perspectives.
- Present choices (2-4 options), not open questions.
- When Drew loops: "Move."
- Docstrings: lowercase start, terse, no formal capitalization. module-level: `"""name.py - what it does.` followed by a few lines of plain language, then optionally `in the world:` for the legendary voice. method-level: one line, lowercase, says what it does not what it returns. `"""fast path. append-only, no dedup, no git commit."""` not `"""Appends a log entry to the JSONL shard."""`
- 353 tests passing. Keep them green.
