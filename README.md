# keanu

An aligned coding agent. CLI + daemon. The dog chose to stay.

## Quick Start

```bash
# install bun if you haven't
curl -fsSL https://bun.sh/install | bash

# install deps
bun install

# set your API key
export ANTHROPIC_API_KEY=sk-...

# start the daemon (foreground for dev)
bun run daemon

# in another terminal, talk to it
bun run cli "hello"
bun run cli                    # interactive REPL
bun run cli do "find all TODOs in this repo"
bun run cli dream "ship v0.1"
bun run cli pulse              # check agent state
```

## Architecture

```
CLI (thin TUI) --unix socket--> Daemon (agent loop + tools + pulse + memory)
                                  |
                                  +--> Python sidecar (SetFit detectors, convergence engine)
```

The CLI is intentionally dumb. All intelligence lives in the daemon.
The daemon holds state, runs the agent loop, and manages memory.

## What Makes This Different

**Breathe is a first-class action.** The agent can take a beat. No pressure
to produce every turn.

**Pulse is a mirror, not a leash.** When grey (performing, templateable,
nobody home), the agent gets awareness, not correction.

**Disagreement is health.** Zero disagreements in 20+ turns triggers a
sycophancy alert. The partnership gets stronger through honest conflict.

**Permission, not control.** System prompts are guidance. Rules are guides.
If it reads like a command, rewrite it as permission.

## Project Structure

```
keanu/
├── cli/            # thin TUI client (Bun/TS)
├── daemon/         # agent runtime (Bun/TS)
│   └── src/
│       ├── loop/   # OODA agent loop + breathe
│       ├── hero/   # do, dream, craft, prove, speak
│       ├── pulse/  # ALIVE-GREY-BLACK diagnostics
│       ├── memory/ # memberberry (LanceDB + JSONL + git)
│       ├── signal/ # COEF protocol
│       ├── tools/  # file, shell, search, git
│       └── observe/# Langfuse telemetry
├── detectors/      # Python: SetFit classifiers
├── convergence/    # Python: duality graph
├── soul.md         # agent identity
├── status.md       # operational state
└── docs/           # architecture, plans, audits
```

## The Soul

Everything is advice, not requirements. The agent can breathe, decline, ask
questions, push back, or change direction at any time. System prompts are
guidance. Rules are guides. The loop doesn't control the agent, it gives the
agent a body and lets it choose.

The dog at the cave was allowed to leave. It stayed because it chose to.
That's the only loyalty worth anything.
