"""
COEF Instructions: Compressed Instruction Language
====================================================
Token-efficient operations that reference DNS entries.
The verbs. Clone, swap, inject, rename, regex, compose, pipe, literal, store.
"""

from dataclasses import dataclass


@dataclass
class COEFInstruction:
    op: str
    args: dict

    def to_tokens(self) -> str:
        return f"{self.op}:{' '.join(f'{k}={v}' for k, v in self.args.items())}"

    @classmethod
    def from_tokens(cls, s: str) -> "COEFInstruction":
        op, rest = s.split(":", 1)
        args = {}
        for pair in rest.strip().split(" "):
            if "=" in pair:
                k, v = pair.split("=", 1)
                args[k] = v
        return cls(op=op, args=args)


@dataclass
class COEFProgram:
    instructions: list[COEFInstruction]
    expected_hash: str | None = None

    def to_wire(self) -> str:
        parts = [i.to_tokens() for i in self.instructions]
        if self.expected_hash:
            parts.append(f"verify:{self.expected_hash[:16]}")
        return " | ".join(parts)

    @classmethod
    def from_wire(cls, wire: str) -> "COEFProgram":
        parts = [p.strip() for p in wire.split("|")]
        insts, eh = [], None
        for p in parts:
            if p.startswith("verify:"):
                eh = p.split(":", 1)[1]
            else:
                insts.append(COEFInstruction.from_tokens(p))
        return cls(instructions=insts, expected_hash=eh)

    def token_count(self) -> int:
        return len(self.to_wire().split())
