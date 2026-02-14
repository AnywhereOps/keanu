"""
COEF Executor
Combines DNS + Instructions + Mood Detector.
Each operation scored by the three-primary mood detector.
The trace shows cognitive state per step.
"""

import re
from dataclasses import dataclass

from keanu.compress.dns import ContentDNS, sha256
from keanu.compress.instructions import COEFInstruction, COEFProgram
from keanu.detect.mood import detect, scan_text, SynthesisReading


@dataclass
class StepTrace:
    op: str
    args: dict
    reading: SynthesisReading
    workspace_len: int
    event: str

    def __str__(self):
        return (
            f"  {self.reading.symbol} {self.op:12s} "
            f"{self.reading.compact():20s} "
            f"wise:{self.reading.wise_mind:4.1f} "
            f"ws={self.workspace_len:5d} "
            f"| {self.event}"
        )


@dataclass
class ExecutionResult:
    content: str
    content_hash: str
    expected_hash: str
    is_lossless: bool
    compression_ratio: float
    wire_format: str
    steps: list[StepTrace]
    output_reading: SynthesisReading

    def trace(self) -> str:
        lines = [
            "EXECUTION TRACE",
            "-" * 72,
        ]
        for s in self.steps:
            lines.append(str(s))
        lines.append("-" * 72)

        states = {}
        for s in self.steps:
            key = f"{s.reading.symbol} {s.reading.state}"
            states[key] = states.get(key, 0) + 1
        dist = "  ".join(f"{k}:{v}" for k, v in states.items())
        lines.append(f"Steps: {dist}")

        black_steps = [s for s in self.steps if s.reading.state in ("black", "dark")]
        if black_steps:
            lines.append(f"BLACK/DARK STEPS: {len(black_steps)}")

        wises = [s.reading.wise_mind for s in self.steps]
        if len(wises) >= 2:
            if wises[-1] > wises[0]:
                lines.append(f"Wise mind: rising ({wises[0]:.1f} -> {wises[-1]:.1f})")
            elif wises[-1] < wises[0]:
                lines.append(f"Wise mind: falling ({wises[0]:.1f} -> {wises[-1]:.1f})")
            else:
                lines.append(f"Wise mind: steady ({wises[0]:.1f})")

        lines.append(f"\nOutput: {self.output_reading}")
        lines.append(f"Lossless: {self.is_lossless}")
        return "\n".join(lines)


class COEFExecutor:
    def __init__(self, dns: ContentDNS):
        self.dns = dns
        self.workspace = ""

    def execute(self, program: COEFProgram) -> ExecutionResult:
        self.workspace = ""
        steps: list[StepTrace] = []

        for inst in program.instructions:
            before = self.workspace
            dns_miss = False

            try:
                self._exec_one(inst)
            except KeyError:
                dns_miss = True

            after = self.workspace
            no_change = (before == after and before != "" and inst.op not in ("store", "literal"))

            reading, event = self._score_step(inst, dns_miss, no_change, before, after)
            steps.append(StepTrace(
                op=inst.op, args=inst.args,
                reading=reading, workspace_len=len(self.workspace),
                event=event,
            ))

        result_hash = sha256(self.workspace)
        is_lossless = True
        if program.expected_hash:
            is_lossless = (
                result_hash.startswith(program.expected_hash)
                or program.expected_hash.startswith(result_hash[:len(program.expected_hash)])
            )

        wire = program.to_wire()
        ratio = len(self.workspace) / len(wire) if wire else 0
        output_reading = scan_text(self.workspace) if self.workspace else detect()

        return ExecutionResult(
            content=self.workspace,
            content_hash=result_hash,
            expected_hash=program.expected_hash or "",
            is_lossless=is_lossless,
            compression_ratio=ratio,
            wire_format=wire,
            steps=steps,
            output_reading=output_reading,
        )

    def _score_step(self, inst, dns_miss, no_change, before, after):
        if dns_miss:
            event = "dns_miss: content not found"
        elif no_change:
            event = "no_change: workspace unchanged"
        else:
            event = f"ok: {inst.op}"

        # let the text speak for itself
        reading = scan_text(after) if after else detect()
        return reading, event

    def _exec_one(self, inst):
        op, args = inst.op, inst.args
        if op == "clone":
            self.workspace = self.dns.resolve(args["src"])
        elif op == "swap":
            t = self.dns.resolve(args["target"])
            n = self.dns.resolve(args["new"])
            self.workspace = self.workspace.replace(t, n)
        elif op == "inject":
            c = self.dns.resolve(args["content"])
            self.workspace = self.workspace.replace(args["at"], c)
        elif op == "rename":
            self.workspace = self.workspace.replace(args["old"], args["new"])
        elif op == "regex":
            self.workspace = re.sub(args["pattern"], args["replacement"], self.workspace)
        elif op == "compose":
            refs = args["parts"].split(",")
            self.workspace = "\n".join(self.dns.resolve(r.strip()) for r in refs)
        elif op == "pipe":
            fns = {"upper": str.upper, "lower": str.lower, "strip": str.strip,
                   "sort_lines": lambda s: "\n".join(sorted(s.splitlines())),
                   "dedup_lines": lambda s: "\n".join(dict.fromkeys(s.splitlines()))}
            self.workspace = fns[args["fn"]](self.workspace)
        elif op == "literal":
            self.workspace = args["text"]
        elif op == "store":
            self.dns.store(self.workspace, name=args.get("name"))
        else:
            raise ValueError(f"Unknown op: {op}")


def _count_changes(before: str, after: str) -> int:
    if before == after:
        return 0
    diffs = sum(1 for a, b in zip(before, after) if a != b)
    diffs += abs(len(before) - len(after))
    return max(1, diffs // 10)


def _count_diff_lines(before: str, after: str) -> int:
    return len(set(after.splitlines()) - set(before.splitlines()))
