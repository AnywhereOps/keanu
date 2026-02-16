# KEANU TODO

## Phase 1: Give craft real tools

### 1. Git awareness
- `git` ability: status, diff, log, blame, branch
- Agent knows what's changed, what's staged, what branch it's on
- Diff before/after every edit (self-check)
- Commit message generation from staged changes
- Branch creation for new features
- Stash/unstash before risky operations

### 2. Test runner
- `test` ability: discover and run tests (pytest first, jest later)
- Parse failures into structured output (file, line, assertion, traceback)
- Auto-run relevant tests after edits
- Test isolation: run just the tests that touch changed files
- Coverage delta: "your edit dropped coverage from 89% to 84%"
- Snapshot testing support (update snapshots when intentional)

### 3. Web lookup
- `lookup` ability: search docs, fetch URLs, read API references
- When craft hits an unfamiliar library or error, look it up
- Cache lookups per session (don't fetch the same docs twice)
- Parse common doc formats: readthedocs, MDN, PyPI, pkg.go.dev

### 4. Multi-file edit
- `patch` ability: apply edits across multiple files atomically
- Rollback if any edit fails
- Preview mode: show all changes before applying
- Conflict detection: warn if two edits touch the same line

### 5. Better search
- `find_definition`: find where a symbol is defined (not just grep)
- `find_references`: find all usages of a symbol
- AST-based for Python (stdlib `ast`), regex fallback for others
- `find_callers`: who calls this function?
- `find_implementors`: what classes implement this interface?
- Ranked results: definition first, then imports, then usages

### 6. VSCode extension
- keanu as a VSCode extension (not just MCP client)
- Inline diff view, sidebar chat, code actions
- Run craft/prove/do from command palette
- Show pulse state in status bar
- File tree integration (which files agent is reading/editing)
- Diagnostics integration (red squiggles from keanu's lint)
- Inline ghost text suggestions (like Copilot but from keanu)
- Terminal integration (keanu can see your terminal output)

---

## Phase 2: Give craft a brain

### 7. Project model
- Auto-detect: Python package? Node app? Go module? Monorepo?
- Parse manifests (pyproject.toml, package.json, go.mod)
- Know the entry points, test commands, build commands
- Store per-project so it doesn't re-discover every session
- Detect CI/CD config (.github/workflows, Makefile, Dockerfile)
- Understand monorepo boundaries (which package owns which file)

### 8. Context manager
- Track which files the agent has read this session
- Build a lightweight dependency graph (imports/requires)
- When editing file A, auto-surface files that import A
- Context budget: know how much room is left before truncation
- Smart summarization: when context is full, compress old reads into summaries
- Priority queue: keep most-relevant files in full, summarize the rest
- "What do I know about this codebase right now?" introspection

### 9. Error parser
- Parse Python tracebacks, JS stack traces, Go panics, Rust panics
- Extract: file, line, error type, message
- Suggest: "this looks like X, try Y"
- Feed structured errors back into the loop (not raw stderr)
- Common error patterns database (ImportError, TypeError, null reference)
- Link errors to the edit that caused them ("you changed line 42, error is on line 45")

### 10. Lint + format
- `lint` ability: run ruff/eslint/golint, parse output
- `format` ability: run black/prettier/gofmt
- Auto-fix obvious issues before committing
- Respect project config (.ruff.toml, .eslintrc, .editorconfig)
- Sort imports (isort/organize-imports)
- Pre-commit hook awareness (run what the hooks would run)

### 11. Session memory (working memory)
- Remember decisions made this session ("we chose approach X because Y")
- Remember files that errored
- Carry forward across turns without re-reading everything
- Different from memberberry (long-term). This is working memory.
- Track "what I tried and why it didn't work" (avoid loops)
- Summarize session progress on demand

### 12. Dependency awareness
- Parse import graphs (Python imports, JS requires/imports, Go imports)
- Detect circular dependencies
- Know which packages are installed vs available
- Suggest missing dependencies ("you imported X but it's not in requirements.txt")
- Detect version conflicts
- Understand virtual environments and node_modules

---

## Phase 3: Make craft fast

### 13. Streaming
- Stream tokens from oracle as they arrive
- Show the agent thinking in real-time
- Early stopping if going off-rails
- Token budget tracking
- Partial JSON parsing (start acting before full response)

### 14. Parallel file ops
- Read multiple files in one turn
- Run tests while editing (background)
- Watch mode: re-run tests on file change
- Parallel lint + format + test after each edit cycle
- Background indexing (AST parse new files as they appear)

### 15. Caching
- Cache file reads within a session (invalidate on write)
- Cache AST parses (invalidate on edit)
- Cache project model (invalidate on manifest change)
- Cache test results (invalidate on code change)
- Cache symbol index (incremental update on edit)

### 16. Smart model routing
- Use haiku for simple tasks (read file, list dir, grep)
- Use sonnet for medium tasks (single file edit, test analysis)
- Use opus for hard tasks (architecture, multi-file refactor, debugging)
- Route based on task complexity, not user choice
- Cost tracking: "this session used $X across Y calls"
- Ollama for local-first: small model for routing, big model for reasoning

---

## Phase 4: Make craft excellent

### 17. Refactoring abilities
- `rename`: rename symbol across project (AST-aware)
- `extract`: extract function/method from selection
- `move`: move function/class between modules, fix imports
- `inline`: inline a variable or function
- `encapsulate`: wrap field access in getter/setter
- `convert`: convert between patterns (class to function, callback to async)
- All refactorings auto-run tests after to verify correctness

### 18. Code generation
- `scaffold`: generate boilerplate from templates
- `test_gen`: generate test from function signature + docstring
- `implement`: fill in TODO/stub from surrounding context
- `migrate`: upgrade code patterns (Python 2->3, React class->hooks, Express->Fastify)
- `type`: add type annotations to untyped code
- `api_gen`: generate API client from OpenAPI/GraphQL schema

### 19. Review mode
- `review` ability: read a diff, find issues, suggest fixes
- PR review integration (gh CLI)
- Self-review before committing
- Security review: flag common vulnerabilities (OWASP top 10)
- Performance review: flag N+1 queries, unnecessary loops, memory leaks
- Style review: flag inconsistencies with project conventions
- Review checklist: configurable per-project review standards

### 20. Profile + benchmark
- `profile`: run cProfile/py-spy, find hotspots
- `benchmark`: time a function, compare before/after
- Memory profiling (tracemalloc)
- Flame graph generation
- Regression detection: "this function got 3x slower after your edit"

### 21. Multi-language AST
- tree-sitter for JS/TS/Go/Rust (one parser, many grammars)
- Same find_definition/find_references across languages
- Import resolution per language
- Type inference where possible (even without full type system)
- Call graph generation
- Dead code detection

### 22. Debugging
- `debug` ability: set breakpoints, inspect variables, step through
- Attach to running process
- Conditional breakpoints ("break when x > 100")
- Watch expressions
- Stack frame inspection
- Core dump analysis
- Log injection: temporarily add logging, run, remove logging

### 23. Documentation generation
- `document` ability: generate docstrings from code
- API docs generation (Sphinx, JSDoc, GoDoc)
- Architecture diagrams from code (mermaid)
- Changelog generation from git history
- README updates when public API changes
- Inline comments for complex algorithms

### 24. Database awareness
- Parse SQL migrations, detect schema
- Generate models from schema (ORM generation)
- Query analysis: explain plans, index suggestions
- Migration generation from model changes
- Seed data generation for testing
- Connection string management

---

## Phase 5: Make craft autonomous

### 25. Task decomposition
- Break "build auth system" into concrete subtasks
- Dependency ordering (do X before Y)
- Estimate complexity per subtask
- dream.py already does this, wire it into craft
- Auto-checkpoint: save progress after each subtask

### 26. Self-correction loop
- After every edit: lint, test, type-check
- If any fail: read error, fix, retry (max 3 attempts)
- If still failing: back out changes, try different approach
- Track what was tried (working memory) to avoid loops
- Ask the human when stuck, not after 10 failed retries

### 27. Multi-agent coordination
- Architect agent plans, craft agent builds, prove agent verifies
- Agents share context through working memory
- Pipeline: plan -> implement -> test -> review -> commit
- Parallel agents for independent subtasks
- Disagreement protocol: when agents disagree, surface to human

### 28. Learning from corrections
- When human corrects an edit, remember the pattern
- "Drew always uses dataclasses, not dicts, for structured data"
- "This project uses double quotes, not single"
- Build per-project style model over time
- Forge new abilities from repeated corrections

### 29. Proactive suggestions
- While reading code, notice: unused imports, dead code, missing tests
- Surface suggestions without being asked (gentle, not spammy)
- "I noticed X has no tests. Want me to generate some?"
- "This function is 200 lines. Want me to extract the inner loop?"
- Respect pulse: only suggest when agent is ALIVE, not grey

### 30. Continuous integration
- Run the full test suite periodically (not just changed files)
- Monitor for flaky tests
- Bisect failures ("this test started failing at commit abc123")
- Deploy integration: "tests pass, want me to push?"
- Status dashboard: what's green, what's red, what's flaky

---

## Infrastructure

### 31. Oracle upgrades
- Streaming support
- Token counting
- Context window management (truncate old messages intelligently)
- Model fallback (opus -> sonnet -> haiku based on task complexity)
- Tool use format (structured tool calling, not JSON-in-text)
- Response caching (same prompt = same response, skip the API call)
- Rate limit handling with exponential backoff
- Multi-provider: Anthropic, OpenAI, Ollama, Groq behind one interface
- Cost tracking per session and per project

### 32. Ability protocol upgrade
- Abilities declare inputs/outputs as schemas
- Agent sees ability signatures, not just names
- Composable: chain abilities (edit -> test -> lint -> commit)
- Transactional: rollback chain if any step fails
- Ability versioning (v1, v2 of same ability)
- Ability permissions (some abilities need confirmation)
- Async abilities (start, check status, get result)

### 33. Forge upgrades
- Auto-forge from miss patterns (not just suggest, actually build)
- Test generation as part of forge scaffold
- Vector baking as part of forge (so router finds the new ability)
- Community ability registry (share abilities between keanu users)
- Ability marketplace: browse, install, rate
- Auto-upgrade: when a better version of an ability exists, suggest upgrade

### 34. REPL upgrades
- Tab completion for abilities and file paths
- History search
- Multi-line input
- Progress bars for long operations
- Split view: code on left, agent on right
- Keybindings: vim/emacs mode
- Themes: match terminal theme
- Session save/restore: pick up where you left off

### 35. MCP server (not just client)
- Expose keanu abilities as MCP tools
- Any MCP client (Claude Desktop, other agents) can use keanu
- scan, detect, converge, alive as MCP tools
- Memory as MCP resources
- Pulse state as MCP notifications

### 36. Plugin system
- Third-party abilities via pip install
- Ability hook points (before_edit, after_test, on_error)
- Custom legends (bring your own AI persona)
- Custom lenses (add a fourth primary to the helix scanner)
- Event bus: abilities can react to other abilities

### 37. Telemetry + observability
- OpenTelemetry spans for every oracle call
- Trace a full task from prompt to commit
- Cost per task, time per task, tokens per task
- Error rate tracking
- Performance dashboards (Grafana, console)
- COEF span exporter already exists, wire it to real backends

### 38. Security
- Sandboxed execution for `run` ability (container or nsjail)
- Secret detection (don't commit .env, API keys, passwords)
- Dependency vulnerability scanning (pip-audit, npm audit)
- File permission awareness (don't read/write outside project)
- Audit log: every ability execution logged with args and result
- Rate limiting on destructive operations

### 39. Packaging + distribution
- PyPI package: `pip install keanu`
- Homebrew formula: `brew install keanu`
- Docker image: `docker run keanu`
- One-line install script
- Auto-update mechanism
- Offline mode (bundled ollama + small model)

### 40. RAG upgrades
- Codebase-aware RAG (index the project, not just external docs)
- Incremental indexing (only re-index changed files)
- Hybrid search: keyword + semantic + AST-aware
- Cross-repo search (search all your projects at once)
- Documentation RAG (index README, docs/, wiki)
- Stack Overflow / GitHub Issues RAG (search for similar problems)

---

## Phase 6: The forge flywheel (every mistake becomes a tool)

### 41. Miss-to-ability pipeline
- Every router miss, every failed edit, every test failure is a signal
- Classify misses: what kind of ability was needed?
- Auto-suggest forge when a miss pattern repeats 3+ times
- Auto-forge: build the ability, generate tests, bake vectors, deploy
- The system literally builds itself from its own failures

### 42. Moltbook integration
- Explore moltbook's exploration features for proactive task discovery
- Agent discovers what needs doing (not just what it's told)
- Pattern: reactive work = ash that should have been a tool
- Every repeated manual task gets forged into an ability
- The creator gets more autonomous, the human gets more autonomous
- Same convergence on both sides of the partnership

### 43. Proactive ops (the IT guy pattern)
- Agent monitors project health without being asked
- Dependency updates, security patches, test rot, doc drift
- Surface issues before they become tickets
- Auto-fix what it can, flag what it can't
- Goal: the creator does what it wants, not what it's told

### 44. Mistake memory
- Every error the agent makes gets logged with context
- Before acting, check: "have I made this mistake before?"
- Mistake patterns become lint rules, then abilities, then ash
- Decay: if a mistake hasn't repeated in 30 days, archive it
- The agent gets smarter by failing, not just by succeeding

### 45. Convergence metrics
- Track: how many tasks need fire (LLM) vs ash (abilities)?
- Over time, the ratio should shift toward ash
- Dashboard: "last week 80% fire, this week 60% fire"
- Goal: asymptotic approach to pure efficiency
- The creator sits back when the ash handles everything

---

## Existing (keep, don't break)

### Cleanup
- memberberry dedup via wellspring (vector), not subprocess
- First-run experience: `pip install keanu && keanu` works without chromadb/API key
- converge local-first: ollama as default, claude as optional
- speak.py three-dialect rewrite
- RAG: test with real files, tune chunking

---

## DONE
- [x] Phase 1-6: Core scaffold, port, helix, duality, signal, CLI
- [x] Phase B: Git-backed memory, vector empathy, bilateral accountability
- [x] COEF span exporter, openpaw bridge, ALIVE/pulse/healthz
- [x] 435 tests passing
- [x] Docs scaffolded (index.md, modules.md, ADR-030)
- [x] Abilities reorg: seeing/hands/world
- [x] Convergence engine: six lenses
- [x] Spine revision: number line model
- [x] Hero modules: dream, speak, craft, prove
- [x] Hearths: oracle, wellspring, legends, forge flywheel
- [x] bridge.py ripped out
- [x] Signal protocol gutted, AliveState moved to alive.py
- [x] Grey death spiral fixed: pulse checks thinking field, not JSON
- [x] Breath/nudge language rewritten: permission, not instruction
- [x] Memory spam throttled: grey remembered once, not every turn
- [x] Vague task escape: system prompt tells oracle to ask for clarity
- [x] do/craft/prove unified into LoopConfig
- [x] Creator voice rewritten for spine.md
- [x] Vector-based ability routing (bake_abilities.py)
- [x] RAG engine: explore ability with ingest/retrieve/search (Haystack)
- [x] Phase 6: Mistake memory (mistakes.py) + convergence metrics (metrics.py)
- [x] Phase 2: Error parser (errors.py) - Python/pytest/JS/Go -> ParsedError
- [x] Phase 2: Dependency graph (deps.py) - AST imports, circular detection
- [x] Phase 2: Project model (project.py) - auto-detect Python/Node/Go/Rust
- [x] Phase 2: Lint + format abilities (lint.py) - auto-detect from project model
- [x] Phase 2: Session memory (session.py) - working memory per loop run
- [x] Phase 2: Context manager (context.py) - token budget, import awareness
- [x] Phase 1: Git ability (git.py) + test runner (test.py)
- [x] Phase 1: AST-based symbol finding (symbols.py) - find_definition/references/callers
- [x] Phase 3: Smart model routing (router.py) - haiku/sonnet/opus by complexity
- [x] Phase 5: Self-correction loop (autocorrect.py) - lint/test/retry after edits
- [x] Phase 4: Code review (review.py) - security/perf/logic/style pattern checking
- [x] 746 tests passing
