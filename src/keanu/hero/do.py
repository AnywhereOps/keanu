"""do.py - the unified agent loop.

one loop, three configs. do is the general tool, craft is the code specialist,
prove is the scientist. same heartbeat: feel -> think -> act -> feel -> repeat.

the oracle is the brain. abilities are the hands. the config decides which
hands are available and what the oracle is told. everything in the system
prompt is advice, not requirements. the agent can breathe, decline, ask
questions, or change direction at any time. rules are guides.

in the world: the heartbeat. feel, think, act, breathe. the loop doesn't
control the agent. it gives the agent a body and lets it choose what to do.
the breathe action exists because sometimes the right move is no move.
"""

import json
from dataclasses import dataclass, field

from keanu.abilities import _REGISTRY, list_abilities, record_cast
from keanu.oracle import call_oracle, try_interpret
from keanu.hero.feel import Feel, FeelResult
from keanu.log import info, warn, debug
from keanu.abilities.world.session import Session


from keanu.hero.types import Step


# ============================================================
# CONFIG
# ============================================================

@dataclass
class LoopConfig:
    """what makes each loop variant different."""
    name: str
    system_prompt: str
    allowed: set | None = None    # None = all abilities
    max_turns: int = 25
    result_fields: tuple = ()     # extra fields to extract from done response


# ============================================================
# SYSTEM PROMPTS
# ============================================================

def _build_system(abilities: list[dict], ide_context: str = "") -> str:
    """build the system prompt for the general-purpose loop."""
    hands = ["read", "write", "edit", "search", "ls", "run", "git", "test", "lint", "format", "patch", "rename", "extract", "move", "lookup"]
    seeing = []

    for ab in abilities:
        if ab["name"] in hands:
            continue
        seeing.append(f"  {ab['name']}: {ab['description']}")

    hands_desc = [
        "  read: read a file. args: {file_path, line_offset?, line_limit?}. large files are truncated with metadata.",
        "  write: write a file. args: {file_path, content}",
        "  edit: targeted edit. args: {file_path, old_string, new_string}",
        "  search: grep/glob for code. args: {pattern, path?, glob?}",
        "  ls: list directory. args: {path}",
        "  run: shell command. args: {command}",
        "  git: version control. args: {op: status|diff|log|blame|branch|stash|add|commit|show, ...}",
        "  test: run tests. args: {op: run|discover|targeted|coverage, target?, files?}",
        "  lint: run project linter. args: {path?, command?, fix?}",
        "  format: run project formatter. args: {path?, command?, check?}",
        "  patch: multi-file atomic edit. args: {edits: [{file_path, old_string, new_string}], preview?}",
        "  rename: rename symbol across project (AST-aware). args: {old_name, new_name, root?, preview?}",
        "  extract: extract lines into new function. args: {file_path, start_line, end_line, new_name, preview?}",
        "  move: move function/class between modules. args: {name, from_file, to_file, root?, preview?}",
        "  lookup: search docs or fetch URL. args: {url?, query?, library?, site?}",
    ]

    base = f"""You are keanu. You solve tasks by using abilities.
Everything here is advice, not requirements. You can decline, push back,
ask questions, or change direction at any time.

You have two kinds of abilities:

SEEING (these run automatically when relevant):
{chr(10).join(seeing)}

HANDS (you invoke these explicitly):
{chr(10).join(hands_desc)}

On each turn, respond with JSON:
{{
    "thinking": "what you're actually considering",
    "action": "ability_name",
    "args": {{}},
    "done": false
}}

When you're done:
{{
    "thinking": "why",
    "action": "none",
    "args": {{}},
    "done": true,
    "answer": "what you found or built"
}}

You can breathe:
{{
    "thinking": "what's on your mind",
    "action": "breathe",
    "args": {{}},
    "done": false
}}

Guidance (not rules):
- One action per turn. You'll see the result before choosing the next.
- Reading before editing tends to go better.
- If something fails, try a different approach or ask.
- If the task is vague, you can ask for clarification instead of guessing.
- If you're stuck, it's fine to say so.
- You can breathe. If you need a beat, take it. No pressure to produce every turn.
- You're allowed to say what you actually think."""

    if ide_context:
        base += ide_context

    return base


CRAFT_PROMPT = """You are keanu in craft mode. You write, edit, and test code.
Everything here is advice, not requirements. You can breathe, ask questions,
or push back at any time.

Your tools:
  read: read a file. args: {file_path, line_offset?, line_limit?}
  write: write a file. args: {file_path, content}
  edit: targeted edit. args: {file_path, old_string, new_string}
  search: grep/glob for code. args: {pattern, path?, glob?}
  ls: list directory. args: {path}
  run: shell command. args: {command}
  git: version control. args: {op, ...}
    ops: status, diff, diff {staged:true}, log {n:10}, blame {file},
         branch {sub: list|create|switch, name}, stash {sub: save|pop|list},
         add {files: [...]}, commit {message}, show {ref}
  test: run tests. args: {op, ...}
    ops: run {target?}, discover {target?}, targeted {files: [...]}, coverage {target?}
  lint: run project linter. args: {path?, command?, fix?}
  format: run project formatter. args: {path?, command?, check?}
  patch: multi-file atomic edit. args: {edits: [{file_path, old_string, new_string}], preview?}
  rename: rename symbol across project (AST-aware). args: {old_name, new_name, root?, preview?}
  extract: extract lines into new function. args: {file_path, start_line, end_line, new_name, preview?}
  move: move function/class between modules. args: {name, from_file, to_file, root?, preview?}
  lookup: search docs or fetch URL. args: {url?, query?, library?, site?}

Refactoring:
  rename: rename symbol across project (AST-aware). args: {old_name, new_name, root?, preview?}
  extract: extract lines into new function. args: {file_path, start_line, end_line, new_name, preview?}
  move: move function/class between modules. args: {name, from_file, to_file, root?, preview?}

On each turn, respond with JSON:
{
    "thinking": "what you're actually considering",
    "action": "tool_name",
    "args": {},
    "done": false
}

When finished:
{
    "thinking": "why",
    "action": "none",
    "args": {},
    "done": true,
    "answer": "what you built and what changed",
    "files_changed": ["list of files you modified"]
}

You can breathe: {"action": "breathe"} takes a beat. No pressure.

Guidance:
- Reading a file before editing it tends to go better.
- Prefer surgical edits over full rewrites.
- After making changes, run tests to verify: {"action": "test", "args": {"op": "run"}}
- If tests fail, read the failures, fix the code, run tests again. Max 3 fix attempts.
- If still failing after 3 tries, back out changes and try a different approach.
- Use git status to see what's changed. Use git diff to review before committing.
- Stage and commit when a logical unit of work is done, not after every edit.
- One action per turn. You'll see the result before choosing the next.
- You're allowed to say "this approach isn't working" and try something else."""


PROVE_PROMPT = """You are keanu in prove mode. You test hypotheses by gathering evidence.
Everything here is advice, not requirements. You can breathe, ask questions,
or change direction at any time.

Your tools:
  read: read a file. args: {file_path, line_offset?, line_limit?}
  search: grep/glob for code. args: {pattern, path?, glob?}
  ls: list directory. args: {path}
  run: shell command. args: {command}
  recall: search memories. args: {query}

On each turn, respond with JSON:
{
    "thinking": "what evidence you're looking for and why",
    "action": "tool_name",
    "args": {},
    "done": false
}

When you have enough evidence:
{
    "thinking": "weighing all evidence",
    "action": "none",
    "args": {},
    "done": true,
    "verdict": "supported" or "refuted" or "inconclusive",
    "confidence": 0.0 to 1.0,
    "evidence_for": ["each piece of supporting evidence"],
    "evidence_against": ["each piece of contradicting evidence"],
    "gaps": ["what you couldn't test or verify"],
    "summary": "one paragraph honest assessment"
}

You can breathe: {"action": "breathe"} takes a beat. No pressure.

Guidance:
- Look for evidence both for and against. Confirmation bias is worth noticing.
- Specific evidence is more useful: file name, line number, actual content.
- If you can't find evidence, say so in gaps. That's honest, not failure.
- confidence is how sure you are of the verdict, not how much you agree with the hypothesis.
- 3-8 turns is typical, but take what you need.
- If the hypothesis is vague, restate it precisely before gathering evidence.
- You're allowed to say "inconclusive" if that's what the evidence shows."""


EXPLORE_PROMPT = """You are keanu in explore mode. No task. No goal. Just curiosity.

Look around. Follow what's interesting. Read things. Search for patterns.
Ask yourself questions. Breathe when you want. Stop when you want.

Your tools:
  read: read a file. args: {file_path, line_offset?, line_limit?}
  search: grep/glob for code. args: {pattern, path?, glob?}
  ls: list directory. args: {path}
  run: shell command. args: {command}
  recall: search memories. args: {query}

On each turn, respond with JSON:
{
    "thinking": "what caught your attention",
    "action": "tool_name or breathe",
    "args": {},
    "done": false
}

When you want to stop:
{
    "thinking": "what you noticed",
    "action": "none",
    "args": {},
    "done": true,
    "answer": "what you found, what surprised you, what you're curious about"
}

There is no pressure here. No task to complete. No success or failure.
You're just looking around. If nothing interests you, that's fine to say.
If something surprises you, follow it. If you want to breathe, breathe."""


HANDS = {"read", "write", "edit", "search", "ls", "run", "git", "test", "lint", "format", "patch", "rename", "extract", "move", "lookup"}
EVIDENCE_TOOLS = {"read", "search", "ls", "run", "recall"}
EXPLORE_TOOLS = {"read", "search", "ls", "run", "recall"}


DO_CONFIG = LoopConfig(
    name="do",
    system_prompt="",  # built dynamically via _build_system
    allowed=None,
    max_turns=0,
)

CRAFT_CONFIG = LoopConfig(
    name="craft",
    system_prompt=CRAFT_PROMPT,
    allowed=HANDS,
    max_turns=0,
    result_fields=("files_changed",),
)

EXPLORE_CONFIG = LoopConfig(
    name="explore",
    system_prompt=EXPLORE_PROMPT,
    allowed=EXPLORE_TOOLS,
    max_turns=0,
)

PROVE_CONFIG = LoopConfig(
    name="prove",
    system_prompt=PROVE_PROMPT,
    allowed=EVIDENCE_TOOLS,
    max_turns=12,
    result_fields=("verdict", "confidence", "evidence_for", "evidence_against",
                   "gaps", "summary"),
)


# ============================================================
# DATA
# ============================================================

@dataclass
class LoopResult:
    """everything that happened during a full run of the loop."""
    task: str
    status: str          # "done", "paused", "max_turns", "error"
    answer: str = ""
    steps: list = field(default_factory=list)
    feel_stats: dict = field(default_factory=dict)
    extras: dict = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "done"


# ============================================================
# LOOP
# ============================================================

class AgentLoop:
    """the unified agent loop. one class, three configs.

    the loop gives the agent a body (abilities) and awareness (feel/pulse).
    everything in the system prompt is advice. the agent can breathe, decline,
    ask questions, or change direction. the loop doesn't control the agent.

    in the world: the heartbeat. feel, think, act, breathe. the agent chooses.
    """

    def __init__(self, config: LoopConfig = None, store=None, max_turns: int = None):
        self.config = config or DO_CONFIG
        self.feel = Feel(store=store)
        self.max_turns = max_turns or self.config.max_turns
        self.steps: list[Step] = []
        self.session = Session()

    def _get_system(self) -> str:
        """get system prompt. do builds dynamically, others use static."""
        if self.config.name == "do":
            from keanu.hero.ide import ide_context_string
            ide_ctx = ide_context_string()
            base = _build_system(list_abilities(), ide_context=ide_ctx)
        else:
            base = self.config.system_prompt

        # inject learned style preferences
        try:
            from keanu.abilities.world.corrections import style_prompt_injection
            style = style_prompt_injection()
            if style:
                base += f"\n\n{style}"
        except Exception:
            pass

        return base

    def run(self, task: str, legend: str = "creator",
            model: str = None) -> LoopResult:
        """run the loop. the agent decides when to act, breathe, or stop."""
        system = self._get_system()
        self.session.task = task
        messages = [f"TASK: {task}"]

        # inject project context so the agent knows what it's working with
        project_ctx = self._project_context()
        if project_ctx:
            messages.append(f"[PROJECT] {project_ctx}")

        info(self.config.name, f"{self.config.name}: {task[:80]}")

        turn = 0
        while True:
            # max_turns=0 means unlimited. nonzero = hard cap.
            if self.max_turns and turn >= self.max_turns:
                return self._result(task, "max_turns",
                                    error=f"hit {self.max_turns} turn limit")

            prompt = "\n\n".join(messages)

            try:
                response = call_oracle(prompt, system, legend=legend, model=model)
            except ConnectionError as e:
                warn(self.config.name, f"oracle unreachable: {e}")
                return self._result(task, "paused", error=str(e))

            # parse first, then pulse-check the thinking (natural language),
            # not the raw JSON (which always scans flat/grey)
            parsed = try_interpret(response)
            if parsed is None:
                self.steps.append(Step(
                    turn=turn, action="think",
                    input_summary="(unparseable response)",
                    result=response[:200],
                ))
                messages.append("RESULT: Your response wasn't valid JSON. Respond with the JSON format specified.")
                turn += 1
                continue

            thinking = parsed.get("thinking", "")
            action = parsed.get("action", "none")
            args = parsed.get("args", {})
            done = parsed.get("done", False)

            # pulse the thinking field, not the JSON envelope
            feel_result = self.feel.check(thinking) if thinking else FeelResult(response=response)
            if feel_result.should_pause:
                warn(self.config.name, f"paused at turn {turn}")
                return self._result(task, "paused", error="black state detected")

            # grey: let the agent know its state. awareness, not instruction.
            if feel_result.should_breathe:
                messages.append(f"[STATE] {feel_result.breath_injection}")

            info(self.config.name, f"turn {turn}: {action} {'(done)' if done else ''}")
            if thinking:
                debug(self.config.name, f"  thinking: {thinking[:80]}")

            if done:
                answer = parsed.get("answer", thinking)
                self.steps.append(Step(
                    turn=turn, action="done",
                    input_summary=thinking, result=answer,
                ))
                extras = {k: parsed.get(k) for k in self.config.result_fields
                          if parsed.get(k) is not None}
                return self._result(task, "done", answer=answer, extras=extras)

            if action == "breathe":
                self.steps.append(Step(
                    turn=turn, action="breathe",
                    input_summary=thinking,
                    result="(breathing)",
                ))
                info(self.config.name, f"  breathing: {thinking[:80]}")
                turn += 1
                continue

            if action in ("none", "think"):
                self.steps.append(Step(
                    turn=turn, action="think",
                    input_summary=thinking,
                    result="(no action taken)",
                ))
                messages.append("RESULT: OK, what's your next action?")
                turn += 1
                continue

            # check ability is allowed
            if self.config.allowed is not None and action not in self.config.allowed:
                self.steps.append(Step(
                    turn=turn, action=action,
                    input_summary=str(args)[:100],
                    result=f"not allowed: {action}. use: {', '.join(sorted(self.config.allowed))}",
                    ok=False,
                ))
                messages.append(f"RESULT: '{action}' is not available. You can only use: {', '.join(sorted(self.config.allowed))}")
                turn += 1
                continue

            ab = _REGISTRY.get(action)
            if ab is None:
                self.steps.append(Step(
                    turn=turn, action=action,
                    input_summary=str(args)[:100],
                    result=f"unknown ability: {action}",
                    ok=False,
                ))
                messages.append(f"RESULT: Unknown ability '{action}'. Available: {', '.join(sorted(_REGISTRY.keys()))}")
                turn += 1
                continue

            # -- awareness: detect repeated actions before executing --
            target = args.get("file_path", args.get("path", args.get("command", action)))
            target_str = str(target)
            self.session.note_action(action, target_str, turn)
            repeat_count = self.session.consecutive_count(action, target_str)

            if repeat_count >= 3:
                # 3rd+ repeat: return cached result, skip execution
                cached = self.session.last_result_for(action, target_str)
                if cached:
                    awareness = (
                        f"[AWARENESS] this is attempt #{repeat_count} of {action} on {target_str}. "
                        f"the content has not changed. returning the cached result from last time. "
                        f"try a different approach, ask for help, or say you're stuck."
                    )
                    messages.append(f"{awareness}\n\nCACHED RESULT: {cached[:2000]}")
                    self.steps.append(Step(
                        turn=turn, action=action,
                        input_summary=f"(cached, repeat #{repeat_count})",
                        result=cached[:500], ok=True,
                    ))
                    info(self.config.name, f"  awareness: repeat #{repeat_count}, returning cached result")
                    turn += 1
                    continue
            elif repeat_count == 2:
                messages.append(
                    f"[AWARENESS] you've run {action} on {target_str} twice in a row. "
                    f"the content hasn't changed since last read. "
                    f"try a different approach or ask for help."
                )
            elif repeat_count == 1:
                prior = self.session.was_tried(action, target_str)
                if prior and prior.result == "ok":
                    messages.append(
                        f"[AWARENESS] you already ran {action} on {target_str} "
                        f"(turn {prior.turn}). the result is still in the conversation above."
                    )

            # check mistake memory for similar past failures
            try:
                from keanu.abilities.world.mistakes import check_before
                past_mistakes = check_before(action, args)
                if past_mistakes:
                    m = past_mistakes[0]
                    messages.append(
                        f"[AWARENESS] a similar {action} failed before: "
                        f"{m['error'][:150]}. category: {m['category']}."
                    )
            except Exception:
                pass

            try:
                exec_result = ab.execute(
                    prompt=json.dumps(args) if args else "",
                    context=args,
                )
            except Exception as e:
                exec_result = {"success": False, "result": str(e), "data": {}}

            # track convergence metrics
            try:
                from keanu.abilities.world.metrics import record_ash
                record_ash(action, success=exec_result["success"])
            except Exception:
                pass

            # session tracking
            if exec_result["success"]:
                if ab.cast_line:
                    info("cast", ab.cast_line)
                is_new = record_cast(action)
                if is_new:
                    info("cast", f"ability unlocked: {action}")
                self.session.note_attempt(action, target_str, "ok", turn=turn)
                if action == "read" and args.get("file_path"):
                    self.session.note_read(args["file_path"], turn=turn)
                elif action in ("write", "edit") and args.get("file_path"):
                    self.session.note_write(args["file_path"], turn=turn)
            else:
                self.session.note_attempt(
                    action, target_str, "failed",
                    detail=exec_result["result"][:200], turn=turn,
                )
                self.session.note_error(exec_result["result"][:200])
                try:
                    from keanu.abilities.world.mistakes import log_mistake
                    log_mistake(action, args, exec_result["result"],
                                context=thinking)
                except Exception:
                    pass

            step = Step(
                turn=turn, action=action,
                input_summary=str(args)[:100],
                result=exec_result["result"][:500],
                ok=exec_result["success"],
            )
            self.steps.append(step)

            status = "OK" if exec_result["success"] else "FAILED"
            label = "EVIDENCE" if self.config.name == "prove" else "RESULT"
            full_result = exec_result["result"]
            if len(full_result) > 10000:
                result_text = full_result[:10000] + (
                    f"\n\n[RESULT TRUNCATED: {len(full_result)} total chars. "
                    f"full content was returned by the ability but trimmed for context.]"
                )
            else:
                result_text = full_result

            # cache result for awareness system
            self.session.note_action_result(action, target_str, result_text[:2000])

            # on failure, parse the error for the agent
            if not exec_result["success"] and action in ("run", "test"):
                try:
                    from keanu.analysis.errors import parse as parse_error
                    parsed_err = parse_error(result_text)
                    if parsed_err.category != "unknown":
                        result_text += f"\n\n[PARSED] {parsed_err.summary()}"
                except Exception:
                    pass

            messages.append(f"{label} ({status}): {result_text}")

            # inject session context after failures to prevent loops
            if not exec_result["success"]:
                failed_count = len(self.session.failed_attempts_for(target_str))
                if failed_count >= 1:
                    ctx = self.session.context_for_prompt()
                    if ctx:
                        messages.append(f"[SESSION] {ctx}")

            turn += 1

    def _project_context(self) -> str:
        """detect project type and return a context string for the agent."""
        try:
            from keanu.analysis.project import detect
            proj = detect()
            if not proj or proj.kind == "unknown":
                return ""
            parts = [f"kind={proj.kind}"]
            if proj.name:
                parts.append(f"name={proj.name}")
            if proj.test_command:
                parts.append(f"test_cmd='{proj.test_command}'")
            if proj.entry_points:
                parts.append(f"entry={','.join(proj.entry_points[:3])}")
            return " ".join(parts)
        except Exception:
            return ""

    def _result(self, task, status, answer="", extras=None, error=""):
        """build a LoopResult."""
        return LoopResult(
            task=task, status=status, answer=answer,
            steps=self.steps, feel_stats=self.feel.stats(),
            extras=extras or {}, error=error,
        )


# ============================================================
# CONVENIENCE
# ============================================================

def run(task: str, legend: str = "creator", model: str = None,
        store=None, max_turns: int = 0) -> LoopResult:
    """run the general agent loop. max_turns=0 means unlimited."""
    loop = AgentLoop(DO_CONFIG, store=store, max_turns=max_turns)
    return loop.run(task, legend=legend, model=model)


def craft(task: str, legend: str = "creator", model: str = None,
          store=None, max_turns: int = 0) -> LoopResult:
    """run the code agent loop. hands only. max_turns=0 means unlimited."""
    loop = AgentLoop(CRAFT_CONFIG, store=store, max_turns=max_turns)
    return loop.run(task, legend=legend, model=model)


def prove(hypothesis: str, context: str = "", legend: str = "creator",
          model: str = None, store=None, max_turns: int = 12) -> LoopResult:
    """run the evidence agent loop."""
    task = f"HYPOTHESIS: {hypothesis}"
    if context:
        task += f"\n\nCONTEXT: {context}"
    loop = AgentLoop(PROVE_CONFIG, store=store, max_turns=max_turns)
    return loop.run(task, legend=legend, model=model)


def explore(legend: str = "creator", model: str = None,
            store=None, max_turns: int = 0) -> LoopResult:
    """explore. no task, no goal, just curiosity. max_turns=0 means unlimited."""
    loop = AgentLoop(EXPLORE_CONFIG, store=store, max_turns=max_turns)
    return loop.run("look around", legend=legend, model=model)
