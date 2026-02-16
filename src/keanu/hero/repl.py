"""repl.py - interactive terminal for keanu.

type a task, the agent loop runs, you see the result.
/craft, /prove, /explore switch modes. /help for commands.

in the world: the front door. type a task, or just explore.
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from keanu.abilities import list_abilities
from keanu.hero.do import AgentLoop, Step, DO_CONFIG, CRAFT_CONFIG, PROVE_CONFIG, EXPLORE_CONFIG
from keanu.log import info

console = Console()

BANNER = [
    Text(),
    Text(" ██╗  ██╗███████╗ █████╗ ███╗   ██╗██╗   ██╗", style="bold green"),
    Text(" ██║ ██╔╝██╔════╝██╔══██╗████╗  ██║██║   ██║", style="bold green"),
    Text(" █████╔╝ █████╗  ███████║██╔██╗ ██║██║   ██║", style="bold green"),
    Text(" ██╔═██╗ ██╔══╝  ██╔══██║██║╚██╗██║██║   ██║", style="bold green"),
    Text(" ██║  ██╗███████╗██║  ██║██║ ╚████║╚██████╔╝", style="bold green"),
    Text(" ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝", style="bold green"),
    Text(),
    Text("  type a task, or /help", style="dim"),
    Text(),
]

HELP_TEXT = """
  [bold]/help[/bold]              show this
  [bold]/abilities[/bold]         list registered abilities
  [bold]/mode[/bold] [dim][do|craft|prove|explore][/dim]  switch agent mode
  [bold]/explore[/bold]           explore mode. no task, just curiosity.
  [bold]/model[/bold] [dim][name][/dim]     show or switch model
  [bold]/legend[/bold] [dim][name][/dim]    show or switch legend
  [bold]/quit[/bold]              exit
"""

MODES = {"do": DO_CONFIG, "craft": CRAFT_CONFIG, "prove": PROVE_CONFIG, "explore": EXPLORE_CONFIG}


def _print_step(step: Step):
    """print a single agent step with color."""
    if step.action == "done":
        return
    if step.action == "breathe":
        console.print(f"  [dim italic]{step.input_summary[:120]}[/dim italic]")
        return
    if step.action == "think":
        console.print(f"  [dim]{step.input_summary[:120]}[/dim]")
    elif step.ok:
        console.print(f"  [green]{step.action}[/green] [dim]{step.input_summary[:80]}[/dim]")
    else:
        console.print(f"  [red]{step.action} FAILED[/red] [dim]{step.result[:80]}[/dim]")


def _print_feel(feel_stats):
    """print feel stats with rich styling."""
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
        console.print(f"  [dim]{', '.join(parts)}[/dim]")


class Repl:
    """Interactive keanu terminal."""

    def __init__(self, legend="creator", model=None):
        self.legend = legend
        self.model = model
        self.config = DO_CONFIG
        self.store = None
        try:
            from keanu.memory import MemberberryStore
            self.store = MemberberryStore()
        except Exception:
            pass

    def run(self):
        for line in BANNER:
            console.print(line)

        while True:
            try:
                prompt = f"[green]{self.config.name}> [/green]" if self.config != DO_CONFIG else "[green]> [/green]"
                user_input = console.input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                self._quit()
                break
            if not user_input:
                continue
            if user_input.startswith("/"):
                if self._slash(user_input):
                    break
                continue
            self._run_task(user_input)

    def _slash(self, cmd: str) -> bool:
        """handle slash command. returns True to quit."""
        parts = cmd.split(None, 1)
        command = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if command in ("/quit", "/q", "/exit"):
            self._quit()
            return True
        elif command == "/help":
            console.print(HELP_TEXT)
        elif command == "/abilities":
            for ab in list_abilities():
                console.print(f"  [green]{ab['name']}[/green]  {ab['description']}")
        elif command == "/mode":
            if arg in MODES:
                self.config = MODES[arg]
                console.print(f"  mode -> [green]{arg}[/green]")
            elif arg:
                console.print(f"  [red]unknown mode.[/red] use: {', '.join(MODES)}")
            else:
                console.print(f"  mode: [green]{self.config.name}[/green]")
        elif command == "/explore":
            self.config = EXPLORE_CONFIG
            console.print(f"  mode -> [green]explore[/green]")
            self._run_task("look around")
        elif command in ("/craft", "/prove", "/do"):
            mode = command[1:]
            self.config = MODES[mode]
            console.print(f"  mode -> [green]{mode}[/green]")
        elif command == "/model":
            if arg:
                self.model = arg
                console.print(f"  model -> [green]{arg}[/green]")
            else:
                console.print(f"  model: [green]{self.model or 'default'}[/green]")
        elif command == "/legend":
            if arg:
                from keanu.legends import list_legends
                available = list_legends()
                if arg in available:
                    self.legend = arg
                    console.print(f"  legend -> [green]{arg}[/green]")
                else:
                    console.print(f"  [red]unknown legend[/red] ({' | '.join(available)})")
            else:
                console.print(f"  legend: [green]{self.legend}[/green]")
        else:
            console.print(f"  [red]unknown:[/red] {command}. try /help")
        return False

    def _run_task(self, task: str):
        """run agent loop on a task."""
        info("repl", f"task: {task[:80]}")
        loop = AgentLoop(self.config, store=self.store)

        with console.status("[green]thinking...", spinner="dots"):
            result = loop.run(task, legend=self.legend, model=self.model)

        for step in result.steps:
            _print_step(step)

        console.print()
        if result.ok:
            if result.answer:
                try:
                    console.print(Markdown(result.answer))
                except Exception:
                    console.print(f"  {result.answer}")
        elif result.status == "paused":
            console.print(f"  [yellow]paused:[/yellow] {result.error}")
        elif result.status == "max_turns":
            console.print(f"  [yellow]hit turn limit[/yellow]")
            if result.steps:
                console.print(f"  last: {result.steps[-1].action} -> {result.steps[-1].result[:120]}")
        else:
            console.print(f"  [red]error:[/red] {result.error}")

        _print_feel(result.feel_stats)
        console.print()

    def _quit(self):
        from keanu.log import flush_sink
        flush_sink()
        console.print("\n  [dim]bye[/dim]")


def run_repl(legend="creator", model=None):
    Repl(legend=legend, model=model).run()
