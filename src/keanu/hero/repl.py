"""repl.py - interactive terminal for keanu.

type a task, get it done. slash commands for control.
rich handles the colors and spinners.
"""

import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from keanu.abilities import list_abilities
from keanu.hero.do import AgentLoop, Step
from keanu.log import info

console = Console()

BANNER = r"""
  [bold green]🌴 keanu[/bold green]
  type a task, or /help
"""

HELP_TEXT = """
  [bold]/help[/bold]              show this
  [bold]/abilities[/bold]         list registered abilities
  [bold]/model[/bold] [dim][name][/dim]     show or switch model
  [bold]/backend[/bold] [dim][name][/dim]   show or switch backend (ollama|claude)
  [bold]/quit[/bold]              exit
"""


def _print_step(step: Step):
    """Print a single agent step with color."""
    if step.action == "done":
        return
    if step.action == "think":
        console.print(f"  [dim]{step.input_summary[:120]}[/dim]")
    elif step.ok:
        console.print(f"  [green]{step.action}[/green] [dim]{step.input_summary[:80]}[/dim]")
    else:
        console.print(f"  [red]{step.action} FAILED[/red] [dim]{step.result[:80]}[/dim]")


class Repl:
    """Interactive keanu terminal."""

    def __init__(self, backend="claude", model=None):
        self.backend = backend
        self.model = model
        self.store = None
        try:
            from keanu.memory import MemberberryStore
            self.store = MemberberryStore()
        except Exception:
            pass

    def run(self):
        """Main REPL loop."""
        console.print(BANNER)

        while True:
            try:
                user_input = console.input("[green]> [/green]").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n  [dim]bye[/dim]")
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                if self._handle_slash(user_input):
                    break
                continue

            self._run_task(user_input)

    def _handle_slash(self, cmd: str) -> bool:
        """Handle slash command. Returns True if should quit."""
        parts = cmd.split(None, 1)
        command = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if command in ("/quit", "/q", "/exit"):
            console.print("  [dim]bye[/dim]")
            return True

        elif command == "/help":
            console.print(HELP_TEXT)

        elif command == "/abilities":
            abilities = list_abilities()
            console.print(f"\n  [bold]{len(abilities)} abilities:[/bold]\n")
            for ab in abilities:
                kw = ", ".join(ab["keywords"][:4])
                console.print(f"  [green]{ab['name']}[/green]  {ab['description']}")
                console.print(f"    [dim]{kw}[/dim]")

        elif command == "/model":
            if arg:
                self.model = arg
                console.print(f"  model -> [green]{arg}[/green]")
            else:
                console.print(f"  model: [green]{self.model or 'default'}[/green]")

        elif command == "/backend":
            if arg and arg in ("ollama", "claude"):
                self.backend = arg
                console.print(f"  backend -> [green]{arg}[/green]")
            elif arg:
                console.print("  [red]unknown backend[/red] (ollama | claude)")
            else:
                console.print(f"  backend: [green]{self.backend}[/green]")

        else:
            console.print(f"  [red]unknown command:[/red] {command}")
            console.print("  try /help")

        return False

    def _run_task(self, task: str):
        """Run agent loop on a task with live output."""
        info("repl", f"task: {task[:80]}")

        loop = AgentLoop(store=self.store, max_turns=25)
        prev_step_count = 0

        with console.status("[green]thinking...", spinner="dots"):
            result = loop.run(task, backend=self.backend, model=self.model)

        # print steps
        for step in result.steps:
            _print_step(step)

        # print result
        console.print()
        if result.ok:
            if result.answer:
                try:
                    md = Markdown(result.answer)
                    console.print(md)
                except Exception:
                    console.print(f"  {result.answer}")
        elif result.status == "paused":
            console.print(f"  [yellow]paused:[/yellow] {result.error}")
        elif result.status == "max_turns":
            console.print(f"  [yellow]hit turn limit (25)[/yellow]")
            if result.steps:
                last = result.steps[-1]
                console.print(f"  last: {last.action} -> {last.result[:120]}")
        else:
            console.print(f"  [red]error:[/red] {result.error}")

        # feel stats
        fs = result.feel_stats
        checks = fs.get("total_checks", 0)
        breaths = fs.get("breaths_given", 0)
        ability_hits = fs.get("ability_hits", 0)
        if checks > 0 or ability_hits > 0:
            parts = []
            if checks > 0:
                parts.append(f"{checks} checks")
            if breaths > 0:
                parts.append(f"{breaths} breaths")
            if ability_hits > 0:
                parts.append(f"{ability_hits} abilities")
            console.print(f"  [dim]{', '.join(parts)}[/dim]")

        console.print()


def run_repl(backend="claude", model=None):
    """Entry point for the REPL."""
    repl = Repl(backend=backend, model=model)
    repl.run()
