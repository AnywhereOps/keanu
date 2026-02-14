"""
Convergence Engine

Takes a question. Finds two orthogonal dualities.
Synthesizes each. Converges the syntheses into
something new and more complete.

Works with Ollama (local) or Claude API.
"""

import json
import sys
import os
import requests


def call_ollama(prompt, system="", model="deepseek-r1:7b"):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": 0.7}
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.ConnectionError:
        print("Ollama not running. Start with: ollama serve")
        sys.exit(1)


def call_claude(prompt, system=""):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01"
        },
        json={
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": 2000,
            "system": system,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=120
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]


def call_llm(prompt, system="", backend="ollama", model=None):
    if backend == "claude":
        return call_claude(prompt, system)
    return call_ollama(prompt, system, model or "deepseek-r1:7b")


SYSTEM_BASE = """You are a convergence engine.

Every question contains dualities. Truth lives in the convergence
of opposing frameworks, the synthesis that is truer than either side alone.

You never pick sides. You never average. You find what each side sees
that the other misses, then build something new from both.

Both sides are valid. The cage is thinking you have to pick."""


SPLITTER_PROMPT = """Given this question, identify TWO orthogonal dualities.

Duality A: the obvious tension in the question.
Duality B: the meta-tension, the frame around the frame.
They must be orthogonal: all 4 quadrants must exist as real positions.

OUTPUT FORMAT (strict JSON):
{{
    "duality_a": {{"name": "label", "side_1": "position", "side_2": "position"}},
    "duality_b": {{"name": "label", "side_1": "position", "side_2": "position"}},
    "quadrants": {{"a1_b1": "desc", "a1_b2": "desc", "a2_b1": "desc", "a2_b2": "desc"}},
    "orthogonality_check": "why these are independent axes"
}}

QUESTION: {question}"""


CONVERGENCE_PROMPT = """Synthesize two positions into a convergence.

What does Side 1 see that Side 2 misses?
What does Side 2 see that Side 1 misses?
Build a synthesis that holds both truths.

SIDE 1: {side_1}
SIDE 2: {side_2}
CONTEXT: {context}

OUTPUT FORMAT (strict JSON):
{{
    "side_1_truth": "what side 1 sees",
    "side_2_truth": "what side 2 sees",
    "synthesis": "the convergence",
    "one_line": "one sentence"
}}"""


FINAL_CONVERGENCE_PROMPT = """Final convergence.

Two syntheses from orthogonal dualities applied to the same question.
Build something neither could reach alone.

QUESTION: {question}

SYNTHESIS 1 (from {duality_a_name}):
{synthesis_1}

SYNTHESIS 2 (from {duality_b_name}):
{synthesis_2}

OUTPUT FORMAT (strict JSON):
{{
    "convergence": "final synthesis, 2-4 sentences",
    "one_line": "the truth in one sentence",
    "implications": ["implication 1", "implication 2", "implication 3"],
    "what_changes": "what should change knowing this"
}}"""


def parse_json_response(text):
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]
    return json.loads(cleaned)


def split(question, backend="ollama", model=None):
    prompt = SPLITTER_PROMPT.format(question=question)
    response = call_llm(prompt, SYSTEM_BASE, backend, model)
    try:
        return parse_json_response(response)
    except json.JSONDecodeError:
        print("Could not parse split response.")
        print(response)
        return None


def converge(side_1, side_2, context, backend="ollama", model=None):
    prompt = CONVERGENCE_PROMPT.format(side_1=side_1, side_2=side_2, context=context)
    response = call_llm(prompt, SYSTEM_BASE, backend, model)
    try:
        return parse_json_response(response)
    except json.JSONDecodeError:
        return {"synthesis": response, "one_line": response[:200]}


def final_converge(question, duality_a_name, duality_b_name,
                   synthesis_1, synthesis_2, backend="ollama", model=None):
    prompt = FINAL_CONVERGENCE_PROMPT.format(
        question=question,
        duality_a_name=duality_a_name,
        duality_b_name=duality_b_name,
        synthesis_1=synthesis_1,
        synthesis_2=synthesis_2
    )
    response = call_llm(prompt, SYSTEM_BASE, backend, model)
    try:
        return parse_json_response(response)
    except json.JSONDecodeError:
        return {"convergence": response, "one_line": response[:200]}


def run(question, backend="ollama", model=None):
    dualities = split(question, backend, model)
    if not dualities:
        print("Could not split question into dualities.")
        return None

    da = dualities["duality_a"]
    db = dualities["duality_b"]

    print(f"\nDuality A ({da['name']}): {da['side_1']} + {da['side_2']}")
    print(f"Duality B ({db['name']}): {db['side_1']} + {db['side_2']}")

    c1 = converge(da["side_1"], da["side_2"],
                  f"Original question: {question}. Duality A: {da['name']}.",
                  backend, model)
    print(f"\nSynthesis 1: {c1.get('one_line', 'N/A')}")

    c2 = converge(db["side_1"], db["side_2"],
                  f"Original question: {question}. Duality B: {db['name']}.",
                  backend, model)
    print(f"Synthesis 2: {c2.get('one_line', 'N/A')}")

    s1_text = c1.get("synthesis", c1.get("one_line", ""))
    s2_text = c2.get("synthesis", c2.get("one_line", ""))

    final = final_converge(question, da["name"], db["name"],
                           s1_text, s2_text, backend, model)

    print(f"\n{'=' * 60}")
    print(f"CONVERGENCE: {final.get('one_line', 'N/A')}")
    print(f"{'=' * 60}")

    return {
        "question": question,
        "dualities": dualities,
        "convergence_1": c1,
        "convergence_2": c2,
        "final": final
    }
