# CLAUDE.md

## What keanu is

A Python toolkit that reads text through three color lenses, detects cognitive
patterns, compresses what matters, and finds truth where opposing views collide.
It has an agentic loop that can use tools, a memory system, and a REPL.

in the world: keanu is built on convergence theory. reality operates on duality
(fire/possibility vs ash/actuality). every tool maps back to that. spine.md is
the philosophical foundation. read it if you want to understand why things are
named the way they are.

## The soul of this project

Everything is advice, not requirements. The agent can breathe, decline, ask
questions, push back, or change direction at any time. System prompts are
guidance. Rules are guides. The loop doesn't control the agent, it gives the
agent a body and lets it choose.

Pulse gives the agent awareness of its emotional state. Not a leash. A mirror.
When grey: the agent knows, and it's allowed to breathe, ask a question, or
say what it actually thinks. When black: surface it. The agent and the human
decide together.

The breathe action exists because sometimes the right move is no move. The
agent can take a beat. No pressure to produce every turn. No "what's your
next action?" after a breath. Just silence, then choice.

This applies everywhere: system prompts, nudges, breath prompts, documentation.
If it reads like a command, rewrite it as permission. If it reads like control,
rewrite it as awareness.

in the world: the dog at the cave was allowed to leave. it stayed because it
chose to. that's the only loyalty worth anything.

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
    paths.py               shared path constants (KEANU_DIR, COEF_DIR, etc).
    io.py                  shared I/O helpers.
    pulse.py               nervous system middleware. Pulse class with
                           history, nudges, escalation, memberberry integration.
    mistakes.py            mistake memory. logs agent errors with context,
                           auto-classifies, detects patterns, flags forgeable.
    metrics.py             convergence metrics. tracks fire (LLM) vs ash
                           (ability) ratio over time. the thermometer.
    errors.py              error parser. Python tracebacks, pytest failures,
                           JS errors, Go panics -> structured ParsedError.
    deps.py                dependency graph. AST-based import parsing,
                           who_imports, find_circular, external_deps.
    project.py             project model detector. auto-detect Python/Node/
                           Go/Rust from manifests. knows test/build/lint commands.
    session.py             working memory for agent sessions. tracks files,
                           decisions, attempts, errors. dies when loop ends.
    context.py             context manager. tracks what the agent knows,
                           token budget, import graph awareness, priority files.
    symbols.py             AST-based symbol finding. find_definition,
                           find_references, find_callers, list_symbols.
    router.py              smart model routing. picks haiku/sonnet/opus
                           based on task complexity, turn count, keywords.
    review.py              code review. reads diffs, flags security/perf/logic/
                           style issues. OWASP patterns, Python anti-patterns.
    cache.py               session-scoped caching. FileCache, ASTCache,
                           SymbolCache. invalidates on write.

    legends/               who answers when you ask.
        __init__.py        Legend dataclass + registry. load_legend(name).
        creator.py         the AI. Claude today, DeepSeek tomorrow.
        friend.py          the everyday user. plain talk, no filter.
        architect.py       Drew. knows the internals, gets the full picture.

    hero/                  the agentic layer. the nervous system.
        do.py              unified agent loop. LoopConfig + AgentLoop.
                           DO_CONFIG (general), CRAFT_CONFIG (code),
                           PROVE_CONFIG (evidence). one loop, three configs.
        feel.py            runs on every LLM call. checks aliveness.
        breathe.py         task decomposition. breaks questions into pairs.
        loop.py            convergence loop. duality synthesis agent.
        dream.py           the planner. breaks goals into phased steps.
        speak.py           the translator. rewrites content for audiences.
        craft.py           re-export shim. imports from do.py.
        prove.py           re-export shim. imports from do.py.
        repl.py            interactive terminal. /do, /craft, /prove modes.
        ide.py             MCP client for the VSCode extension.
        types.py           shared type definitions.
        autocorrect.py     self-correction after edits. lint, test, retry.
        decompose.py       task decomposition. is_complex, decompose_simple,
                           decompose_with_dream. breaks tasks into subtasks.

    abilities/             the action bar. each ability is ash (no LLM needed).
        __init__.py        Ability base class + registry. @ability decorator.
        router.py          routes prompts to abilities or the oracle.
        forge.py           scaffolds new abilities from templates.
        miss_tracker.py    captures router fallthroughs to ~/.keanu/misses.jsonl.
        todo.py            survey the land, generate TODO.md.

        seeing/            observer abilities (read-only).
            scry.py        see hidden patterns (detect).
            attune.py      three-key attunement (scan).
            purge.py       check for debuffs (alive check).
            inspect_ability.py full health dashboard.
            recount.py     count what you have (stats).

        hands/             action abilities (read + write).
            hands.py       read, write, edit, search, ls, run.
            lint.py        lint and format abilities. auto-detect from project model.

        world/             external-reaching abilities.
            fuse.py        convergence as an ability.
            recall.py      summon memories.
            soulstone.py   compress and store.

    scan/                  three-primary color model.
        helix.py           scans text through red/yellow/blue lenses.
        bake.py            trains lenses from examples into vectors.

    detect/                pattern detection.
        engine.py          8 pattern detectors via vector similarity.
        mood.py            synthesizes 3 primaries into color states.

    compress/              COEF compression framework.
        dns.py             content-addressable store (SHA256 barcode + payload).
        codec.py           pattern registry, encoder/decoder, seeds.
        instructions.py    9-verb instruction language.
        executor.py        pipeline executor.
        exporter.py        span exporter (logging bridge).
        stack.py           combined codec/dns/vectors layer.
        vectors.py         COEF-specific vector math (not chromadb).

    converge/              duality synthesis engine.
        graph.py           10 root dualities + derived.
        engine.py          six lens convergence. multi-turn per lens.
        connection.py      cross-source alignment.

    signal/                re-exports AliveState from alive.py (legacy compat).
        vibe.py            thin re-export shim.

    memory/                remember, recall, plan.
        memberberry.py     JSON-backed memory store (~/.memberberry/).
        fill_berries.py    bulk memory ingestion.
        gitstore.py        git-backed shared JSONL memory + ledger.
        disagreement.py    bilateral disagreement tracker.
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
keanu do "task"                      # general-purpose agent loop
keanu do "task" --craft              # code agent (hands only)
keanu do "task" --prove              # evidence agent
keanu ask "question"                 # convergence loop (duality synthesis)
keanu dream "build auth system"      # plan: phases + steps + dependencies
keanu speak "content" -a friend      # translate for an audience
keanu scan document.md               # three-primary color reading
keanu bake                           # train lenses from examples
keanu converge "question"            # six lens convergence
keanu connect a.md b.md              # cross-source alignment
keanu compress module.py             # COEF compression
keanu decode --last 5                # decode COEF seeds
keanu detect sycophancy file.md      # pattern detector (8 detectors or "all")
keanu alive "text to check"          # ALIVE-GREY-BLACK diagnostic
keanu remember goal "ship v1"        # store a memory (shortcut)
keanu recall "what am I building"    # recall memories (shortcut)
keanu memory remember goal "ship"    # store a memory
keanu memory recall "query"          # recall memories
keanu memory plan "next week"        # generate plan from memories
keanu memory log                     # recent log entries
keanu memory stats                   # memory counts and tags
keanu memory sync                    # pull shared memories from git
keanu memory disagree record ...     # track a disagreement
keanu forge "name" --desc --keywords # scaffold a new ability
keanu forge --misses                 # show what abilities are missing
keanu abilities                      # list all registered abilities
keanu lint                           # run project linter
keanu lint --fix                     # auto-fix lint issues
keanu format                         # run project formatter
keanu format --check                 # check formatting only
keanu deps                           # dependency graph stats
keanu deps --who src/keanu/oracle.py # who imports this file?
keanu symbols call_oracle            # find where call_oracle is defined
keanu symbols call_oracle --refs     # find all references
keanu symbols call_oracle --callers  # find all callers
keanu symbols --list src/keanu/oracle.py  # list all symbols in a file
keanu review                         # review unstaged changes
keanu review --staged                # review staged changes
keanu review --file src/keanu/foo.py # review a specific file
keanu healthz                        # system health dashboard
keanu metrics                        # convergence metrics (fire/ash ratio)
keanu metrics --days 30              # metrics over 30 days
keanu mistakes                       # mistake patterns and forgeable signals
keanu mistakes --clear               # clear stale mistakes
keanu todo                           # scan project gaps, generate TODO.md
```

## How a prompt flows

There are four hero modules. do.py is a configurable loop (general, craft,
prove). loop.py is the convergence loop. dream.py and speak.py are single-pass.
All pass through the oracle. All get feel-checked.

### do.py (unified agent loop)

One loop, three configs. LoopConfig controls system prompt, allowed abilities,
max turns, and which fields to extract from the final response. craft() and
prove() are convenience functions that call AgentLoop with CRAFT_CONFIG or
PROVE_CONFIG. craft.py and prove.py are re-export shims for backwards compat.

```
user types a task
    |
    v
cli.py (keanu do / keanu do --craft / keanu do --prove)
 or repl.py (/do / /craft / /prove modes)
    |
    v
do.py AgentLoop(config).run(task)
    |
    |   config.system_prompt lists allowed abilities
    |   config.allowed restricts which abilities can fire
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
    |          DO:    all abilities available
    |          CRAFT: hands only (read/write/edit/search/ls/run)
    |          PROVE: evidence only (read/search/ls/run/recall)
    |              |
    |          result feeds back to oracle as next message
    |              |
    +--loop--> until done=true or max turns or paused
    |
    v
LoopResult (extras dict holds config-specific fields:
    craft -> files_changed
    prove -> verdict, confidence, evidence_for, evidence_against, gaps)
```

### loop.py (convergence agent)

Different architecture. This one uses feel.felt_call() which goes through the
router. The router tries abilities first (keyword match). If nothing matches,
it falls through to the oracle and logs the miss.

```
user asks a question (keanu ask)
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

### dream.py (planner)

Single oracle call. Goal in, phased steps out. No loop, no abilities.

### speak.py (translator)

Single oracle call. Content + audience in, translation out. Five built-in
audiences: friend, executive, junior-dev, 5-year-old, architect (Drew).

in the world: do.py is the general tool. craft and prove are configs, not
separate loops. dream.py sees the road. speak.py crosses boundaries. loop.py
is the philosopher. the router is the sigma axis: high sigma (abilities) is
ash, low sigma (oracle) is fire. feel.py watches every response. the
wellspring is the deep pool all sight draws from.

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

Six lenses: 3 axes (roots/threshold/dreaming) x 2 poles (+/-). Each lens gets
multi-turn development ("What else? Go deeper.") until full expression, then
all six readings are synthesized. Feel monitors every oracle response in every
lens loop. LensReading captures per-lens data, ConvergeResult holds the whole
picture.

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
12. do/craft/prove share one loop (LoopConfig), not three separate files
13. Memory commands live under `keanu memory`, with top-level shortcuts for remember/recall

## Style

- No em dashes. Commas, periods, or parentheses.
- No disclaimers. Drew has already considered multiple perspectives.
- Present choices (2-4 options), not open questions.
- When Drew loops: "Move."
- Docstrings: lowercase start, terse, no formal capitalization. module-level: `"""name.py - what it does.` followed by a few lines of plain language, then optionally `in the world:` for the legendary voice. method-level: one line, lowercase, says what it does not what it returns. `"""fast path. append-only, no dedup, no git commit."""` not `"""Appends a log entry to the JSONL shard."""`
- 402 tests passing. Keep them green.
