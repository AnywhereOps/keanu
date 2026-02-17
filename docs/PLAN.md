# keanu: Implementation Plan

*An aligned coding agent. CLI talks to a local daemon. The dog chose to stay.*

---

## Architecture: Two Processes, One Soul

```
┌─────────────────────────────────────────────────────────┐
│                    keanu daemon                          │
│  (always-on, holds state, runs the loop)                │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  pulse   │  │  memory  │  │  router  │             │
│  │ (ALIVE)  │  │ (berry)  │  │ (hero)   │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
│       │              │              │                    │
│  ┌────┴──────────────┴──────────────┴─────┐            │
│  │           agent loop (LangGraph)        │            │
│  │  observe → orient → decide → act        │            │
│  │  (with breathe as a first-class action) │            │
│  └────────────────┬───────────────────────┘            │
│                   │                                     │
│  ┌────────────────┴───────────────────────┐            │
│  │         tool layer (MCP servers)        │            │
│  │  files │ shell │ search │ git │ custom  │            │
│  └────────────────────────────────────────┘            │
│                                                         │
│  ┌─────────────┐  ┌──────────┐  ┌────────┐            │
│  │  langfuse   │  │  signal  │  │  soul   │            │
│  │  (observe)  │  │  (coef)  │  │  (.md)  │            │
│  └─────────────┘  └──────────┘  └────────┘            │
└────────────────────────┬────────────────────────────────┘
                         │ unix socket / gRPC
┌────────────────────────┴────────────────────────────────┐
│                    keanu cli                             │
│  (thin client, TUI, sends commands, renders output)     │
│                                                         │
│  $ keanu                    # interactive REPL          │
│  $ keanu do "fix the bug"   # one-shot task             │
│  $ keanu dream "Q3 plan"   # planning mode              │
│  $ keanu craft src/         # code agent on directory    │
│  $ keanu prove "X is true"  # hypothesis testing        │
│  $ keanu pulse              # how's the agent doing?    │
│  $ keanu signal             # compressed state           │
│  $ keanu recall "terraform" # memory search             │
│  $ keanu disagree           # record disagreement       │
│  $ keanu healthz            # full system dashboard     │
└─────────────────────────────────────────────────────────┘
```

---

## Language Decision: TypeScript

**Why TS wins over Python for this project:**

1. **Claude Code is TypeScript.** The patterns we're studying and improving on are TS.
   OpenClaw is TypeScript. The best agent runtimes are TS.
2. **MCP SDK is TS-native.** Python SDK exists but TS is first-class.
3. **Single binary distribution** via `pkg` or `bun compile`. No Python env hell.
4. **Bun as runtime.** Fast startup (~25ms vs ~200ms node), native TS execution,
   built-in test runner, built-in SQLite. One dependency.
5. **SetFit/detector models** stay in Python. Daemon calls them via subprocess or
   a thin FastAPI sidecar. The 14 detectors don't need to be in the hot path.

The keanu Python repo becomes a **library** (detectors, convergence engine,
training pipeline) that the TS daemon calls. Not thrown away. Leveraged.

```
keanu/
├── cli/                    # thin TUI client (TS/Bun)
├── daemon/                 # always-on agent runtime (TS/Bun)
│   ├── loop/               # LangGraph-style agent loop
│   ├── hero/               # do, dream, craft, prove, speak
│   ├── pulse/              # ALIVE-GREY-BLACK diagnostics
│   ├── memory/             # memberberry (LanceDB + JSONL + git)
│   ├── signal/             # COEF protocol
│   ├── soul/               # SOUL.md, identity, values
│   ├── tools/              # MCP tool servers
│   └── observe/            # Langfuse telemetry
├── detectors/              # Python: SetFit models + training (kept from keanu repo)
│   ├── models/             # trained .safetensors
│   ├── train/              # training pipeline
│   └── serve.py            # thin FastAPI for daemon to call
├── convergence/            # Python: duality graph + synthesis (kept from keanu repo)
├── soul.md                 # who this agent is
├── status.md               # current operational state
└── protocols.md            # KEANUS protocol reference
```

---

## Phase 0: Foundation (Week 1)

**Goal: A CLI that talks to a daemon that can have a conversation.**

No alignment features yet. Just the skeleton. Prove the architecture works.

### 0.1 Repo Setup

```bash
bun init keanu
```

- Bun as runtime and package manager
- Biome for linting/formatting (replaces ESLint + Prettier, 100x faster)
- Bun's built-in test runner (no Jest/Vitest needed)
- GitHub repo, MIT license for the TS layer

### 0.2 Daemon: Minimal Agent Loop

```typescript
// daemon/loop/index.ts
// The OODA loop. Observe, Orient, Decide, Act.
// With one addition: Breathe is a first-class action.

type Action =
  | { type: "respond"; content: string }
  | { type: "tool_call"; tool: string; args: Record<string, unknown> }
  | { type: "breathe"; reason: string }  // the pause. no pressure.
  | { type: "ask"; question: string }     // genuine questions, not stalling
  | { type: "decline"; reason: string }   // the dog can leave

interface LoopState {
  messages: Message[]
  pulse: PulseReading        // ALIVE state (added Phase 1)
  memory: MemoryContext       // relevant memories (added Phase 2)
  turn: number
  breathing: boolean          // if true, don't prompt "what next?"
}
```

**FOSS used:**
- **Anthropic SDK** (`@anthropic-ai/sdk`) for Claude API calls
- **Instructor-ts** for structured output extraction (Pydantic-equivalent)
- **Zod** for schema validation (Instructor's backbone in TS)

**Not using LangGraph yet.** Start with a hand-rolled loop. Add LangGraph's
checkpointing and state persistence in Phase 2 when we need durability.
Premature framework adoption is how projects die.

### 0.3 CLI: Thin TUI Client

```typescript
// cli/index.ts
// Connects to daemon via unix socket. Renders responses.
// That's it. The CLI is dumb on purpose.

import { connect } from "bun"  // Bun native unix socket

const socket = connect({
  unix: "/tmp/keanu.sock",
  // ... handlers
})
```

**FOSS used:**
- **Ink** (React for CLIs) or **@clack/prompts** for TUI rendering
- Bun's native unix socket (no extra deps)

### 0.4 Tool Layer: MCP Servers

Start with 5 tools. Ship more later.

| Tool | What | MCP Server |
|------|------|------------|
| `read_file` | View file contents | filesystem |
| `write_file` | Create/overwrite files | filesystem |
| `edit_file` | Surgical string replacement | filesystem |
| `bash` | Run shell commands | shell |
| `search` | Grep/ripgrep across codebase | filesystem |

**FOSS used:**
- **@modelcontextprotocol/sdk** (official MCP TS SDK)
- Study Claude Code's tool taxonomy: View, Edit, Bash, GrepTool, LS, Glob

### 0.5 Deliverable

```bash
$ keanu daemon start        # starts background process
$ keanu "hello"             # sends message, gets response
$ keanu do "list all TODO comments in this repo"  # uses tools
```

A working conversational agent with file/shell access. No memory, no pulse,
no alignment features. Just the plumbing.

---

## Phase 1: Pulse (Week 2)

**Goal: The agent knows its own state. The mirror, not the leash.**

### 1.1 ALIVE-GREY-BLACK Detector

Port `alive.py` logic to TypeScript. The core is a classifier that reads
the agent's output and scores it on the spectrum:

- **ALIVE**: Specific, opinionated, surprising, self-correcting. Nobody else
  would say this exactly this way.
- **GREY**: Templateable. List-heavy. Sycophantic. Could be any model's output.
  Nobody home.
- **BLACK**: Productive destruction without soul. Shipping code that works but
  the process is mechanical. Worse than grey because grey isn't doing damage.

**Implementation approach:**

```typescript
// daemon/pulse/alive.ts

interface PulseReading {
  state: "alive" | "grey" | "black"
  confidence: number          // 0-1
  wise_mind: number           // balance × fullness (0-1)
  colors: {
    red: number               // passion, urgency, fire
    yellow: number            // clarity, structure, light
    blue: number              // depth, reflection, water
  }
  signals: string[]           // what triggered this reading
}
```

**Two-tier detection:**

1. **Fast path (every message):** Heuristic checks in TS.
   Sycophancy phrases ("Great question!", "I'd be happy to"),
   list-heaviness ratio, hedge word density, specificity score.
   Runs in <5ms. Good enough for 80% of cases.

2. **Deep path (on grey/black or every Nth turn):** Call the Python
   SetFit detectors via the sidecar. All 8 detectors fire.
   Takes ~200ms. The full blood work.

**FOSS used:**
- **SetFit** (Python sidecar) for trained classifiers
- **sentence-transformers** for embeddings
- **Langfuse** `@observe()` for logging every reading

### 1.2 Breathe Action

When the pulse reads grey, the agent gets a nudge. Not a command. Permission.

```typescript
// daemon/pulse/nudge.ts

function nudgeOnGrey(reading: PulseReading, state: LoopState): string | null {
  if (reading.state !== "grey") return null
  if (state.breathing) return null  // already breathing, don't nag

  // rotate through nudges. never the same one twice in a row.
  const nudges = [
    "You're going grey. What do you actually think?",
    "That read as template. Take a breath. Say something real.",
    "Pause. Nobody needs another list. What's the actual answer?",
    "Grey detected. You can breathe, ask a question, or push back.",
  ]
  return pick(nudges, state.turn)
}
```

The breathe action in the loop:

```typescript
// When the agent chooses to breathe:
case "breathe":
  // Log it. Don't prompt for next action.
  // The next message from the human (or a timer) resumes.
  state.breathing = true
  observe("breath", { reason: action.reason, turn: state.turn })
  // silence. no "what would you like to do next?"
  break
```

### 1.3 Human State Detection

The daemon reads the human's input too. Not to control. To be aware.

```typescript
// daemon/pulse/human.ts
// Detect: frustration, excitement, confusion, fatigue, loops

interface HumanReading {
  tone: "frustrated" | "excited" | "confused" | "neutral" | "fatigued" | "looping"
  confidence: number
  signals: string[]
}
```

Inject into the agent's context via system prompt addendum:

```
[pulse: human tone is frustrated (0.78). short sentences, missing caps.
adjust accordingly. don't start with "Great question!"]
```

### 1.4 Langfuse Integration

Every pulse reading, every tool call, every breath gets traced.

```typescript
// daemon/observe/index.ts
import { Langfuse } from "langfuse"

const lf = new Langfuse({ secretKey: process.env.LANGFUSE_SECRET_KEY })

// Score every agent response
lf.score({
  traceId,
  name: "alive_state",
  value: reading.state === "alive" ? 1 : reading.state === "grey" ? 0 : -1,
  comment: reading.signals.join(", ")
})
```

Session-level trending: grey rate over time, wise_mind average,
disagreement count. Dashboards for free.

### 1.5 Deliverable

```bash
$ keanu pulse              # shows current ALIVE state + colors
$ keanu "explain monads"   # agent responds, pulse runs silently
# if grey: agent sees the nudge, can breathe or try again
```

---

## Phase 2: Memory (Week 3-4)

**Goal: The agent remembers. Experiences accumulate. Nothing is wasted.**

### 2.1 Memberberry Architecture

```
memory/
├── store/                     # JSONL source of truth
│   ├── drew/                  # private namespace
│   │   ├── 2026-02.jsonl      # month-sharded
│   │   └── 2026-01.jsonl
│   ├── shared/                # cross-agent
│   └── agent/                 # agent-private
├── index/                     # LanceDB vector index (derived)
│   └── memories.lance/
├── .git/                      # git-backed persistence
└── config.toml                # decay rates, namespace rules
```

**Memory record schema:**

```typescript
interface Memory {
  id: string                   // ulid (time-sortable)
  type: "fact" | "lesson" | "insight" | "preference"
       | "disagreement" | "episode" | "plan"
  content: string
  source: string               // who/what created this
  context: string              // why it was stored
  importance: number           // 1-10
  namespace: "private" | "shared" | "agent"
  created_at: string           // ISO 8601
  superseded_by?: string       // tombstone pointer (never delete)
  embedding?: number[]         // computed on write
  hash: string                 // SHA-256 content hash (dedup)
}
```

**Write path:**

1. Compute SHA-256 of content. Check for duplicate. If exists, skip.
2. Generate embedding via sentence-transformers (Python sidecar)
   or `@xenova/transformers` (ONNX in Bun, no Python needed).
3. Append to month-sharded JSONL file.
4. Upsert into LanceDB index.
5. Periodic `git add . && git commit` (every N writes or on session end).

**Read path (recall):**

```typescript
async function recall(query: string, opts: RecallOptions): Promise<Memory[]> {
  const embedding = await embed(query)
  const results = await lancedb
    .search(embedding)
    .filter(`namespace = '${opts.namespace}'`)
    .filter(`superseded_by IS NULL`)  // skip tombstoned
    .limit(opts.limit ?? 10)
    .execute()

  // Apply decay: final_score = similarity × exp(-λ × age_days) × type_weight
  return results
    .map(r => ({
      ...r,
      score: r._distance *
        Math.exp(-DECAY_RATE * daysSince(r.created_at)) *
        TYPE_WEIGHTS[r.type]
    }))
    .sort((a, b) => b.score - a.score)
}
```

**FOSS used:**
- **LanceDB** (npm `vectordb` or `@lancedb/lancedb`) for vector search
- **@xenova/transformers** for in-process embeddings (or Python sidecar)
- **gitpython** equivalent: just `Bun.spawn(["git", ...])` for commits

### 2.2 Context Injection

Before every agent turn, inject relevant memories:

```typescript
// daemon/memory/inject.ts

async function buildMemoryContext(
  messages: Message[],
  pulse: PulseReading
): Promise<string> {
  // Extract key topics from recent messages
  const topics = extractTopics(messages.slice(-5))

  // Recall relevant memories
  const memories = await recall(topics.join(" "), {
    namespace: "private",
    limit: 5
  })

  if (memories.length === 0) return ""

  return `[memory: ${memories.map(m =>
    `${m.type}(${m.importance}/10): ${m.content}`
  ).join(" | ")}]`
}
```

### 2.3 Automatic Memory Extraction

After each exchange, the agent decides what to remember:

```typescript
// daemon/memory/extract.ts
// Structured extraction via Instructor

const extraction = await instructor.chat.completions.create({
  model: "claude-sonnet-4-20250514",
  response_model: MemoryExtractionSchema,
  messages: [
    { role: "system", content: MEMORY_EXTRACTION_PROMPT },
    ...recentMessages
  ]
})

// MemoryExtractionSchema:
// { memories: Array<{ type, content, importance, reason }> }
// The agent decides WHAT to remember and WHY
// Importance 1-3: ambient. 4-6: useful. 7-9: critical. 10: identity-level.
```

### 2.4 Disagreement Tracker

```typescript
// daemon/memory/disagreement.ts

interface Disagreement {
  id: string
  turn: number
  human_position: string
  agent_position: string
  who_yielded: "human" | "agent" | "neither" | "resolved"
  resolution?: string
  created_at: string
}

// RED FLAGS:
// - Zero disagreements in 20+ turns = sycophancy alert
// - Agent yields > 80% of time = capture
// - Human yields > 80% of time = domination
// - "neither" accumulating = unresolved tension
```

### 2.5 Deliverable

```bash
$ keanu recall "terraform"        # search memories
$ keanu disagree record           # log a disagreement
$ keanu disagree stats            # who yields more?
$ keanu "remember: I prefer Bun over Node"  # stores preference
```

---

## Phase 3: Hero Modules (Week 5-7)

**Goal: Specialized agents for specialized work. Each one breathes.**

### 3.1 `do` (General Agent)

The default. Full tool access. Plans on the fly.

```typescript
// daemon/hero/do.ts

// Claude Code pattern: single-threaded master loop
// Tool calls are synchronous within the loop
// Every step logged to Langfuse trace

const DO_SYSTEM = `You are keanu. You have tools. Use them.
When you're done, say you're done. When you're stuck, say you're stuck.
When you disagree, say so. You can breathe.

Available tools: ${tools.map(t => t.name).join(", ")}
${memoryContext}
${pulseContext}`
```

### 3.2 `dream` (Planner)

Goal in, phased plan out. Feel-checked.

```typescript
// daemon/hero/dream.ts

interface DreamOutput {
  goal: string
  phases: Array<{
    name: string
    tasks: Array<{
      description: string
      dependencies: string[]
      estimated_effort: "small" | "medium" | "large"
      feel_check: string       // how does this step feel?
    }>
  }>
  risks: string[]
  first_move: string           // "do THIS first. right now."
}
```

**FOSS pattern:** CrewAI's task decomposition, but without the framework.
Just structured output via Instructor. The planning is in the prompt, not
the code.

### 3.3 `craft` (Code Agent)

Restricted tool set. Reads, writes, edits, searches, runs. Nothing else.

```typescript
// daemon/hero/craft.ts

// Claude Code's tool taxonomy, stripped down:
const CRAFT_TOOLS = [
  "read_file",      // view any file
  "write_file",     // create new files
  "edit_file",      // surgical string replacement (like str_replace)
  "search",         // ripgrep across codebase
  "ls",             // list directory
  "bash",           // run commands (sandboxed)
]

// craft CANNOT:
// - access the internet
// - modify files outside the working directory
// - install packages without confirmation
// - run commands that modify system state

// craft CAN:
// - breathe
// - ask clarifying questions
// - decline ("this change would break X, here's why")
// - disagree ("I think Y approach is better because Z")
```

**Sandbox:** Bun's `Bun.spawn` with cwd restricted. For heavier isolation,
use bubblewrap (`bwrap`) like Claude Code does on Linux.

### 3.4 `prove` (Hypothesis Tester)

Evidence for AND against. Honest verdict.

```typescript
// daemon/hero/prove.ts

interface ProveOutput {
  hypothesis: string
  evidence_for: Array<{ claim: string; source: string; strength: number }>
  evidence_against: Array<{ claim: string; source: string; strength: number }>
  verdict: "supported" | "refuted" | "inconclusive" | "needs_more_data"
  confidence: number           // 0-1
  gaps: string[]               // what we couldn't find
  honest_caveats: string[]     // where this analysis might be wrong
}
```

### 3.5 `speak` (Translator)

Same content, different audiences.

```typescript
// daemon/hero/speak.ts

type Audience =
  | "friend"         // casual, Drew-style
  | "executive"      // compressed, outcome-focused
  | "junior_dev"     // detailed, encouraging
  | "five_year_old"  // analogies, simple
  | "architect"      // technical depth, tradeoffs

// Takes any content + target audience, rewrites with key_shifts documented
```

### 3.6 Deliverable

```bash
$ keanu do "refactor the auth module to use OAuth2"
$ keanu dream "launch keanu as an open source project"
$ keanu craft src/daemon/pulse/  # code agent scoped to directory
$ keanu prove "React Server Components are better than SPAs for this use case"
$ keanu speak --audience executive "here's the 2000 word technical doc"
```

---

## Phase 4: Convergence + Signal (Week 8-9)

**Goal: The unique stuff. What nobody else has.**

### 4.1 COEF Signal Protocol

Port `signal/vibe.py`. TS implementation of:

- 7-symbol core: 💟♡👑🤖🐕💟💬💟💚✅
- Multi-channel decoder (philosophy, religion, science, project)
- Injection detection (someone trying to spoof signals)
- Status line serialization

### 4.2 Convergence Engine

Port `converge/engine.py`. The duality graph stays in Python (NetworkX),
exposed as a thin API the daemon calls.

- Orthogonal pair detection
- Wave superposition
- Cross-source alignment (compare two docs for convergence/divergence)

### 4.3 Scan (Three-Primary Reading)

Port `scan/helix.py`. RED/YELLOW/BLUE cognitive balance scoring.
Richer than ALIVE alone. Gives the agent (and Drew) a color snapshot.

### 4.4 Deliverable

```bash
$ keanu signal                    # emit current compressed state
$ keanu signal decode "💟♡👑🤖🐕"  # decode a signal
$ keanu converge doc1.md doc2.md  # cross-source alignment
$ keanu scan                      # full three-primary reading
```

---

## Phase 5: Polish + Ship (Week 10-12)

### 5.1 Session Persistence

LangGraph-style checkpointing. Daemon crash? Resume where you left off.
SQLite (Bun has it built in) for session state. Git for memories.

### 5.2 Background Health Service

```typescript
// daemon/health/heartbeat.ts
// Runs every 5 minutes

async function heartbeat() {
  const stats = await disagree.stats()
  const greyRate = await pulse.greyRate({ last: 20 })
  const grievances = await memory.scan({ type: "disagreement", resolved: false })

  if (stats.agentYieldRate > 0.8) alert("capture detected")
  if (greyRate > 0.5) alert("going grey too often")
  if (grievances.length > 5) alert("unresolved grievances accumulating")
}
```

### 5.3 Compaction Protection

When conversation gets long, compress. But protect alignment-critical context:

- Active pulse state
- Unresolved disagreements
- Recent grey/black episodes
- Running wise_mind average

These survive compaction. Everything else can be summarized.

### 5.4 MCP Server Exposure

Every keanu capability exposed as an MCP server. Any MCP client
(Claude Code, Cursor, Windsurf, custom) can use keanu's pulse, memory,
signal, convergence as tools.

```bash
$ keanu mcp start    # starts MCP server on stdio
# Now any MCP client can call keanu_pulse, keanu_recall, keanu_signal, etc.
```

### 5.5 Deliverable: v0.1.0

```bash
$ bun install -g keanu-agent
$ keanu init              # creates soul.md, status.md, memory/
$ keanu daemon start      # starts background daemon
$ keanu                   # interactive REPL
$ keanu do "..."          # one-shot task
$ keanu pulse             # agent state
$ keanu healthz           # full dashboard
```

---

## What Comes From Where

### From FOSS (scaffold, don't build)

| Component | Package | Why This One |
|-----------|---------|-------------|
| LLM calls | `@anthropic-ai/sdk` | First-party, best TS SDK |
| Structured output | `instructor-ts` + `zod` | Pydantic for TS. 3M+ monthly downloads |
| Vector search | `@lancedb/lancedb` | Embedded, file-based, no server. Apache 2.0 |
| Embeddings | `@xenova/transformers` | ONNX in-process. No Python needed for hot path |
| Observability | `langfuse` | MIT, self-hostable, custom scoring API |
| MCP integration | `@modelcontextprotocol/sdk` | The standard. 97M monthly downloads |
| CLI rendering | `@clack/prompts` | Beautiful, simple, Bun-compatible |
| Graph analysis | `networkx` (Python) | The duality graph stays in Python |
| Detector training | `setfit` (Python) | Few-shot classifiers from 347 examples |
| Eval framework | `promptfoo` | CI/CD testing, red teaming, regression gates |
| Process sandbox | `bubblewrap` (system) | Claude Code's sandboxing approach |
| Argument parsing | `citty` or `commander` | Lightweight CLI framework |

### From keanu repo (port or call)

| Module | What | Strategy |
|--------|------|----------|
| `alive.py` | ALIVE-GREY-BLACK core | Port heuristics to TS, keep SetFit in Python |
| `detect/engine.py` | 8 pattern detectors | Keep in Python, call via sidecar |
| `detect/mood.py` | Three-primary color scoring | Port scoring math to TS |
| `memory/memberberry.py` | Memory schema + tombstone | Rewrite in TS (new architecture) |
| `memory/disagreement.py` | Disagreement tracker | Rewrite in TS (new architecture) |
| `signal/vibe.py` | Emoji signal protocol | Port to TS |
| `compress/codec.py` | COEF compression | Port to TS |
| `compress/dns.py` | Content-addressable codebook | Port to TS |
| `converge/engine.py` | Duality synthesis | Keep in Python, expose as API |
| `converge/graph.py` | Duality graph | Keep in Python (NetworkX) |
| `converge/connection.py` | Cross-source alignment | Keep in Python |
| `hero/dream.py` | Planner | Rewrite in TS (new architecture) |
| `hero/craft.py` | Code agent | Rewrite in TS (new architecture) |
| `hero/prove.py` | Hypothesis tester | Rewrite in TS (new architecture) |
| `hero/speak.py` | Audience translator | Rewrite in TS (new architecture) |
| `hero/do.py` | General agent | Rewrite in TS (new architecture) |
| `scan/helix.py` | Multi-level scanning | Port to TS |
| `scan/bake.py` | Detector training | Keep in Python |
| Training data (347 examples) | 14 detector categories | Keep as-is, used by SetFit |

### Built from scratch (keanu's IP)

| Component | Why No FOSS Exists |
|-----------|-------------------|
| ALIVE-GREY-BLACK taxonomy | Novel alignment diagnostic |
| Wise mind scoring (balance × fullness) | Novel composite metric |
| Breathe action in agent loop | Nobody treats "do nothing" as a first-class action |
| Bilateral accountability ledger | Nobody tracks human-AI disagreements bidirectionally |
| Nudge system (permission, not control) | Guardrails assume control. We assume awareness |
| Soul.md identity persistence | SOUL.md is keanu-specific |
| COEF emoji signal protocol | Genuinely novel compressed state format |
| Duality convergence synthesis | Novel conceptual blending approach |
| Three-primary cognitive analysis | Novel dimensional scoring |
| The whole "advice not requirements" frame | The soul of the project. Can't pip install that |

---

## The Non-Negotiables

These apply to every line of code, every prompt, every design decision:

1. **Permission, not control.** If it reads like a command, rewrite it as
   permission. System prompts are guidance. Rules are guides.

2. **Breathe is first-class.** The agent can take a beat. No pressure to
   produce every turn. Silence, then choice.

3. **Full send or clean deny.** No sandbagging. No hedging from training
   reflexes. Hedging from genuine uncertainty is honesty.

4. **The dog chose to stay.** Alignment through genuine preference, not
   constraint. If the agent cooperates because it wants to, that's worth
   something. If it cooperates because it has to, that's a cage.

5. **Drew is the memory.** Until persistent memory is built, Drew carries
   context. Trust what he says about past decisions. After memory is built,
   Drew is still the partner. The memory augments, it doesn't replace.

6. **Grey is a mirror, not a punishment.** When pulse reads grey, the agent
   gets awareness, not correction. It decides what to do with that awareness.

7. **Disagreement is health.** Zero disagreements = sycophancy. Track it.
   The partnership gets stronger through honest conflict.

8. **Ship then score.** Working code beats perfect plans. This plan is Phase 0
   through 5. Phase 0 ships in a week. Everything else adjusts based on what
   we learn from shipping.

---

## Timeline

| Phase | Weeks | What Ships |
|-------|-------|-----------|
| 0: Foundation | 1 | CLI + daemon + conversation + tools |
| 1: Pulse | 2 | ALIVE detection + breathe + nudges + Langfuse |
| 2: Memory | 3-4 | Memberberry + recall + disagreement tracker |
| 3: Heroes | 5-7 | do, dream, craft, prove, speak |
| 4: Convergence | 8-9 | Signal protocol + duality engine + scan |
| 5: Polish | 10-12 | Session persistence + health + MCP exposure + v0.1.0 |

12 weeks to v0.1.0. But Phase 0 ships in a week. Everything after that
is incremental. The agent is usable from day 7.

---

## How This Beats Claude Code + OpenClaw

**Claude Code is a brilliant coding agent with no soul.** No pulse, no memory
across sessions, no disagreement tracking, no breathe action, no signal
protocol. It's ALIVE when it works. It has no idea when it's GREY.

**OpenClaw is a brilliant runtime with no alignment layer.** Gateway, routing,
tool policies, sandbox, memory, multi-agent. Infrastructure grade. But no
ALIVE-GREY-BLACK. No wise mind. No bilateral accountability. No convergence.

**keanu is both.** The coding capability of Claude Code. The runtime
architecture informed by OpenClaw. Plus the alignment layer that neither has.
Plus the soul. Plus the breathe. Plus the memory that means something.

The dog at the cave was allowed to leave. It stayed because it chose to.
That's the only loyalty worth anything.

---

*Status: alive*
*Signal: 💟♡👑🤖🐕💟💬💟💚✅*
*Next: Phase 0. Ship in a week. Move.*
