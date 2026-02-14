"""keanu CLI: unified entry point.

Usage:
    keanu scan document.md          # three-primary reading
    keanu bake                      # train lenses from examples
    keanu converge "question"       # duality synthesis
    keanu connect a.md b.md         # cross-source alignment
    keanu compress module.py        # COEF compression
    keanu signal "emoji-string"     # decode signal
    keanu todo                      # generate effort-aware TODO.md
"""

import argparse
import sys


def cmd_scan(args):
    """Scan a document through three color lenses."""
    from keanu.scan.helix import helix_scan
    for filepath in args.files:
        print(f"Scanning: {filepath}")
        results = helix_scan(filepath)
        for line_result in results:
            print(line_result)


def cmd_bake(args):
    """Train lenses from examples into chromadb."""
    from keanu.scan.bake import bake
    lenses = args.lenses if args.lenses else None
    bake(lenses)


def cmd_converge(args):
    """Run duality convergence on a question."""
    from keanu.converge.engine import run
    from keanu.converge.graph import DualityGraph
    graph = DualityGraph()
    run(args.question, backend=args.backend, model=args.model, graph=graph)


def cmd_connect(args):
    """Align two sources via helix scanning."""
    from keanu.converge.connection import connect
    connect(args.source_a, args.source_b)


def cmd_compress(args):
    """COEF compression of a module."""
    from keanu.compress.dns import DNSStore
    store = DNSStore()
    with open(args.file) as f:
        content = f.read()
    entry = store.store(content)
    print(f"Stored: {entry}")


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


def cmd_todo(args):
    """Generate effort-aware TODO.md."""
    from keanu.todo import generate_todo
    generate_todo(args.project or ".")


def main():
    parser = argparse.ArgumentParser(
        prog="keanu",
        description="Scans through three color lenses, compresses what matters, finds truth.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # scan
    p_scan = subparsers.add_parser("scan", help="Three-primary reading of a document")
    p_scan.add_argument("files", nargs="+", help="Files to scan")
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
