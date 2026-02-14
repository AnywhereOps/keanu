"""keanu CLI: unified entry point.

Usage:
    keanu scan document.md          # three-primary reading
    keanu bake                      # train lenses from examples
    keanu converge "question"       # duality synthesis
    keanu connect a.md b.md         # cross-source alignment
    keanu compress module.py        # COEF compression
    keanu signal "emoji-string"     # decode signal
    keanu alive "text to check"     # ALIVE-GREY-BLACK diagnostic
    keanu detect sycophancy file.md # pattern detector
    keanu remember goal "ship v1"   # store a memory
    keanu recall "what am I building" # recall relevant memories
    keanu plan "next week"          # generate plan from memories
    keanu fill interactive          # guided memory ingestion
    keanu sync                      # pull shared memories from git
    keanu disagree record --topic "x" --human "y" --ai "z"  # track disagreement
    keanu disagree stats            # bilateral accountability metrics
    keanu healthz                    # system health dashboard
    keanu todo                      # generate effort-aware TODO.md
"""

import argparse
import sys
from pathlib import Path


def cmd_scan(args):
    """Scan a document through three color lenses."""
    from keanu.scan.helix import run
    for filepath in args.files:
        run(filepath, output_json=args.json)


def cmd_bake(args):
    """Train lenses from examples into chromadb."""
    from keanu.scan.bake import bake
    lenses = args.lenses if args.lenses else None
    bake(lenses)


def cmd_converge(args):
    """Run duality convergence on a question."""
    from keanu.converge.engine import run
    run(args.question, backend=args.backend, model=args.model)


def cmd_connect(args):
    """Align two sources via helix scanning."""
    from keanu.converge.connection import run
    run(args.source_a, args.source_b)


def cmd_compress(args):
    """COEF compression of a module."""
    from keanu.compress.dns import ContentDNS
    store = ContentDNS()
    with open(args.file) as f:
        content = f.read()
    h = store.store(content)
    print(f"Stored: {h[:16]}")


def cmd_signal(args):
    """Decode an emoji signal string."""
    from keanu.signal import from_sequence, read_emotion
    sig = from_sequence(args.signal)
    reading = sig.reading()
    print(f"  Sequence:  {reading['ch1_said']}")
    print(f"  Feeling:   {reading['ch2_feeling']}")
    print(f"  Meaning:   {reading['ch3_meaning']}")
    print(f"  ALIVE:     {reading['alive']} (ok: {reading['alive_ok']})")
    subsets = sig.matched_subsets()
    if subsets:
        print(f"  Subsets:   {', '.join(f'{k} = {v}' for k, v in subsets)}")


def cmd_detect(args):
    """Run a pattern detector on a file."""
    from keanu.detect.engine import run
    from keanu.detect import DETECTORS
    if args.detector == "all":
        for d in DETECTORS:
            run(args.file, d, title=d.upper().replace("_", " ") + " SCAN",
                output_json=args.json)
    else:
        run(args.file, args.detector,
            title=args.detector.upper().replace("_", " ") + " SCAN",
            output_json=args.json)


def cmd_alive(args):
    """ALIVE-GREY-BLACK diagnostic. Text in, state out."""
    from keanu.alive import diagnose
    if args.text:
        text = args.text
    elif args.file:
        with open(args.file) as f:
            text = f.read()
    else:
        import sys
        text = sys.stdin.read()

    reading = diagnose(text)
    print()
    print(reading.summary())
    print()


def _get_store(shared=False):
    if shared:
        from keanu.memory import GitStore
        return GitStore()
    from keanu.memory import MemberberryStore
    return MemberberryStore()


def cmd_remember(args):
    """Store a memory."""
    from keanu.memory import Memory
    store = _get_store(args.shared)
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    memory = Memory(
        content=args.content,
        memory_type=args.type,
        tags=tags,
        importance=args.importance,
        context=args.context or "",
        source="cli",
    )
    mid = store.remember(memory)
    print(f"  Remembered [{args.type}] {args.content}")
    print(f"  id: {mid} | importance: {args.importance} | tags: {', '.join(tags) or 'none'}")


def cmd_recall(args):
    """Recall relevant memories."""
    store = _get_store(args.shared)
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
    results = store.recall(
        query=args.query or "",
        tags=tags,
        memory_type=args.type,
        limit=args.limit,
    )
    if not results:
        print("  No memories found.")
        return
    print(f"\n  Recalled {len(results)} memories:\n")
    for m in results:
        score = m.get("_relevance_score", 0)
        tags_str = ", ".join(m.get("tags", []))
        print(f"  [{m['memory_type'][:4].upper()}] {m['content']}")
        print(f"    score: {score} | importance: {m.get('importance', '?')} | tags: {tags_str or 'none'} | id: {m['id']}")
        if m.get("context"):
            print(f"    context: {m['context']}")
        print()


def cmd_plan(args):
    """Generate a plan from memories."""
    from keanu.memory import MemberberryStore, PlanGenerator
    store = MemberberryStore()
    planner = PlanGenerator(store)
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
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


def cmd_plans(args):
    """List plans."""
    from keanu.memory import MemberberryStore
    store = MemberberryStore()
    plans = store.get_plans(status=args.status)
    if not plans:
        print("  No plans found.")
        return
    print(f"\n  {len(plans)} plan(s):\n")
    for p in plans:
        action_count = len(p.get("actions", []))
        print(f"  [{p['status'].upper()}] {p['title']}")
        print(f"    {action_count} actions | target: {p.get('target_date', '?')[:10]} | id: {p['id']}")
        print()


def cmd_deprioritize(args):
    """Lower a memory's importance. Nothing is ever deleted."""
    store = _get_store(args.shared)
    if store.deprioritize(args.memory_id):
        print(f"  Deprioritized {args.memory_id} (importance -> 1)")
    else:
        print(f"  Memory {args.memory_id} not found")


def cmd_sync(args):
    """Pull latest shared memories from git."""
    from keanu.memory import GitStore
    store = GitStore()
    store.sync()
    s = store.stats()
    print(f"  Synced. {s['shared_memories']} shared memories across {len(s['namespaces'])} namespaces.")


def cmd_stats(args):
    """Show memory stats."""
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


def cmd_fill(args):
    """Bulk memory ingestion."""
    from keanu.memory.fill_berries import interactive, bulk_import, parse_markdown, generate_template
    mode = args.mode
    if mode == "interactive":
        interactive()
    elif mode == "bulk":
        if not args.file:
            print("Usage: keanu fill bulk <file.jsonl>")
            return
        bulk_import(args.file)
    elif mode == "parse":
        if not args.file:
            print("Usage: keanu fill parse <file.md>")
            return
        parse_markdown(args.file)
    elif mode == "template":
        generate_template(
            person=args.person or "",
            project=args.project or "",
            archetype=args.archetype or "",
        )


def cmd_disagree(args):
    """Record or resolve a disagreement. Both sides get vectors."""
    from keanu.memory import DisagreementTracker
    store = _get_store(args.shared)
    tracker = DisagreementTracker(store)

    if args.action == "record":
        if not args.topic or not args.human or not args.ai:
            print("Usage: keanu disagree record --topic 'x' --human 'y' --ai 'z'")
            return
        d = tracker.record(args.topic, args.human, args.ai)
        print(f"  Recorded disagreement: {d.topic}")
        print(f"  id: {d.id}")
        if d.human_reading:
            print(f"  Human emotional reads: {', '.join(r['state'] for r in d.human_reading)}")
        if d.ai_reading:
            print(f"  AI emotional reads: {', '.join(r['state'] for r in d.ai_reading)}")

    elif args.action == "resolve":
        if not args.id or not args.winner:
            print("Usage: keanu disagree resolve --id <id> --winner human|ai|compromise")
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
            print()
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


def cmd_health(args):
    """System health dashboard. One command, full picture."""
    from keanu.memory import MemberberryStore, DisagreementTracker

    store = _get_store(args.shared)
    tracker = DisagreementTracker(store)

    print("\n  ╔══════════════════════════════════════╗")
    print("  ║          keanu health                ║")
    print("  ╚══════════════════════════════════════╝\n")

    # -- Memory health --
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

    # -- Disagreement health --
    ds = tracker.stats()
    print(f"  DISAGREEMENT")
    print(f"    total:     {ds['total']}")
    if ds["total"] > 0:
        print(f"    resolved:  {ds.get('resolved', 0)}")
        print(f"    open:      {ds.get('unresolved', 0)}")
    if ds["alerts"]:
        for alert in ds["alerts"]:
            print(f"    !! {alert}")
    elif ds["total"] == 0 and total > 20:
        print(f"    !! No disagreements recorded in {total} memories. Watch for sycophancy.")
    elif ds["total"] == 0:
        print(f"    (no disagreements yet - that's fine early on)")
    print()

    # -- Module status --
    print(f"  MODULES")
    modules = {
        "scan/helix":     ("keanu.scan.helix", "needs chromadb"),
        "detect/mood":    ("keanu.detect.mood", "color theory"),
        "detect/engine":  ("keanu.detect.engine", "pattern vectors"),
        "compress/dns":   ("keanu.compress.dns", "content-addressable"),
        "converge":       ("keanu.converge.engine", "duality synthesis"),
        "signal":         ("keanu.signal", "emoji codec"),
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

    # -- External deps --
    print(f"  EXTERNAL DEPS")
    externals = {
        "chromadb":  "vector storage (scan, detect)",
        "requests":  "LLM API calls (converge)",
    }
    for dep, purpose in externals.items():
        try:
            __import__(dep)
            print(f"    {dep:<14} installed     {purpose}")
        except ImportError:
            print(f"    {dep:<14} not installed {purpose}")
    print()

    # -- Signal check --
    try:
        from keanu.signal import core, AliveState
        sig = core()
        reading = sig.reading()
        alive = reading.get("alive", "unknown")
        alive_ok = reading.get("alive_ok", False)
        state = "ALIVE" if alive_ok else "CHECK"
        print(f"  SIGNAL")
        print(f"    core:      {reading.get('ch1_said', '?')}")
        print(f"    state:     {alive} ({state})")
    except Exception:
        print(f"  SIGNAL")
        print(f"    (could not read core signal)")
    print()


def cmd_todo(args):
    """Generate effort-aware TODO.md."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "todo", Path(__file__).resolve().parents[2] / "scripts" / "todo.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.generate_todo(args.project or ".")


def main():
    parser = argparse.ArgumentParser(
        prog="keanu",
        description="Scans through three color lenses, compresses what matters, finds truth.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # scan
    p_scan = subparsers.add_parser("scan", help="Three-primary reading of a document")
    p_scan.add_argument("files", nargs="+", help="Files to scan")
    p_scan.add_argument("--json", action="store_true", help="Output as JSON")
    p_scan.set_defaults(func=cmd_scan)

    # bake
    p_bake = subparsers.add_parser("bake", help="Train lenses from examples")
    p_bake.add_argument("--lenses", help="Path to lens examples file")
    p_bake.set_defaults(func=cmd_bake)

    # converge
    p_converge = subparsers.add_parser("converge", help="Duality convergence on a question")
    p_converge.add_argument("question", help="Question to converge on")
    p_converge.add_argument("--backend", "-b", choices=["ollama", "claude"], default="ollama", help="LLM backend")
    p_converge.add_argument("--model", "-m", default=None, help="Model name")
    p_converge.set_defaults(func=cmd_converge)

    # connect
    p_connect = subparsers.add_parser("connect", help="Cross-source alignment")
    p_connect.add_argument("source_a", help="First source file")
    p_connect.add_argument("source_b", help="Second source file")
    p_connect.set_defaults(func=cmd_connect)

    # compress
    p_compress = subparsers.add_parser("compress", help="COEF compression")
    p_compress.add_argument("file", help="File to compress")
    p_compress.set_defaults(func=cmd_compress)

    # signal
    p_signal = subparsers.add_parser("signal", help="Decode emoji signal")
    p_signal.add_argument("signal", help="Emoji signal string")
    p_signal.set_defaults(func=cmd_signal)

    # detect
    from keanu.detect import DETECTORS
    p_detect = subparsers.add_parser("detect", help="Run pattern detector on a file")
    p_detect.add_argument("detector", choices=DETECTORS + ["all"],
                          help="Which detector to run")
    p_detect.add_argument("file", help="File to scan (or - for stdin)")
    p_detect.add_argument("--json", action="store_true", help="Output as JSON")
    p_detect.set_defaults(func=cmd_detect)

    # alive
    p_alive = subparsers.add_parser("alive", help="ALIVE-GREY-BLACK diagnostic")
    p_alive.add_argument("text", nargs="?", default="", help="Text to diagnose")
    p_alive.add_argument("--file", "-f", default="", help="File to diagnose")
    p_alive.set_defaults(func=cmd_alive)

    # remember
    from keanu.memory.memberberry import MemoryType
    valid_types = [e.value for e in MemoryType]
    p_remember = subparsers.add_parser("remember", aliases=["r"], help="Store a memory")
    p_remember.add_argument("type", choices=valid_types, help="Memory type")
    p_remember.add_argument("content", help="What to remember")
    p_remember.add_argument("--tags", default="", help="Comma-separated tags")
    p_remember.add_argument("--importance", type=int, default=5, help="1-10 scale")
    p_remember.add_argument("--context", default="", help="Situational context")
    p_remember.add_argument("--shared", action="store_true", help="Store in shared git repo")
    p_remember.set_defaults(func=cmd_remember)

    # recall
    p_recall = subparsers.add_parser("recall", aliases=["q"], help="Recall relevant memories")
    p_recall.add_argument("query", nargs="?", default="", help="Search query")
    p_recall.add_argument("--tags", default="", help="Comma-separated tag filter")
    p_recall.add_argument("--type", default=None, help="Filter by memory type")
    p_recall.add_argument("--limit", type=int, default=10, help="Max results")
    p_recall.add_argument("--shared", action="store_true", help="Search shared git repo")
    p_recall.set_defaults(func=cmd_recall)

    # plan
    p_plan = subparsers.add_parser("plan", aliases=["p"], help="Generate plan from memories")
    p_plan.add_argument("focus", help="What to plan for")
    p_plan.add_argument("--tags", default="", help="Comma-separated tag filter")
    p_plan.add_argument("--days", type=int, default=14, help="Planning horizon in days")
    p_plan.set_defaults(func=cmd_plan)

    # plans
    p_plans = subparsers.add_parser("plans", help="List plans")
    p_plans.add_argument("--status", default=None,
                         choices=["draft", "active", "blocked", "done", "dropped"],
                         help="Filter by status")
    p_plans.set_defaults(func=cmd_plans)

    # deprioritize (was forget - nothing dies)
    p_depri = subparsers.add_parser("deprioritize", aliases=["dp"],
                                     help="Lower memory importance (nothing is deleted)")
    p_depri.add_argument("memory_id", help="Memory ID to deprioritize")
    p_depri.add_argument("--shared", action="store_true", help="Deprioritize in shared repo")
    p_depri.set_defaults(func=cmd_deprioritize)

    # sync
    p_sync = subparsers.add_parser("sync", help="Pull latest shared memories from git")
    p_sync.set_defaults(func=cmd_sync)

    # stats
    p_stats = subparsers.add_parser("stats", help="Memory stats")
    p_stats.add_argument("--shared", action="store_true", help="Include shared repo stats")
    p_stats.set_defaults(func=cmd_stats)

    # fill
    p_fill = subparsers.add_parser("fill", help="Bulk memory ingestion")
    p_fill.add_argument("mode", choices=["interactive", "bulk", "parse", "template"],
                        help="Ingestion mode")
    p_fill.add_argument("file", nargs="?", default=None, help="File for bulk/parse modes")
    p_fill.add_argument("--person", default="", help="Person name (template mode)")
    p_fill.add_argument("--project", default="", help="Project name (template mode)")
    p_fill.add_argument("--archetype", default="", help="Project archetype (template mode)")
    p_fill.set_defaults(func=cmd_fill)

    # disagree
    p_disagree = subparsers.add_parser("disagree", help="Track disagreements (both sides get vectors)")
    p_disagree.add_argument("action", choices=["record", "resolve", "stats", "list"],
                            help="What to do")
    p_disagree.add_argument("--topic", default="", help="What the disagreement is about")
    p_disagree.add_argument("--human", default="", help="What the human said")
    p_disagree.add_argument("--ai", default="", help="What the AI said")
    p_disagree.add_argument("--id", default="", help="Disagreement ID (for resolve)")
    p_disagree.add_argument("--winner", default="", choices=["human", "ai", "compromise", ""],
                            help="Who was right (for resolve)")
    p_disagree.add_argument("--resolved-by", default="", help="Who resolved it")
    p_disagree.add_argument("--shared", action="store_true", help="Use shared git repo")
    p_disagree.set_defaults(func=cmd_disagree)

    # health
    p_health = subparsers.add_parser("healthz", aliases=["health"],
                                      help="System health dashboard")
    p_health.add_argument("--shared", action="store_true", help="Include shared repo")
    p_health.set_defaults(func=cmd_health)

    # todo
    p_todo = subparsers.add_parser("todo", help="Generate effort-aware TODO.md")
    p_todo.add_argument("--project", help="Project root directory (default: current)")
    p_todo.set_defaults(func=cmd_todo)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
