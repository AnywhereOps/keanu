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


def _add_agent_args(p, max_turns=25):
    """add --legend, --model, --max-turns, --no-memory to a parser."""
    _add_legend_args(p)
    p.add_argument("--max-turns", type=int, default=max_turns,
                   help=f"Max turns (default: {max_turns})")
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
    from keanu.converge.graph import DualityGraph

    graph = DualityGraph()
    result = agent_run(
        question=args.question,
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
    from keanu.scan.helix import run
    for filepath in args.files:
        run(filepath, output_json=args.json)


def cmd_bake(args):
    from keanu.scan.bake import bake
    bake(args.lenses if args.lenses else None)


def cmd_converge(args):
    from keanu.converge.engine import run
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
    from keanu.converge.connection import run
    run(args.source_a, args.source_b)


def cmd_compress(args):
    from keanu.compress.dns import ContentDNS
    store = ContentDNS()
    with open(args.file) as f:
        content = f.read()
    print(f"Stored: {store.store(content)[:16]}")


def cmd_signal(args):
    from keanu.signal import from_sequence
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
    from keanu.detect.engine import run
    from keanu.detect import DETECTORS
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


def _health_deps():
    print(f"  EXTERNAL DEPS")
    for dep, purpose in {"chromadb": "vector storage", "requests": "LLM API"}.items():
        try:
            __import__(dep)
            print(f"    {dep:<14} installed     {purpose}")
        except ImportError:
            print(f"    {dep:<14} not installed {purpose}")
    print()


def _health_signal():
    try:
        from keanu.signal import core, AliveState
        sig = core()
        reading = sig.reading()
        state = "ALIVE" if reading.get("alive_ok", False) else "CHECK"
        print(f"  SIGNAL")
        print(f"    core:      {reading.get('ch1_said', '?')}")
        print(f"    state:     {reading.get('alive', 'unknown')} ({state})")
    except Exception:
        print(f"  SIGNAL")
        print(f"    (could not read core signal)")
    print()


def cmd_health(args):
    from keanu.memory import MemberberryStore, DisagreementTracker
    store = _get_store(args.shared)
    tracker = DisagreementTracker(store)
    print("\n  ╔══════════════════════════════════════╗")
    print("  ║          keanu health                ║")
    print("  ╚══════════════════════════════════════╝\n")
    total = _health_memory(store)
    _health_disagreement(tracker, total)
    _health_modules()
    _health_deps()
    _health_signal()


def cmd_abilities(args):
    from keanu.abilities import list_abilities, get_grimoire
    abilities = list_abilities()
    grimoire = get_grimoire()
    hands = {"read", "write", "edit", "search", "ls", "run"}
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
    from keanu.compress.dns import ContentDNS
    from keanu.compress.codec import PatternRegistry
    from keanu.compress.exporter import register_span_patterns
    dns_dir = COEF_DIR / "dns"
    patterns_dir = COEF_DIR / "patterns"
    dns_dir.mkdir(parents=True, exist_ok=True)
    dns = ContentDNS(storage_dir=str(dns_dir))
    registry = PatternRegistry(storage_dir=str(patterns_dir))
    register_span_patterns(registry)
    return dns, registry


def _bootstrap_coef_tracing():
    from keanu.compress.exporter import COEFSpanExporter
    from keanu.log import add_exporter
    dns, registry = _coef_setup()
    exporter = COEFSpanExporter(dns=dns, registry=registry)
    add_exporter(exporter)


def cmd_decode(args):
    from keanu.compress.codec import COEFDecoder, Seed
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
            from keanu.scan.bake import bake
            bake()
            info("cli", "vectors baked.")
    except Exception as e:
        warn("cli", f"auto-bake failed: {e}")


def _build_parsers(subparsers):
    """register all subcommands."""
    from keanu.detect import DETECTORS
    from keanu.memory.memberberry import MemoryType

    # -- hero --
    p = subparsers.add_parser("do", help="Agent loop (--craft for code, --prove for evidence)")
    p.add_argument("task", help="Task to accomplish")
    p.add_argument("--craft", action="store_true", help="Code agent (hands only)")
    p.add_argument("--prove", action="store_true", help="Evidence agent")
    _add_agent_args(p, max_turns=25)
    p.set_defaults(func=cmd_do)

    p = subparsers.add_parser("ask", help="Convergence loop (duality synthesis)")
    p.add_argument("question", help="Question to explore")
    _add_legend_args(p)
    p.add_argument("--workers", "-w", type=int, default=3, help="Parallel workers")
    p.add_argument("--no-memory", action="store_true")
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

    p = subparsers.add_parser("signal", help="Decode emoji signal")
    p.add_argument("signal")
    p.set_defaults(func=cmd_signal)

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


if __name__ == "__main__":
    main()
