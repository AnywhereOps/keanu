"""keanu CLI: unified entry point.

Usage:
    keanu                               # launch the REPL
    keanu do "task"                     # general-purpose agent
    keanu do "task" --craft             # code agent (hands only)
    keanu do "task" --prove             # evidence agent
    keanu ask "question"                # convergence loop
    keanu dream "build auth system"     # planner
    keanu speak "technical content" -a friend  # translator
    keanu scan document.md              # three-primary reading
    keanu memory remember goal "ship"   # store a memory
    keanu memory recall "what next"     # recall memories
    keanu memory plan "next week"       # generate plan
    keanu memory log                    # recent log entries
    keanu memory stats                  # counts and tags
    keanu health                        # system health dashboard
"""

import argparse
import atexit
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from keanu.log import info, warn


# ============================================================
# HELPERS
# ============================================================

def _get_store(shared=False):
    if shared:
        from keanu.memory import GitStore
        return GitStore()
    from keanu.memory import MemberberryStore
    return MemberberryStore()


def _maybe_store(args):
    """get memberberry store if --no-memory wasn't passed."""
    if getattr(args, 'no_memory', False):
        return None
    try:
        from keanu.memory import MemberberryStore
        return MemberberryStore()
    except Exception:
        return None


def _print_steps(steps):
    """print agent step log."""
    if not steps:
        return
    print("  Steps:")
    for s in steps:
        status = "ok" if s.ok else "FAIL"
        print(f"    [{s.turn}] {s.action} ({status}): {s.result[:80]}")
    print()


def _print_feel(feel_stats):
    """print feel stats one-liner."""
    checks = feel_stats.get("total_checks", 0)
    breaths = feel_stats.get("breaths_given", 0)
    hits = feel_stats.get("ability_hits", 0)
    if checks or hits:
        parts = []
        if checks:
            parts.append(f"{checks} checks")
        if breaths:
            parts.append(f"{breaths} breaths")
        if hits:
            parts.append(f"{hits} abilities")
        print(f"  Feel: {', '.join(parts)}")
        print()


def _print_loop_result(result, max_turns=25):
    """print result from any agent loop."""
    if result.ok:
        print(f"\n  Done ({len(result.steps)} steps).\n")
        if result.answer:
            print(f"  {result.answer}\n")
        extras = result.extras
        if extras.get("files_changed"):
            print("  Files changed:")
            for f in extras["files_changed"]:
                print(f"    {f}")
            print()
        if extras.get("verdict"):
            v = extras["verdict"].upper()
            print(f"  Verdict: {v} (confidence: {extras.get('confidence', 0):.0%})\n")
            for label, key, prefix in [
                ("Evidence for", "evidence_for", "+"),
                ("Evidence against", "evidence_against", "-"),
                ("Gaps", "gaps", "?"),
            ]:
                items = extras.get(key, [])
                if items:
                    print(f"  {label}:")
                    for item in items:
                        print(f"    {prefix} {item}")
                    print()
            if extras.get("summary"):
                print(f"  {extras['summary']}\n")
    elif result.status == "paused":
        print(f"\n  Paused: {result.error}\n")
    elif result.status == "max_turns":
        print(f"\n  Hit turn limit ({max_turns}).\n")
        if result.steps:
            last = result.steps[-1]
            print(f"  Last: {last.action} -> {last.result[:120]}\n")
    else:
        print(f"\n  Error: {result.error}\n")
    _print_steps(result.steps)
    _print_feel(result.feel_stats)


def _add_legend_args(p):
    """add --legend and --model to a parser."""
    p.add_argument("--legend", "-l", default="creator",
                   help="Which legend answers (default: creator)")
    p.add_argument("--model", "-m", default=None, help="Model name")


def _add_agent_args(p, max_turns=0):
    """add --legend, --model, --max-turns, --no-memory to a parser."""
    _add_legend_args(p)
    p.add_argument("--max-turns", type=int, default=max_turns,
                   help=f"Max turns, 0=unlimited (default: {max_turns})")
    p.add_argument("--no-memory", action="store_true",
                   help="Don't use memberberry store")


# ============================================================
# HERO COMMANDS
# ============================================================

def cmd_do(args):
    """Run the agent loop. --craft for code, --prove for evidence."""
    from keanu.hero.do import run as do_run, craft, prove

    if getattr(args, 'craft', False):
        result = craft(args.task, legend=args.legend, model=args.model,
                       store=_maybe_store(args), max_turns=args.max_turns)
    elif getattr(args, 'prove', False):
        result = prove(args.task, legend=args.legend, model=args.model,
                       store=_maybe_store(args), max_turns=args.max_turns)
    else:
        result = do_run(task=args.task, legend=args.legend, model=args.model,
                        store=_maybe_store(args), max_turns=args.max_turns)
    _print_loop_result(result, args.max_turns)



def cmd_ask(args):
    """Run the convergence loop on a question."""
    from keanu.hero.loop import run as agent_run
    from keanu.abilities.world.converge.graph import DualityGraph

    # RAG context injection
    rag_context = ""
    if getattr(args, "rag", False):
        from keanu.abilities.seeing.explore.retrieve import build_context
        rag_context = build_context(args.question, include_web=getattr(args, "web", False))
        if rag_context:
            info("cli", f"RAG context: {len(rag_context)} chars")

    question = args.question
    if rag_context:
        question = f"{rag_context}\n{args.question}"

    graph = DualityGraph()
    result = agent_run(
        question=question,
        legend=args.legend,
        model=args.model,
        graph=graph,
        store=_maybe_store(args),
        max_workers=args.workers,
    )

    if not result.accepted:
        print(f"\n  Not sure this is the right question yet.\n")
        if result.assessment and result.assessment.concerns:
            print(f"  Concerns:")
            for c in result.assessment.concerns:
                print(f"    - {c}")
        print(f"\n  Say more, or come at it differently.\n")
        return

    print(f"\n{'=' * 60}")
    print(f"  CONVERGENCE")
    print(f"{'=' * 60}")
    if result.one_line:
        print(f"\n  {result.one_line}\n")
    if result.convergence:
        print(f"  {result.convergence}\n")
    if result.what_changes:
        print(f"  What changes: {result.what_changes}\n")
    if result.learnings:
        print(f"  Learnings:")
        for l in result.learnings:
            print(f"    - {l}")
        print()
    _print_feel(result.feel_stats)


def cmd_dream(args):
    """Dream up a plan."""
    from keanu.hero.dream import dream
    result = dream(args.goal, context=args.context or "", legend=args.legend, model=args.model)
    if not result.ok:
        print(f"\n  Dream failed: {result.error}\n")
        return
    print(f"\n  Dream: {result.goal}")
    print(f"  {result.total_steps} steps across {len(result.phases)} phases\n")
    for i, phase in enumerate(result.phases, 1):
        print(f"  Phase {i}: {phase.get('name', 'unnamed')}")
        for step in phase.get("steps", []):
            dep = f" (after: {step['depends_on']})" if step.get("depends_on") else ""
            print(f"    - {step['action']}{dep}")
            if step.get("why"):
                print(f"      {step['why']}")
        print()


def cmd_speak(args):
    """Speak content to a specific audience."""
    from keanu.hero.speak import speak
    content = args.content
    if args.file:
        with open(args.file) as f:
            content = f.read()
    if not content:
        print("  Provide content as argument or --file")
        return
    result = speak(content, audience=args.audience, legend=args.legend, model=args.model)
    if not result.ok:
        print(f"\n  Speak failed: {result.error}\n")
        return
    print(f"\n  Audience: {result.audience}\n")
    print(f"  {result.translation}\n")
    if result.key_shifts:
        print(f"  Shifts:")
        for shift in result.key_shifts:
            print(f"    - {shift}")
        print()


# ============================================================
# ANALYSIS COMMANDS
# ============================================================

def cmd_scan(args):
    from keanu.abilities.seeing.scan.helix import run
    for filepath in args.files:
        run(filepath, output_json=args.json)


def cmd_bake(args):
    from keanu.abilities.seeing.scan.bake import bake
    bake(args.lenses if args.lenses else None)


def cmd_ingest(args):
    from keanu.abilities.seeing.explore.ingest import ingest, DEFAULT_COLLECTION
    collection = args.collection or DEFAULT_COLLECTION
    total_files = 0
    total_chunks = 0
    for path in args.paths:
        result = ingest(path, collection=collection)
        total_files += result["files"]
        total_chunks += result["chunks"]
        print(f"  {path}: {result['files']} files, {result['chunks']} chunks")
    print(f"\n  Total: {total_files} files, {total_chunks} chunks in '{collection}'\n")


def cmd_search(args):
    from keanu.abilities.seeing.explore.search import web_search
    results = web_search(args.query, n_results=args.limit)
    if not results:
        print("\n  No results found. Set SERPER_API_KEY for web search.\n")
        return
    print()
    for r in results:
        print(f"  [{r['title']}]({r['url']})")
        print(f"    {r['snippet']}\n")


def cmd_git(args):
    """Run git operations."""
    from keanu.abilities.hands.git import GitAbility
    ab = GitAbility()
    ctx = {"op": args.op}
    if args.file:
        ctx["file"] = args.file
    if args.n:
        ctx["n"] = args.n
    if args.name:
        ctx["name"] = args.name
    if args.message:
        ctx["message"] = args.message
    if args.staged:
        ctx["staged"] = True
    if args.sub:
        ctx["sub"] = args.sub
    if args.files:
        ctx["files"] = args.files
    result = ab.execute("", ctx)
    if result["success"]:
        print(f"\n{result['result']}\n")
    else:
        print(f"\n  Error: {result['result']}\n")


def cmd_test(args):
    """Run test operations."""
    from keanu.abilities.hands.test import TestAbility
    ab = TestAbility()
    ctx = {"op": args.op}
    if args.target:
        ctx["target"] = args.target
    if args.files:
        ctx["files"] = args.files
    result = ab.execute("", ctx)
    print(f"\n{result['result']}\n")
    if result["data"].get("failures"):
        print(f"  Failures ({result['data']['failure_count']}):")
        for f in result["data"]["failures"]:
            print(f"    {f['file']}::{f['test']} - {f['error']}")
        print()


def cmd_lint(args):
    """Run project linter."""
    from keanu.abilities.hands.lint import LintAbility
    ab = LintAbility()
    ctx = {}
    if args.path:
        ctx["path"] = args.path
    if args.fix:
        ctx["fix"] = True
    result = ab.execute("", ctx)
    print(f"\n{result['result']}\n")
    if result["data"].get("issues"):
        print(f"  Issues ({result['data']['issue_count']}):")
        for issue in result["data"]["issues"][:20]:
            print(f"    {issue['file']}:{issue['line']} {issue['message']}")
        print()


def cmd_format(args):
    """Run project formatter."""
    from keanu.abilities.hands.lint import FormatAbility
    ab = FormatAbility()
    ctx = {}
    if args.path:
        ctx["path"] = args.path
    if args.check:
        ctx["check"] = True
    result = ab.execute("", ctx)
    print(f"\n{result['result']}\n")


def cmd_converge(args):
    from keanu.abilities.world.converge.engine import run
    result = run(args.question, legend=args.legend, model=args.model, verbose=True)
    if not result.ok:
        print(f"Could not converge: {result.error or 'no synthesis'}")
        return
    print(f"\n{'=' * 60}")
    print(f"  CONVERGENCE: {result.one_line}")
    print(f"{'=' * 60}")
    if result.synthesis and result.synthesis != result.one_line:
        print(f"\n{result.synthesis}")
    if result.tensions:
        print(f"\nUnresolved tensions:")
        for t in result.tensions:
            print(f"  - {t}")
    if result.what_changes:
        print(f"\nWhat changes: {result.what_changes}")
    print(f"\nLens readings:")
    for r in result.readings:
        status = " [BLACK]" if r.black else ""
        print(f"  {r.name}: {r.turns} turns, {r.score:.1f}/10{status}")


def cmd_connect(args):
    from keanu.abilities.world.converge.connection import run
    run(args.source_a, args.source_b)


def cmd_compress(args):
    from keanu.abilities.world.compress.dns import ContentDNS
    store = ContentDNS()
    with open(args.file) as f:
        content = f.read()
    print(f"Stored: {store.store(content)[:16]}")


def cmd_detect(args):
    from keanu.abilities.seeing.detect.engine import run
    from keanu.abilities.seeing.detect import DETECTORS
    detectors = DETECTORS if args.detector == "all" else [args.detector]
    for d in detectors:
        run(args.file, d, title=d.upper().replace("_", " ") + " SCAN",
            output_json=args.json)


def cmd_alive(args):
    import json as _json
    from keanu.alive import diagnose
    if args.text:
        text = args.text
    elif args.file:
        with open(args.file) as f:
            text = f.read()
    else:
        text = sys.stdin.read()
    reading = diagnose(text)
    if args.json:
        print(_json.dumps(reading.to_dict(), indent=2))
    else:
        print()
        print(reading.summary())
        print()


# ============================================================
# MEMORY COMMANDS
# ============================================================

def cmd_memory_remember(args):
    from keanu.log import remember as log_remember
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    log_remember(args.content, memory_type=args.type, tags=tags,
                 importance=args.importance, source="cli")
    print(f"  Remembered [{args.type}] {args.content}")
    print(f"  importance: {args.importance} | tags: {', '.join(tags) or 'none'}")


def cmd_memory_recall(args):
    from keanu.log import recall as log_recall
    results = log_recall(query=args.query or "", memory_type=args.type, limit=args.limit)
    if not results:
        info("memory", f"recall '{args.query or 'all'}' -> 0 results")
        print("  No memories found.")
        return
    info("memory", f"recall '{args.query or 'all'}' -> {len(results)} results")
    print(f"\n  Recalled {len(results)} memories:\n")
    for m in results:
        content = m.get("content", "")
        mtype = m.get("memory_type", "")
        tags_str = ", ".join(m.get("tags", [])) if isinstance(m.get("tags"), list) else m.get("tags", "")
        if (not mtype or mtype == "log") and m.get("attrs"):
            mtype = m["attrs"].get("memory_type", mtype)
            tags_str = m["attrs"].get("tags", tags_str)
        print(f"  [{mtype[:4].upper() if mtype else '????'}] {content}")
        if tags_str:
            print(f"    tags: {tags_str}")
        print()


def cmd_memory_plan(args):
    from keanu.memory import MemberberryStore, PlanGenerator
    store = MemberberryStore()
    if args.list:
        plans = store.get_plans(status=args.status)
        if not plans:
            print("  No plans found.")
            return
        print(f"\n  {len(plans)} plan(s):\n")
        for p in plans:
            print(f"  [{p['status'].upper()}] {p['title']}")
            print(f"    {len(p.get('actions', []))} actions | target: {p.get('target_date', '?')[:10]} | id: {p['id']}")
            print()
        return

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
    planner = PlanGenerator(store)
    plan = planner.generate_plan(focus=args.focus, tags=tags, horizon_days=args.days)
    print(f"\n  Plan: {plan.title}")
    print(f"  Status: {plan.status} | Target: {plan.target_date[:10]}")
    print(f"  {plan.notes}")
    print(f"  ID: {plan.id}\n")
    if plan.actions:
        print("  Actions:")
        for a in plan.actions:
            deadline = a.get("deadline", "")[:10] if a.get("deadline") else "no deadline"
            print(f"    {a['description']}")
            print(f"      due: {deadline}")
        print()
    else:
        print("  No actions generated. Store more memories first!\n")


def cmd_memory_log(args):
    from keanu.log import recall as log_recall
    results = log_recall(query="", limit=args.limit)
    if not results:
        print("  No log entries.")
        return
    print(f"\n  Last {len(results)} log entries:\n")
    for r in results:
        content = r.get("content", "")[:120]
        tags = r.get("tags", [])
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        print(f"  {content}{tag_str}")
    print()


def cmd_memory_stats(args):
    store = _get_store(getattr(args, 'shared', False))
    s = store.stats()
    print(f"\n  memberberry stats")
    print(f"  Memories: {s['total_memories']}")
    for t, c in s["memories_by_type"].items():
        print(f"    {t}: {c}")
    print(f"  Plans: {s['total_plans']}")
    for st, c in s["plans_by_status"].items():
        print(f"    {st}: {c}")
    print(f"  Tags: {', '.join(s['unique_tags']) or 'none'}")
    print()


def cmd_memory_sync(args):
    from keanu.memory import GitStore
    store = GitStore()
    store.sync()
    s = store.stats()
    print(f"  Synced. {s['shared_memories']} shared memories across {len(s['namespaces'])} namespaces.")


def cmd_memory_disagree(args):
    from keanu.memory import DisagreementTracker
    store = _get_store(args.shared)
    tracker = DisagreementTracker(store)
    if args.action == "record":
        if not args.topic or not args.human or not args.ai:
            print("Usage: keanu memory disagree record --topic 'x' --human 'y' --ai 'z'")
            return
        d = tracker.record(args.topic, args.human, args.ai)
        print(f"  Recorded disagreement: {d.topic}")
        print(f"  id: {d.id}")
        if d.human_reading:
            print(f"  Human: {', '.join(r['state'] for r in d.human_reading)}")
        if d.ai_reading:
            print(f"  AI: {', '.join(r['state'] for r in d.ai_reading)}")
    elif args.action == "resolve":
        if not args.id or not args.winner:
            print("Usage: keanu memory disagree resolve --id <id> --winner human|ai|compromise")
            return
        if tracker.resolve(args.id, args.winner, resolved_by=args.resolved_by or ""):
            print(f"  Resolved {args.id}: {args.winner}")
        else:
            print(f"  Disagreement {args.id} not found")
    elif args.action == "stats":
        s = tracker.stats()
        print(f"\n  Disagreement stats")
        print(f"  Total: {s['total']} | Resolved: {s['resolved']} | Unresolved: {s['unresolved']}")
        if s['resolved'] > 0:
            print(f"  Human wins: {s['human_wins']} | AI wins: {s['ai_wins']} | Compromises: {s['compromises']}")
        if s['alerts']:
            for alert in s['alerts']:
                print(f"  !! {alert}")
        print()
    elif args.action == "list":
        records = tracker.get_all()
        if not records:
            print("  No disagreements recorded.")
            return
        print(f"\n  {len(records)} disagreement(s):\n")
        for r in records:
            print(f"  [{r.get('memory_type', '?')[:4].upper()}] {r['content']}")
            print(f"    id: {r['id']}")
        print()


# ============================================================
# SYSTEM COMMANDS
# ============================================================

def _health_memory(store):
    s = store.stats()
    total = s["total_memories"]
    print(f"  MEMORY")
    print(f"    memories:  {total}")
    if s["memories_by_type"]:
        parts = [f"{t}: {c}" for t, c in s["memories_by_type"].items()]
        print(f"    by type:   {', '.join(parts)}")
    print(f"    plans:     {s['total_plans']}")
    tags = s["unique_tags"]
    print(f"    tags:      {len(tags)} unique" + (f" ({', '.join(tags[:8])}{'...' if len(tags) > 8 else ''})" if tags else ""))
    print()
    return total


def _health_disagreement(tracker, total_memories):
    ds = tracker.stats()
    print(f"  DISAGREEMENT")
    print(f"    total:     {ds['total']}")
    if ds["total"] > 0:
        print(f"    resolved:  {ds.get('resolved', 0)}")
        print(f"    open:      {ds.get('unresolved', 0)}")
    if ds["alerts"]:
        for alert in ds["alerts"]:
            print(f"    !! {alert}")
    elif ds["total"] == 0 and total_memories > 20:
        print(f"    !! No disagreements in {total_memories} memories. Watch for sycophancy.")
    elif ds["total"] == 0:
        print(f"    (no disagreements yet)")
    print()


def _health_modules():
    print(f"  MODULES")
    modules = {
        "scan/helix":     ("keanu.abilities.seeing.scan.helix", "needs chromadb"),
        "detect/mood":    ("keanu.abilities.seeing.detect.mood", "color theory"),
        "detect/engine":  ("keanu.abilities.seeing.detect.engine", "pattern vectors"),
        "compress/dns":   ("keanu.abilities.world.compress.dns", "content-addressable"),
        "converge":       ("keanu.abilities.world.converge.engine", "duality synthesis"),
        "memory":         ("keanu.memory.memberberry", "remember/recall/plan"),
        "memory/git":     ("keanu.memory.gitstore", "shared JSONL"),
        "memory/disagree":("keanu.memory.disagreement", "bilateral tracker"),
    }
    for name, (mod_path, desc) in modules.items():
        try:
            __import__(mod_path)
            print(f"    {name:<18} OK    {desc}")
        except ImportError as e:
            print(f"    {name:<18} MISS  {desc} ({e})")
        except Exception as e:
            print(f"    {name:<18} ERR   {desc} ({e})")
    print()


def _health_oracle():
    import os
    print(f"  ORACLE")
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        print(f"    api key:   {masked}")
    else:
        print(f"    api key:   NOT SET (set ANTHROPIC_API_KEY)")
    print()


def _health_vectors():
    print(f"  VECTORS")
    try:
        from keanu.wellspring import depths
        chroma_dir = Path(depths())
        if not chroma_dir.exists():
            print(f"    status:    NOT BAKED (run keanu bake)")
            print()
            return
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(chroma_dir))
            collections = client.list_collections()
            names = [c.name for c in collections]
            print(f"    status:    baked ({len(collections)} collections)")
            for name in sorted(names):
                count = client.get_collection(name).count()
                print(f"    {name:<16} {count} vectors")
        except ImportError:
            print(f"    status:    chromadb not installed")
        except Exception as e:
            print(f"    status:    error ({e})")
    except Exception as e:
        print(f"    status:    error ({e})")
    print()


def _health_forge():
    from keanu.abilities import list_abilities
    from keanu.abilities.miss_tracker import get_misses
    abilities = list_abilities()
    misses = get_misses(limit=100)
    print(f"  FORGE")
    print(f"    abilities: {len(abilities)} registered")
    print(f"    misses:    {len(misses)} logged")
    if misses:
        from keanu.abilities.miss_tracker import analyze_misses
        top = analyze_misses(limit=100)[:3]
        if top:
            words = ", ".join(f"{w} ({c}x)" for w, c in top)
            print(f"    top miss:  {words}")
    print()


def _health_convergence():
    try:
        from keanu.abilities.world.metrics import ratio
        from keanu.abilities.world.mistakes import stats as mistake_stats
        r = ratio(7)
        ms = mistake_stats()
        print(f"  CONVERGENCE")
        if r["total"] > 0:
            pct = int(r["ratio"] * 100)
            print(f"    fire/ash:  {r['fire']}/{r['ash']} ({pct}% ash, {r['trend']})")
        else:
            print(f"    fire/ash:  no data yet")
        print(f"    mistakes:  {ms['active']} active, {ms['patterns_forgeable']} forgeable")
        print()
    except Exception as e:
        print(f"  CONVERGENCE")
        print(f"    error: {e}")
        print()


def _health_deps():
    print(f"  EXTERNAL DEPS")
    for dep, purpose in {"chromadb": "vector storage", "requests": "LLM API"}.items():
        try:
            __import__(dep)
            print(f"    {dep:<14} installed     {purpose}")
        except ImportError:
            print(f"    {dep:<14} not installed {purpose}")
    print()


def cmd_health(args):
    from keanu.memory import MemberberryStore, DisagreementTracker
    store = _get_store(args.shared)
    tracker = DisagreementTracker(store)
    print("\n  ╔══════════════════════════════════════╗")
    print("  ║          keanu health                ║")
    print("  ╚══════════════════════════════════════╝\n")
    _health_oracle()
    _health_vectors()
    total = _health_memory(store)
    _health_disagreement(tracker, total)
    _health_forge()
    _health_convergence()
    _health_modules()
    _health_deps()


def cmd_abilities(args):
    from keanu.abilities import list_abilities, get_grimoire
    abilities = list_abilities()
    grimoire = get_grimoire()
    hands = {"read", "write", "edit", "search", "ls", "run", "git", "test"}
    world = {"fuse", "recall", "soulstone"}
    categories = [
        ("SEEING", [a for a in abilities if a["name"] not in hands and a["name"] not in world]),
        ("WORLD", [a for a in abilities if a["name"] in world]),
        ("HANDS", [a for a in abilities if a["name"] in hands]),
    ]
    print(f"\n  THE ACTION BAR ({len(abilities)} abilities)\n")
    for cat_name, cat_abilities in categories:
        if not cat_abilities:
            continue
        print(f"  {cat_name}")
        for ab in cat_abilities:
            uses = grimoire.get(ab["name"], {}).get("use_count", 0)
            count_str = f"{uses} cast{'s' if uses != 1 else ''}" if uses else "--"
            label = (ab.get("cast_line", "") or ab["description"]).rstrip(".")
            print(f"    {ab['name']:<14}{label:<34}{count_str:>10}")
        print()


def cmd_metrics(args):
    """Show convergence metrics dashboard."""
    from keanu.abilities.world.metrics import dashboard
    d = dashboard(days=args.days)
    r = d["fire_ash_ratio"]
    print(f"\n  CONVERGENCE METRICS ({d['period_days']}d)\n")
    print(f"  {d['message']}")
    print(f"  fire: {r['fire']}  ash: {r['ash']}  ratio: {r['ratio']}")
    if d["by_ability"]:
        print(f"\n  Top abilities:")
        for a in d["by_ability"][:5]:
            print(f"    {a['ability']:<14} {a['count']:>4}x  ({a['success_rate']:.0%} success)")
    if d["by_legend"]:
        print(f"\n  Fire by legend:")
        for l in d["by_legend"]:
            print(f"    {l['legend']:<14} {l['calls']:>4} calls  {l['total_tokens']:>6} tokens")
    if d["forges_30d"]:
        print(f"\n  Forged (30d): {d['forges_30d']} new abilities")
    print()


def cmd_mistakes(args):
    """Show mistake patterns."""
    from keanu.abilities.world.mistakes import get_patterns, stats as mistake_stats, clear_stale
    if args.clear:
        removed = clear_stale()
        print(f"  Cleared {removed} stale mistakes.")
        return
    s = mistake_stats()
    print(f"\n  MISTAKE MEMORY\n")
    print(f"  total: {s['total']}  active: {s['active']}  stale: {s['stale']}")
    if s["by_category"]:
        print(f"\n  By category:")
        for cat, count in s["by_category"].items():
            print(f"    {cat:<20} {count}x")
    patterns = get_patterns()
    forgeable = [p for p in patterns if p["forgeable"]]
    if forgeable:
        print(f"\n  Forgeable patterns (3+ repeats):")
        for p in forgeable:
            print(f"    {p['action']}/{p['category']}: {p['count']}x  \"{p['latest_error'][:60]}\"")
    elif patterns:
        print(f"\n  No forgeable patterns yet (need 3+ repeats)")
    else:
        print(f"\n  No mistakes recorded yet. Start using craft.")
    print()


def cmd_review(args):
    """Review code for issues."""
    from keanu.analysis.review import review_diff, review_file
    import subprocess

    if args.file:
        result = review_file(args.file)
    else:
        # review staged changes by default
        diff = subprocess.run(
            ["git", "diff", "--staged"] if args.staged else ["git", "diff"],
            capture_output=True, text=True,
        ).stdout
        if not diff:
            diff = subprocess.run(
                ["git", "diff", "HEAD~1"] if not args.staged else ["git", "diff", "--staged"],
                capture_output=True, text=True,
            ).stdout
        if not diff:
            print("\n  No changes to review.\n")
            return
        result = review_diff(diff)

    if result.issues:
        print(f"\n  REVIEW: {result.summary}\n")
        for issue in result.issues[:30]:
            icon = {"critical": "!!", "warning": " !", "info": "  ", "style": "  "}
            prefix = icon.get(issue.severity, "  ")
            print(f"  {prefix} {issue.file}:{issue.line} [{issue.category}] {issue.message}")
            if issue.suggestion:
                print(f"      -> {issue.suggestion}")
    else:
        print(f"\n  {result.summary}\n")
    print()


def cmd_symbols(args):
    """Find symbol definitions or references."""
    from keanu.analysis.symbols import find_definition, find_references, find_callers, list_symbols

    name = args.name
    root = args.root or "."

    if args.list_file:
        symbols = list_symbols(args.list_file)
        if symbols:
            print(f"\n  Symbols in {args.list_file}:\n")
            for s in symbols:
                parent = f" ({s.parent})" if s.parent else ""
                print(f"    {s.line:4d}  {s.kind:<10} {s.name}{parent}")
        else:
            print(f"\n  No symbols found in {args.list_file}")
        print()
        return

    if not name:
        print("  Usage: keanu symbols <name> or keanu symbols --list <file>")
        return

    if args.callers:
        results = find_callers(name, root)
        label = "Callers of"
    elif args.refs:
        results = find_references(name, root)
        label = "References to"
    else:
        results = find_definition(name, root)
        label = "Definitions of"

    if results:
        print(f"\n  {label} '{name}':\n")
        for r in results[:30]:
            if hasattr(r, "kind"):
                parent = f" ({r.parent})" if r.parent else ""
                print(f"    {r.file}:{r.line}  {r.kind}{parent}")
            else:
                print(f"    {r.file}:{r.line}  {r.context}")
    else:
        print(f"\n  No results for '{name}'")
    print()


def cmd_deps(args):
    """Show dependency graph stats."""
    from keanu.analysis.deps import stats as dep_stats, find_circular, external_deps
    root = args.root or "."

    if args.who:
        from keanu.analysis.deps import who_imports
        importers = who_imports(args.who, root)
        if importers:
            print(f"\n  Files that import {args.who}:\n")
            for f in sorted(importers):
                print(f"    {f}")
        else:
            print(f"\n  Nothing imports {args.who}")
        print()
        return

    s = dep_stats(root)
    print(f"\n  DEPENDENCY GRAPH\n")
    print(f"  files:      {s['files']}")
    print(f"  edges:      {s['edges']}")
    print(f"  external:   {s['external']} packages")
    print(f"  avg imports: {s['avg_imports']} per file")
    if s.get("hubs"):
        print(f"\n  Most imported (hubs):")
        for h in s["hubs"][:5]:
            print(f"    {h['file']:<40} {h['imported_by']} importers")
    cycles = find_circular(root)
    if cycles:
        print(f"\n  Circular imports ({len(cycles)}):")
        for c in cycles[:3]:
            print(f"    {' -> '.join(c)}")
    print()


def cmd_suggest(args):
    """Scan code for proactive suggestions."""
    from keanu.analysis.suggestions import scan_file, scan_directory, check_missing_tests

    if args.file:
        suggestions = scan_file(args.file)
        if suggestions:
            print(f"\n  Suggestions for {args.file}:\n")
            for s in suggestions:
                print(f"    {s}")
                if s.fix:
                    print(f"      -> {s.fix}")
        else:
            print(f"\n  No suggestions for {args.file}\n")
    elif args.missing_tests:
        suggestions = check_missing_tests(args.root or ".")
        if suggestions:
            print(f"\n  Missing test files:\n")
            for s in suggestions:
                print(f"    {s.file}: {s.message}")
        else:
            print(f"\n  All source files have tests.\n")
    else:
        report = scan_directory(args.root or ".")
        print(f"\n  {report.summary()}\n")
        if report.suggestions:
            for s in report.suggestions[:30]:
                print(f"    {s}")
    print()


def cmd_codegen(args):
    """Generate code from templates or function signatures."""
    from keanu.gen.codegen import scaffold, generate_tests, find_stubs

    if args.tests_for:
        result = generate_tests(args.tests_for)
        if result.success:
            if args.output:
                Path(args.output).write_text(result.code)
                print(f"\n  Generated tests -> {args.output}\n")
            else:
                print(f"\n{result.code}")
        else:
            print(f"\n  Error: {'; '.join(result.errors)}\n")
    elif args.stubs_in:
        stubs = find_stubs(args.stubs_in)
        if stubs:
            print(f"\n  Stubs in {args.stubs_in}:\n")
            for s in stubs:
                print(f"    {s['file']}:{s['line']}  {s['text']}")
        else:
            print(f"\n  No stubs found in {args.stubs_in}\n")
        print()
    elif args.template:
        variables = {}
        if args.name:
            variables["name"] = args.name
        if args.desc:
            variables["description"] = args.desc
        if args.keywords:
            variables["keywords"] = [k.strip() for k in args.keywords.split(",")]
        result = scaffold(args.template, variables)
        if result.success:
            if args.output:
                Path(args.output).write_text(result.code)
                print(f"\n  Scaffolded {args.template} -> {args.output}\n")
            else:
                print(f"\n{result.code}")
        else:
            print(f"\n  Error: {'; '.join(result.errors)}\n")
    else:
        print("  Usage: keanu gen --template ability --name greet")
        print("         keanu gen --tests-for src/keanu/oracle.py")
        print("         keanu gen --stubs-in src/keanu/oracle.py")


def cmd_mcp(args):
    """Run keanu as an MCP server over stdio."""
    from keanu.abilities.world.mcp_server import MCPServer
    server = MCPServer()
    server.run_stdio()


def cmd_docgen(args):
    """Generate documentation from code."""
    from keanu.gen.docgen import (
        generate_docstrings, generate_class_diagram,
        generate_changelog, generate_api_summary,
    )

    if args.docstrings:
        result = generate_docstrings(args.docstrings, style=args.style)
        if result.success:
            if args.write:
                Path(result.filepath).write_text(result.content)
                print(f"\n  Docstrings written to {result.filepath}\n")
            else:
                print(f"\n{result.content}")
        else:
            print(f"\n  Error: {'; '.join(result.errors)}\n")
    elif args.class_diagram:
        result = generate_class_diagram(args.class_diagram)
        if result.success:
            print(f"\n{result.content}\n")
        else:
            print(f"\n  Error: {'; '.join(result.errors)}\n")
    elif args.changelog:
        result = generate_changelog(n_commits=args.n)
        if result.success:
            print(f"\n{result.content}")
        else:
            print(f"\n  Error: {'; '.join(result.errors)}\n")
    elif args.api:
        result = generate_api_summary(args.api)
        if result.success:
            print(f"\n{result.content}")
        else:
            print(f"\n  Error: {'; '.join(result.errors)}\n")
    else:
        print("  Usage: keanu doc --docstrings file.py")
        print("         keanu doc --class-diagram file.py")
        print("         keanu doc --changelog")
        print("         keanu doc --api file.py")


def cmd_auto_forge(args):
    """Auto-forge pipeline: analyze misses, suggest or create abilities."""
    from keanu.gen.auto_forge import (
        get_all_candidates, auto_forge_all,
        check_project_health, forge_history,
    )

    if args.health:
        health = check_project_health(args.root or ".")
        print(f"\n  PROJECT HEALTH: {health['score']}/100\n")
        if health["issues"]:
            for issue in health["issues"]:
                icon = {"warning": "!", "info": " ", "hint": "?"}
                print(f"  {icon.get(issue['severity'], ' ')} [{issue['category']}] {issue['message']}")
        else:
            print("  No issues found.")
        print()
    elif args.history:
        history = forge_history()
        if history:
            print(f"\n  Forge history ({len(history)} entries):\n")
            for h in history:
                print(f"    {h['name']}  misses: {h['miss_count']}  confidence: {h.get('confidence', 0):.0%}")
        else:
            print("\n  No forge history yet.\n")
        print()
    elif args.run:
        results = auto_forge_all(min_count=args.min_count, dry_run=False)
        if results:
            print(f"\n  Auto-forged {len(results)} abilities:\n")
            for r in results:
                status = r["action"]
                name = r["candidate"]["name"]
                print(f"    [{status}] {name}")
                if r.get("result", {}).get("errors"):
                    for e in r["result"]["errors"]:
                        print(f"      error: {e}")
        else:
            print("\n  No candidates met the threshold.\n")
        print()
    else:
        # default: show candidates (dry run)
        results = auto_forge_all(min_count=args.min_count, dry_run=True)
        if results:
            print(f"\n  Forge candidates ({len(results)}):\n")
            for r in results:
                c = r["candidate"]
                print(f"    {c['name']:<20} {c['miss_count']}x misses  confidence: {c.get('confidence', 0):.0%}")
                if c.get("examples"):
                    print(f"      e.g. \"{c['examples'][0][:60]}\"")
        else:
            candidates = get_all_candidates(min_count=1)
            if candidates:
                print(f"\n  {len(candidates)} candidates below threshold (min_count={args.min_count}):\n")
                for c in candidates[:5]:
                    print(f"    {c.name:<20} {c.miss_count}x misses")
            else:
                print("\n  No forge candidates. The system is handling everything.\n")
        print()


def cmd_database(args):
    """Database schema detection and analysis."""
    from keanu.data.database import detect_schema, analyze_query, generate_model

    if args.detect:
        schema = detect_schema(args.root or ".")
        if schema.tables:
            print(f"\n  Schema: {len(schema.tables)} tables\n")
            for t in schema.tables:
                pk = ", ".join(t.primary_keys()) or "none"
                fk = len(t.foreign_keys())
                print(f"    {t.name} ({len(t.columns)} cols, pk: {pk}, {fk} fk)")
                for c in t.columns:
                    extras = []
                    if c.primary_key:
                        extras.append("PK")
                    if not c.nullable:
                        extras.append("NOT NULL")
                    if c.references:
                        extras.append(f"-> {c.references}")
                    extra_str = f" [{', '.join(extras)}]" if extras else ""
                    print(f"      {c.name}: {c.type}{extra_str}")
                print()
            if schema.source_files:
                print(f"  Sources: {', '.join(schema.source_files)}\n")
        else:
            print("\n  No schema detected.\n")
    elif args.analyze:
        analysis = analyze_query(args.analyze)
        print(f"\n  Query type: {analysis.query_type}")
        print(f"  Tables: {', '.join(analysis.tables)}")
        features = []
        if analysis.has_where:
            features.append("WHERE")
        if analysis.has_join:
            features.append("JOIN")
        if analysis.has_order_by:
            features.append("ORDER BY")
        if analysis.has_group_by:
            features.append("GROUP BY")
        if analysis.has_limit:
            features.append("LIMIT")
        if analysis.has_subquery:
            features.append("SUBQUERY")
        if features:
            print(f"  Features: {', '.join(features)}")
        if analysis.warnings:
            print(f"\n  Warnings:")
            for w in analysis.warnings:
                print(f"    !! {w}")
        print()
    elif args.generate:
        schema = detect_schema(args.root or ".")
        table = schema.get_table(args.generate)
        if table:
            code = generate_model(table, style=args.style)
            print(f"\n{code}")
        else:
            print(f"\n  Table '{args.generate}' not found.\n")
    else:
        print("  Usage: keanu db --detect")
        print("         keanu db --analyze 'SELECT * FROM users'")
        print("         keanu db --generate users")


def cmd_ci(args):
    """CI monitoring and test health."""
    from keanu.data.ci import run_tests, log_run, health_summary, get_history

    if args.run:
        print("\n  Running tests...")
        result = run_tests(args.target)
        log_run(result)
        status = "[green]" if result.green else "[red]"
        print(f"\n  {result.passed} passed, {result.failed} failed, {result.errors} errors ({result.duration_s:.1f}s)")
        if result.failures:
            print(f"\n  Failures:")
            for f in result.failures[:10]:
                print(f"    {f['test']}")
                if f['error']:
                    print(f"      {f['error'][:100]}")
        print()
    elif args.health:
        summary = health_summary()
        if summary["status"] == "no data":
            print("\n  No CI data. Run: keanu ci --run\n")
        else:
            print(f"\n  CI HEALTH: {summary['status'].upper()}")
            print(f"  {summary['runs']} runs, {summary['success_rate']:.0%} green, trend: {summary['trend']}")
            print(f"  avg: {summary['avg_tests']} tests in {summary['avg_duration_s']}s")
            if summary['top_failures']:
                print(f"\n  Top failures:")
                for f in summary['top_failures']:
                    print(f"    {f['test']} ({f['count']}x)")
            print()
    elif args.history_view:
        history = get_history(limit=args.limit)
        if history:
            print(f"\n  CI history ({len(history)} runs):\n")
            for h in history:
                status = "green" if h.get("failed", 0) == 0 else "RED"
                print(f"    [{status}] {h['passed']}p {h.get('failed', 0)}f {h.get('duration_s', 0):.1f}s  {h.get('commit', '')}")
        else:
            print("\n  No CI history.\n")
        print()
    else:
        print("  Usage: keanu ci --run [target]")
        print("         keanu ci --health")
        print("         keanu ci --history")


def cmd_security(args):
    """Security scanning: secrets, dependencies, audit."""
    from keanu.abilities.world.security import (
        scan_secrets, check_secrets_in_staged,
        check_gitignore_coverage, scan_dependencies,
        get_audit_log,
    )

    if args.audit:
        entries = get_audit_log(limit=args.limit)
        if entries:
            print(f"\n  Audit log ({len(entries)} entries):\n")
            for e in entries:
                print(f"    [{e['action']}] {e['result']} ({e.get('duration_ms', 0)}ms)")
        else:
            print("\n  No audit entries.\n")
    elif args.deps:
        vulns = scan_dependencies(args.root or ".")
        if vulns:
            print(f"\n  Vulnerabilities ({len(vulns)}):\n")
            for v in vulns:
                print(f"    [{v.severity}] {v.package} {v.installed_version}: {v.advisory}")
                if v.fix_version:
                    print(f"      fix: {v.fix_version}")
        else:
            print("\n  No known vulnerabilities found.\n")
    elif args.gitignore:
        unprotected = check_gitignore_coverage(args.root or ".")
        if unprotected:
            print(f"\n  Sensitive files NOT in .gitignore:\n")
            for f in unprotected:
                print(f"    !! {f}")
        else:
            print("\n  All sensitive files are gitignored.\n")
    elif args.staged:
        findings = check_secrets_in_staged()
        if findings:
            print(f"\n  Secrets in staged files ({len(findings)}):\n")
            for f in findings:
                print(f"    !! {f}")
        else:
            print("\n  No secrets in staged files.\n")
    else:
        findings = scan_secrets(args.root or ".")
        if findings:
            print(f"\n  Secrets found ({len(findings)}):\n")
            for f in findings:
                print(f"    [{f.category}] {f.file}:{f.line} {f.snippet[:60]}")
        else:
            print("\n  No secrets detected.\n")
    print()


def cmd_profile(args):
    """Profile code or benchmark functions."""
    from keanu.abilities.world.profile import profile_script, find_slow_functions

    if args.file:
        result = profile_script(args.file)
        if result.success:
            print(f"\n  Profile: {args.file}\n")
            for h in result.hotspots[:args.limit]:
                pct = (h.cum_time / result.total_time * 100) if result.total_time else 0
                print(f"    {h.function:<30} {h.cum_time:.4f}s  {h.calls:>6} calls  {pct:.0f}%")
            print(f"\n  Total: {result.total_time:.4f}s\n")
        else:
            print(f"\n  Error: {'; '.join(result.errors)}\n")
    elif args.slow:
        hotspots = find_slow_functions(args.slow, threshold_ms=args.threshold)
        if hotspots:
            print(f"\n  Slow functions in {args.slow} (>{args.threshold}ms):\n")
            for h in hotspots:
                print(f"    {h}")
        else:
            print(f"\n  No slow functions found (>{args.threshold}ms).\n")
    else:
        print("  Usage: keanu profile --file script.py")
        print("         keanu profile --slow module.py --threshold 50")


def cmd_corrections(args):
    """Show learned correction patterns and style preferences."""
    from keanu.abilities.world.corrections import load_corrections, correction_patterns, load_style_prefs

    if args.prefs:
        prefs = load_style_prefs()
        if prefs:
            print(f"\n  Learned style preferences:\n")
            for p in prefs:
                conf = f"{p.confidence:.0%}"
                print(f"    {p.rule:<24} {p.count}x  confidence: {conf}")
        else:
            print("\n  No style preferences learned yet.\n")
    else:
        patterns = correction_patterns(min_count=1)
        if patterns:
            print(f"\n  Correction patterns:\n")
            for pattern, count in sorted(patterns.items(), key=lambda x: -x[1]):
                print(f"    {pattern:<24} {count}x")
        else:
            print("\n  No corrections logged yet.\n")
    print()


def cmd_setup(args):
    from keanu.abilities.world.firstrun import check_setup, format_status, get_quickstart
    if args.quickstart:
        print(f"\n{get_quickstart()}\n")
        return
    status = check_setup()
    print(f"\n{format_status(status)}\n")


def cmd_ops(args):
    from keanu.abilities.world.ops import scan as ops_scan, get_ops_history
    if args.history:
        history = get_ops_history(limit=20)
        if not history:
            print("\n  No ops history yet.\n")
            return
        print(f"\n  Ops history (last {len(history)} scans):\n")
        from datetime import datetime, timezone
        for entry in reversed(history):
            ts = datetime.fromtimestamp(entry.get("timestamp", 0), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            issues = entry.get("issue_count", 0)
            critical = entry.get("critical", 0)
            print(f"    {ts}  {issues} issues ({critical} critical)")
        print()
        return
    checks = [c.strip() for c in args.checks.split(",") if c.strip()] if args.checks else None
    report = ops_scan(args.root, checks=checks)
    print(f"\n  Ops scan: {report.summary()}")
    print(f"  Checks run: {report.checks_run}, Duration: {report.duration_s:.1f}s\n")
    if report.issues:
        for issue in report.issues:
            severity = {"critical": "!", "warning": "~", "info": " "}.get(issue.severity, " ")
            fix = " (auto-fixable)" if issue.auto_fixable else ""
            print(f"    [{severity}] {issue.category}: {issue.message}{fix}")
        print()


def cmd_rag(args):
    from keanu.data.rag import build_index, incremental_index, search, get_index_stats
    if args.index:
        print(f"\n  Building RAG index for {args.root}...")
        stats = build_index(args.root)
        print(f"  Indexed {stats.total_files} files, {stats.total_chunks} chunks\n")
        return
    if args.update:
        print(f"\n  Updating RAG index for {args.root}...")
        stats = incremental_index(args.root)
        print(f"  Updated: {stats.total_files} files, {stats.total_chunks} new chunks\n")
        return
    if args.search:
        results = search(args.search, args.root, n_results=args.n)
        if not results:
            print("\n  No results. Build the index first: keanu rag --index\n")
            return
        print(f"\n  {len(results)} results for '{args.search}':\n")
        for r in results:
            print(f"    [{r.score:.2f}] {r.chunk.file_path}:{r.chunk.start_line}-{r.chunk.end_line} ({r.source})")
            preview = r.chunk.content[:100].replace("\n", " ")
            print(f"           {preview}")
        print()
        return
    if args.stats:
        stats = get_index_stats()
        if stats.total_files == 0:
            print("\n  No index built. Run: keanu rag --index\n")
            return
        from datetime import datetime, timezone
        ts = datetime.fromtimestamp(stats.indexed_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        print(f"\n  RAG Index Stats:")
        print(f"    Root: {stats.root}")
        print(f"    Files: {stats.total_files}")
        print(f"    Chunks: {stats.total_chunks}")
        print(f"    Indexed: {ts}\n")
        return
    print("  Usage: keanu rag --index | --update | --search 'query' | --stats")


def cmd_forge(args):
    if args.misses:
        from keanu.abilities.forge import suggest_from_misses
        from keanu.abilities.miss_tracker import get_misses
        misses = get_misses(limit=50)
        if not misses:
            print("\n  No router misses recorded yet.\n")
            return
        suggestions = suggest_from_misses(limit=50)
        print(f"\n  Router misses (last {len(misses)}):\n")
        for s in suggestions[:10]:
            print(f"    {s['count']:>3}x  \"{s['word']}\" ({s['pct']}%)")
        print()
        return
    if not args.name:
        print("Usage: keanu forge <name> --desc '...' --keywords 'a,b,c'")
        return
    from keanu.abilities.forge import forge_ability
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()] if args.keywords else [args.name]
    result = forge_ability(args.name, args.desc or args.name, keywords)
    if "error" in result:
        print(f"\n  Error: {result['error']}\n")
        return
    print(f"\n  Created:")
    print(f"    {result['ability_file']}")
    print(f"    {result['test_file']}")
    print(f"\n  Next: fill in execute(), add import to abilities/__init__.py, run tests.\n")


def cmd_todo(args):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "todo", Path(__file__).resolve().parents[2] / "scripts" / "todo.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.generate_todo(args.project or ".")


from keanu.paths import COEF_DIR


def _coef_setup():
    """set up DNS + registry for COEF operations."""
    from keanu.abilities.world.compress.dns import ContentDNS
    from keanu.abilities.world.compress.codec import PatternRegistry
    from keanu.abilities.world.compress.exporter import register_span_patterns
    dns_dir = COEF_DIR / "dns"
    patterns_dir = COEF_DIR / "patterns"
    dns_dir.mkdir(parents=True, exist_ok=True)
    dns = ContentDNS(storage_dir=str(dns_dir))
    registry = PatternRegistry(storage_dir=str(patterns_dir))
    register_span_patterns(registry)
    return dns, registry


def _bootstrap_coef_tracing():
    from keanu.abilities.world.compress.exporter import COEFSpanExporter
    from keanu.log import add_exporter
    dns, registry = _coef_setup()
    exporter = COEFSpanExporter(dns=dns, registry=registry)
    add_exporter(exporter)


def cmd_decode(args):
    from keanu.abilities.world.compress.codec import COEFDecoder, Seed
    dns, registry = _coef_setup()
    decoder = COEFDecoder(registry)

    if args.ref:
        try:
            content = dns.resolve(args.ref)
            if content.startswith("COEF::"):
                seed = Seed.from_compact(content)
                result = decoder.decode(seed)
                if args.raw:
                    print(content)
                else:
                    print(f"\n  Pattern: {seed.pattern_id}")
                    print(f"  Hash:    {seed.content_hash[:16]}")
                    print(f"  Lossless: {result.is_lossless}")
                    print(f"\n  {result.content}\n")
            else:
                print(content)
        except KeyError:
            print(f"  Not found: {args.ref}")

    elif args.last:
        names = dns.names()
        seed_names = {n: h for n, h in names.items() if n.startswith("seed:")}
        recent = list(seed_names.items())[-args.last:]
        if not recent:
            print("  No seeds found.")
            return
        print(f"\n  Last {len(recent)} seeds:\n")
        for name, h in recent:
            try:
                content = dns.resolve(name)
                if content.startswith("COEF::"):
                    seed = Seed.from_compact(content)
                    result = decoder.decode(seed)
                    if args.raw:
                        print(f"  {content}")
                    else:
                        print(f"  [{seed.pattern_id}] {result.content[:120]}")
                        print(f"    hash: {h[:16]}  lossless: {result.is_lossless}")
                else:
                    print(f"  [{name}] {content[:120]}")
            except Exception as e:
                print(f"  [{name}] (error: {e})")
        print()

    elif args.subsystem:
        names = dns.names()
        prefix = f"span:keanu.{args.subsystem}"
        matches = {n: h for n, h in names.items() if n.startswith(prefix)}
        if not matches:
            print(f"  No spans for '{args.subsystem}'")
            return
        print(f"\n  {len(matches)} spans for {args.subsystem}:\n")
        for name, h in matches.items():
            try:
                print(f"  {dns.resolve(name)[:140]}")
            except Exception:
                print(f"  [{name}] (unresolvable)")
        print()

    else:
        names = dns.names()
        seed_count = sum(1 for n in names if n.startswith("seed:"))
        print(f"\n  {seed_count} seeds stored. Use --last N or provide a hash/name.\n")


# ============================================================
# PARSER
# ============================================================

def _ensure_vectors():
    """auto-bake chromadb vectors if missing."""
    try:
        from keanu.wellspring import depths
        chroma_dir = depths()
        need_bake = False
        if not Path(chroma_dir).exists():
            need_bake = True
        else:
            try:
                import chromadb
                client = chromadb.PersistentClient(path=chroma_dir)
                client.get_collection("silverado")
                client.get_collection("silverado_rgb")
            except Exception:
                need_bake = True
        if need_bake:
            info("cli", "vectors missing. baking...")
            from keanu.abilities.seeing.scan.bake import bake
            bake()
            info("cli", "vectors baked.")
    except Exception as e:
        warn("cli", f"auto-bake failed: {e}")


def _build_parsers(subparsers):
    """register all subcommands."""
    from keanu.abilities.seeing.detect import DETECTORS
    from keanu.memory.memberberry import MemoryType

    # -- hero --
    p = subparsers.add_parser("do", help="Agent loop (--craft for code, --prove for evidence)")
    p.add_argument("task", help="Task to accomplish")
    p.add_argument("--craft", action="store_true", help="Code agent (hands only)")
    p.add_argument("--prove", action="store_true", help="Evidence agent")
    _add_agent_args(p, max_turns=0)
    p.set_defaults(func=cmd_do)

    p = subparsers.add_parser("ask", help="Convergence loop (duality synthesis)")
    p.add_argument("question", help="Question to explore")
    _add_legend_args(p)
    p.add_argument("--workers", "-w", type=int, default=3, help="Parallel workers")
    p.add_argument("--no-memory", action="store_true")
    p.add_argument("--rag", action="store_true", help="Augment with RAG context from ingested docs")
    p.add_argument("--web", action="store_true", help="Include web search results (requires --rag)")
    p.set_defaults(func=cmd_ask)

    # keep 'agent' as hidden alias
    p = subparsers.add_parser("agent")
    p.add_argument("question", help="Question to explore")
    _add_legend_args(p)
    p.add_argument("--workers", "-w", type=int, default=3)
    p.add_argument("--no-memory", action="store_true")
    p.set_defaults(func=cmd_ask)

    p = subparsers.add_parser("dream", help="Plan: phases + steps + dependencies")
    p.add_argument("goal", help="What to plan for")
    p.add_argument("--context", default="", help="Extra context")
    _add_legend_args(p)
    p.set_defaults(func=cmd_dream)

    p = subparsers.add_parser("speak", help="Translate content for an audience")
    p.add_argument("content", nargs="?", default="", help="Content to translate")
    p.add_argument("--file", "-f", default="", help="Read from file")
    p.add_argument("--audience", "-a", default="friend")
    _add_legend_args(p)
    p.set_defaults(func=cmd_speak)

    # -- RAG --
    p = subparsers.add_parser("ingest", help="Ingest files into RAG vector store")
    p.add_argument("paths", nargs="+", help="Files or directories to ingest")
    p.add_argument("--collection", "-c", default="", help="Collection name (default: keanu_rag)")
    p.set_defaults(func=cmd_ingest)

    p = subparsers.add_parser("search", help="Search the web")
    p.add_argument("query", help="Search query")
    p.add_argument("--limit", "-n", type=int, default=5, help="Number of results")
    p.set_defaults(func=cmd_search)

    # -- coding tools --
    p = subparsers.add_parser("git", help="Git operations")
    p.add_argument("op", choices=["status", "diff", "log", "blame", "branch", "stash", "add", "commit", "show"],
                   default="status", nargs="?")
    p.add_argument("--file", default="", help="File for diff/blame")
    p.add_argument("-n", type=int, default=0, help="Number of log entries")
    p.add_argument("--name", default="", help="Branch name")
    p.add_argument("--message", default="", help="Commit message")
    p.add_argument("--staged", action="store_true", help="Show staged diff")
    p.add_argument("--sub", default="", help="Sub-operation (list/create/switch for branch, save/pop/list for stash)")
    p.add_argument("--files", nargs="*", default=[], help="Files to stage")
    p.set_defaults(func=cmd_git)

    p = subparsers.add_parser("test", help="Run tests")
    p.add_argument("op", choices=["run", "discover", "targeted", "coverage"],
                   default="run", nargs="?")
    p.add_argument("--target", "-t", default="", help="Specific test file or test")
    p.add_argument("--files", nargs="*", default=[], help="Source files for targeted testing")
    p.set_defaults(func=cmd_test)

    # -- analysis --
    p = subparsers.add_parser("scan", help="Three-primary reading")
    p.add_argument("files", nargs="+")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_scan)

    p = subparsers.add_parser("bake", help="Train lenses from examples")
    p.add_argument("--lenses")
    p.set_defaults(func=cmd_bake)

    p = subparsers.add_parser("converge", help="Six lens convergence")
    p.add_argument("question")
    _add_legend_args(p)
    p.set_defaults(func=cmd_converge)

    p = subparsers.add_parser("connect", help="Cross-source alignment")
    p.add_argument("source_a")
    p.add_argument("source_b")
    p.set_defaults(func=cmd_connect)

    p = subparsers.add_parser("compress", help="COEF compression")
    p.add_argument("file")
    p.set_defaults(func=cmd_compress)

    p = subparsers.add_parser("detect", help="Pattern detector")
    p.add_argument("detector", choices=DETECTORS + ["all"])
    p.add_argument("file")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_detect)

    p = subparsers.add_parser("alive", help="ALIVE-GREY-BLACK diagnostic")
    p.add_argument("text", nargs="?", default="")
    p.add_argument("--file", "-f", default="")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_alive)

    # -- memory (subcommand group) --
    valid_types = [e.value for e in MemoryType]

    mem = subparsers.add_parser("memory", aliases=["mem"], help="Memory commands")
    mem_sub = mem.add_subparsers(dest="memory_command")

    p = mem_sub.add_parser("remember", help="Store a memory")
    p.add_argument("type", choices=valid_types)
    p.add_argument("content")
    p.add_argument("--tags", default="")
    p.add_argument("--importance", type=int, default=5)
    p.set_defaults(func=cmd_memory_remember)

    p = mem_sub.add_parser("recall", help="Search memories")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--type", default=None)
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_memory_recall)

    p = mem_sub.add_parser("plan", help="Generate or list plans")
    p.add_argument("focus", nargs="?", default="")
    p.add_argument("--list", action="store_true", help="List existing plans")
    p.add_argument("--status", default=None, choices=["draft", "active", "blocked", "done", "dropped"])
    p.add_argument("--tags", default="")
    p.add_argument("--days", type=int, default=14)
    p.set_defaults(func=cmd_memory_plan)

    p = mem_sub.add_parser("log", help="Recent log entries")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_memory_log)

    p = mem_sub.add_parser("stats", help="Memory stats")
    p.add_argument("--shared", action="store_true")
    p.set_defaults(func=cmd_memory_stats)

    p = mem_sub.add_parser("sync", help="Pull shared memories from git")
    p.set_defaults(func=cmd_memory_sync)

    p = mem_sub.add_parser("disagree", help="Track disagreements")
    p.add_argument("action", choices=["record", "resolve", "stats", "list"])
    p.add_argument("--topic", default="")
    p.add_argument("--human", default="")
    p.add_argument("--ai", default="")
    p.add_argument("--id", default="")
    p.add_argument("--winner", default="", choices=["human", "ai", "compromise", ""])
    p.add_argument("--resolved-by", default="")
    p.add_argument("--shared", action="store_true")
    p.set_defaults(func=cmd_memory_disagree)

    # -- top-level shortcuts for memory --
    p = subparsers.add_parser("remember", aliases=["r"], help="Store a memory (shortcut)")
    p.add_argument("type", choices=valid_types)
    p.add_argument("content")
    p.add_argument("--tags", default="")
    p.add_argument("--importance", type=int, default=5)
    p.set_defaults(func=cmd_memory_remember)

    p = subparsers.add_parser("recall", aliases=["q"], help="Recall memories (shortcut)")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--type", default=None)
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_memory_recall)

    # -- system --
    p = subparsers.add_parser("healthz", aliases=["health"], help="System health dashboard")
    p.add_argument("--shared", action="store_true")
    p.set_defaults(func=cmd_health)

    p = subparsers.add_parser("decode", help="Decode COEF seeds")
    p.add_argument("ref", nargs="?", default="")
    p.add_argument("--last", type=int, default=0)
    p.add_argument("--subsystem", default="")
    p.add_argument("--raw", action="store_true")
    p.set_defaults(func=cmd_decode)

    p = subparsers.add_parser("todo", help="Generate TODO.md")
    p.add_argument("--project")
    p.set_defaults(func=cmd_todo)

    p = subparsers.add_parser("abilities", help="List registered abilities")
    p.set_defaults(func=cmd_abilities)

    p = subparsers.add_parser("metrics", help="Convergence metrics dashboard")
    p.add_argument("--days", "-d", type=int, default=7, help="Time window in days")
    p.set_defaults(func=cmd_metrics)

    p = subparsers.add_parser("mistakes", help="Mistake patterns and stats")
    p.add_argument("--clear", action="store_true", help="Clear stale mistakes")
    p.set_defaults(func=cmd_mistakes)

    p = subparsers.add_parser("lint", help="Run project linter")
    p.add_argument("--path", default="", help="Path to lint (default: cwd)")
    p.add_argument("--fix", action="store_true", help="Auto-fix issues")
    p.set_defaults(func=cmd_lint)

    p = subparsers.add_parser("format", aliases=["fmt"], help="Run project formatter")
    p.add_argument("--path", default="", help="Path to format (default: cwd)")
    p.add_argument("--check", action="store_true", help="Check only, don't modify")
    p.set_defaults(func=cmd_format)

    p = subparsers.add_parser("review", help="Review code for issues")
    p.add_argument("--file", default="", help="Review a specific file")
    p.add_argument("--staged", action="store_true", help="Review staged changes")
    p.set_defaults(func=cmd_review)

    p = subparsers.add_parser("symbols", aliases=["sym"], help="Find symbol definitions/references")
    p.add_argument("name", nargs="?", default="", help="Symbol name to find")
    p.add_argument("--root", default="", help="Project root (default: cwd)")
    p.add_argument("--refs", action="store_true", help="Find references instead of definitions")
    p.add_argument("--callers", action="store_true", help="Find callers of a function")
    p.add_argument("--list", dest="list_file", default="", help="List all symbols in a file")
    p.set_defaults(func=cmd_symbols)

    p = subparsers.add_parser("deps", help="Dependency graph stats")
    p.add_argument("--root", default="", help="Project root (default: cwd)")
    p.add_argument("--who", default="", help="Who imports this file?")
    p.set_defaults(func=cmd_deps)

    p = subparsers.add_parser("suggest", help="Proactive code suggestions")
    p.add_argument("--file", default="", help="Scan a specific file")
    p.add_argument("--root", default="", help="Project root for directory scan")
    p.add_argument("--missing-tests", action="store_true", help="Check for missing test files")
    p.set_defaults(func=cmd_suggest)

    p = subparsers.add_parser("gen", aliases=["generate"], help="Code generation")
    p.add_argument("--template", "-t", default="", choices=["ability", "test", "module", "cli_command", ""],
                   help="Template to scaffold")
    p.add_argument("--name", default="", help="Name for scaffold")
    p.add_argument("--desc", default="", help="Description")
    p.add_argument("--keywords", default="", help="Keywords (comma-separated)")
    p.add_argument("--tests-for", default="", help="Generate tests for a file")
    p.add_argument("--stubs-in", default="", help="Find stubs/TODOs in a file")
    p.add_argument("--output", "-o", default="", help="Output file")
    p.set_defaults(func=cmd_codegen)

    p = subparsers.add_parser("mcp", help="Run as MCP server over stdio")
    p.set_defaults(func=cmd_mcp)

    p = subparsers.add_parser("corrections", help="Show learned correction patterns")
    p.add_argument("--prefs", action="store_true", help="Show style preferences")
    p.set_defaults(func=cmd_corrections)

    p = subparsers.add_parser("db", aliases=["database"], help="Database schema detection and analysis")
    p.add_argument("--detect", action="store_true", help="Auto-detect schema from project files")
    p.add_argument("--analyze", default="", help="Analyze a SQL query")
    p.add_argument("--generate", default="", help="Generate Python model from table")
    p.add_argument("--root", default="", help="Project root")
    p.add_argument("--style", default="dataclass", choices=["dataclass", "sqlalchemy"])
    p.set_defaults(func=cmd_database)

    p = subparsers.add_parser("ci", help="CI monitoring and test health")
    p.add_argument("--run", action="store_true", help="Run tests and log results")
    p.add_argument("--target", default="", help="Specific test target")
    p.add_argument("--health", action="store_true", help="Show test health summary")
    p.add_argument("--history", dest="history_view", action="store_true", help="Show CI history")
    p.add_argument("--limit", type=int, default=20, help="Limit results")
    p.set_defaults(func=cmd_ci)

    p = subparsers.add_parser("security", aliases=["sec"], help="Security scanning")
    p.add_argument("--root", default="", help="Project root to scan")
    p.add_argument("--staged", action="store_true", help="Check staged files for secrets")
    p.add_argument("--deps", action="store_true", help="Scan dependencies for vulnerabilities")
    p.add_argument("--gitignore", action="store_true", help="Check gitignore coverage")
    p.add_argument("--audit", action="store_true", help="Show audit log")
    p.add_argument("--limit", type=int, default=20, help="Limit results")
    p.set_defaults(func=cmd_security)

    p = subparsers.add_parser("profile", aliases=["prof"], help="Profile and benchmark code")
    p.add_argument("--file", default="", help="Profile a Python script")
    p.add_argument("--slow", default="", help="Find slow functions in a file")
    p.add_argument("--threshold", type=float, default=10.0, help="Threshold in ms for slow functions")
    p.add_argument("--limit", type=int, default=20, help="Max hotspots to show")
    p.set_defaults(func=cmd_profile)

    p = subparsers.add_parser("doc", aliases=["docgen"], help="Generate documentation from code")
    p.add_argument("--docstrings", default="", help="Generate docstrings for a file")
    p.add_argument("--class-diagram", default="", help="Generate mermaid class diagram")
    p.add_argument("--changelog", action="store_true", help="Generate changelog from git history")
    p.add_argument("--api", default="", help="Generate API summary for a file")
    p.add_argument("--style", default="google", choices=["google", "numpy", "terse"])
    p.add_argument("--write", "-w", action="store_true", help="Write docstrings back to file")
    p.add_argument("-n", type=int, default=20, help="Number of commits for changelog")
    p.set_defaults(func=cmd_docgen)

    p = subparsers.add_parser("auto-forge", aliases=["af"], help="Auto-forge pipeline")
    p.add_argument("--health", action="store_true", help="Check project health")
    p.add_argument("--history", action="store_true", help="Show forge history")
    p.add_argument("--run", action="store_true", help="Actually forge (not just dry run)")
    p.add_argument("--min-count", type=int, default=5, help="Min miss count to forge")
    p.add_argument("--root", default="", help="Project root for health check")
    p.set_defaults(func=cmd_auto_forge)

    p = subparsers.add_parser("setup", help="First-run setup and status")
    p.add_argument("--quickstart", action="store_true", help="Show quickstart guide")
    p.set_defaults(func=cmd_setup)

    p = subparsers.add_parser("ops", help="Proactive ops monitoring")
    p.add_argument("--root", default=".", help="Project root to scan")
    p.add_argument("--checks", default="", help="Comma-separated checks: deps,tests,docs,code,git")
    p.add_argument("--history", action="store_true", help="Show ops history")
    p.set_defaults(func=cmd_ops)

    p = subparsers.add_parser("rag", help="Codebase RAG index and search")
    p.add_argument("--index", action="store_true", help="Build/rebuild full index")
    p.add_argument("--update", action="store_true", help="Incremental index update")
    p.add_argument("--search", default="", help="Search the index")
    p.add_argument("--stats", action="store_true", help="Show index stats")
    p.add_argument("--root", default=".", help="Project root")
    p.add_argument("-n", type=int, default=5, help="Number of results")
    p.set_defaults(func=cmd_rag)

    p = subparsers.add_parser("forge", help="Scaffold ability or show misses")
    p.add_argument("name", nargs="?", default="")
    p.add_argument("--desc", default="")
    p.add_argument("--keywords", default="")
    p.add_argument("--misses", action="store_true")
    p.set_defaults(func=cmd_forge)


def main():
    parser = argparse.ArgumentParser(
        prog="keanu",
        description="Scans through three color lenses, compresses what matters, finds truth.",
    )
    subparsers = parser.add_subparsers(dest="command")
    _build_parsers(subparsers)

    args = parser.parse_args()

    if not args.command:
        _ensure_vectors()
        from keanu.hero.repl import run_repl
        run_repl()
        return

    # memory subcommand group needs its own check
    if args.command in ("memory", "mem") and not getattr(args, 'memory_command', None):
        parser.parse_args(["memory", "--help"])
        return

    _ensure_vectors()

    try:
        _bootstrap_coef_tracing()
    except Exception:
        pass

    try:
        from keanu.memory import GitStore
        from keanu.log import set_sink
        ledger = GitStore(namespace="keanu")
        set_sink(ledger.append_log, flush_fn=ledger.flush)
        atexit.register(ledger.flush)
    except Exception:
        pass

    args.func(args)
    _stamp()


def _stamp():
    """print the keanu stamp after every command."""
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n  🤖💚🐕 keanu | github.com/AnywhereOps/keanu | {ts}")


if __name__ == "__main__":
    main()
