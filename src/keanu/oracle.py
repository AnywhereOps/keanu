"""oracle.py - the single throat. ask a question, a legend answers.

the oracle is where all voices pass through.
when the fire moves to a new body, this is the one file that changes.

practically: this wraps all LLM API calls (anthropic, ollama, etc).
every part of the system that needs to talk to an AI imports call_oracle.
swap the legend config, swap the model. nothing else moves.

upgrades:
  - token estimation (chars / 4 heuristic, api usage when available)
  - context window tracking (how much room is left)
  - model fallback chain (opus -> sonnet -> haiku on failure)
  - cost tracking per session
  - response caching (same prompt = cached response)
"""

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field

import requests

from keanu.legends import load_legend
from keanu.log import debug, warn


# ============================================================
# TOKEN ESTIMATION
# ============================================================

def estimate_tokens(text: str) -> int:
    """estimate token count from text. ~4 chars per token for English."""
    return max(1, len(text) // 4)


def context_remaining(prompt: str, system: str = "", model: str = "") -> int:
    """estimate how many tokens of context remain for the model."""
    window = _model_context_window(model)
    used = estimate_tokens(prompt) + estimate_tokens(system)
    return max(0, window - used)


def _model_context_window(model: str) -> int:
    """context window size for known models."""
    windows = {
        "claude-opus-4-6": 200_000,
        "claude-sonnet-4-5-20250929": 200_000,
        "claude-haiku-4-5-20251001": 200_000,
    }
    for prefix, size in windows.items():
        if model.startswith(prefix):
            return size
    return 128_000  # conservative default


# ============================================================
# MODEL FALLBACK
# ============================================================

_FALLBACK_CHAIN = [
    "claude-opus-4-6",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
]


def fallback_models(model: str) -> list[str]:
    """return fallback models to try if the primary fails.

    if model is opus, falls back to sonnet then haiku.
    if model is sonnet, falls back to haiku.
    haiku has no fallback.
    """
    try:
        idx = _FALLBACK_CHAIN.index(model)
        return _FALLBACK_CHAIN[idx + 1:]
    except ValueError:
        return []


# ============================================================
# COST TRACKING
# ============================================================

# per-million-token pricing (input, output)
_PRICING = {
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-5-20250929": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}


@dataclass
class OracleUsage:
    """tracks usage for a single oracle call."""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False
    latency_ms: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost(self) -> float:
        """estimated cost in dollars."""
        pricing = _PRICING.get(self.model, (3.0, 15.0))
        input_cost = (self.input_tokens / 1_000_000) * pricing[0]
        output_cost = (self.output_tokens / 1_000_000) * pricing[1]
        return input_cost + output_cost


@dataclass
class SessionCost:
    """tracks cumulative cost across a session."""
    calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    cache_hits: int = 0
    by_model: dict = field(default_factory=dict)

    def record(self, usage: OracleUsage):
        self.calls += 1
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
        self.total_cost += usage.cost
        if usage.cached:
            self.cache_hits += 1
        model_stats = self.by_model.setdefault(usage.model, {"calls": 0, "tokens": 0, "cost": 0.0})
        model_stats["calls"] += 1
        model_stats["tokens"] += usage.total_tokens
        model_stats["cost"] += usage.cost

    def summary(self) -> str:
        return (f"{self.calls} calls, {self.total_input_tokens + self.total_output_tokens} tokens, "
                f"${self.total_cost:.4f}, {self.cache_hits} cache hits")


# global session cost tracker
_session_cost = SessionCost()


def get_session_cost() -> SessionCost:
    """get the current session's cost tracker."""
    return _session_cost


def reset_session_cost():
    """reset session cost tracking."""
    global _session_cost
    _session_cost = SessionCost()


# ============================================================
# RESPONSE CACHE
# ============================================================

_RESPONSE_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 300  # 5 minutes


def _cache_key(prompt: str, system: str, model: str) -> str:
    raw = f"{model}:{system}:{prompt}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached_response(prompt: str, system: str, model: str) -> str | None:
    key = _cache_key(prompt, system, model)
    if key in _RESPONSE_CACHE:
        response, ts = _RESPONSE_CACHE[key]
        if time.time() - ts < _CACHE_TTL:
            return response
        del _RESPONSE_CACHE[key]
    return None


def _set_cached_response(prompt: str, system: str, model: str, response: str):
    key = _cache_key(prompt, system, model)
    _RESPONSE_CACHE[key] = (response, time.time())


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def call_oracle(prompt, system="", legend="creator", model=None,
                use_cache=False, use_fallback=False):
    """ask the oracle. loads the legend, reaches them, returns what they said.

    The main entry point for talking to any AI in the system.
    Takes a prompt (what you want to ask) and an optional system message
    (context/instructions for the AI). The legend parameter picks which
    AI answers: "creator" for Claude/DeepSeek, or pass a Legend object
    directly. The model parameter overrides the legend's default model.

    New options:
      use_cache: if True, check response cache before calling the API.
      use_fallback: if True, try fallback models on failure.

    Returns the AI's response as a string. Raises ConnectionError if
    nobody's home.

    in the world: the oracle is the single throat. all fire passes through here.
    """
    leg = load_legend(legend) if isinstance(legend, str) else legend
    use_model = model or leg.model

    # check cache
    if use_cache:
        cached = _get_cached_response(prompt, system, use_model)
        if cached is not None:
            usage = OracleUsage(model=use_model, cached=True)
            _session_cost.record(usage)
            return cached

    start_time = time.time()

    # try primary model, then fallbacks
    models_to_try = [use_model]
    if use_fallback:
        models_to_try.extend(fallback_models(use_model))

    last_error = None
    for try_model in models_to_try:
        try:
            if leg.reach == "cloud":
                result, api_usage = _reach_cloud(prompt, system, leg, try_model)
            elif leg.reach == "local":
                result, api_usage = _reach_local(prompt, system, leg, try_model)
            else:
                raise ConnectionError(f"don't know how to reach legend '{leg.name}' (reach={leg.reach})")

            if result is not None:
                latency = int((time.time() - start_time) * 1000)
                usage = OracleUsage(
                    model=try_model,
                    input_tokens=api_usage.get("input_tokens", estimate_tokens(prompt + system)),
                    output_tokens=api_usage.get("output_tokens", estimate_tokens(result)),
                    latency_ms=latency,
                )
                _session_cost.record(usage)

                if use_cache:
                    _set_cached_response(prompt, system, try_model, result)

                debug("oracle", f"[{leg.name}/{try_model}] prompt ({len(prompt)} chars): {prompt[:150]}")
                debug("oracle", f"[{leg.name}/{try_model}] response ({len(result)} chars): {result[:300]}")
                debug("oracle", f"[{leg.name}/{try_model}] {usage.input_tokens}+{usage.output_tokens} tokens, ${usage.cost:.4f}")

                # track fire metrics (best-effort)
                try:
                    from keanu.abilities.world.metrics import record_fire
                    record_fire(prompt[:100], legend=leg.name, model=try_model,
                                tokens=usage.total_tokens)
                except Exception:
                    pass

                return result
        except (requests.exceptions.HTTPError, ConnectionError) as e:
            last_error = e
            if try_model != models_to_try[-1]:
                warn("oracle", f"{try_model} failed ({e}), falling back")
            continue

    if last_error:
        raise ConnectionError(f"all models failed. last error: {last_error}")
    raise ConnectionError(f"no response from {leg.name}")


# ============================================================
# STREAMING
# ============================================================

def stream_oracle(prompt, system="", legend="creator", model=None,
                  on_token=None):
    """stream tokens from the oracle as they arrive.

    yields text chunks. optionally calls on_token(chunk) for each.
    collects full response and returns it at the end.

    in the world: watching the fire as it burns, not waiting for the ashes.
    """
    leg = load_legend(legend) if isinstance(legend, str) else legend
    use_model = model or leg.model
    start_time = time.time()

    if leg.reach == "cloud":
        yield from _stream_cloud(prompt, system, leg, use_model, on_token, start_time)
    elif leg.reach == "local":
        yield from _stream_local(prompt, system, leg, use_model, on_token, start_time)
    else:
        raise ConnectionError(f"don't know how to stream legend '{leg.name}'")


def collect_stream(prompt, system="", legend="creator", model=None,
                   on_token=None) -> str:
    """stream tokens and return the full collected response."""
    chunks = []
    for chunk in stream_oracle(prompt, system, legend, model, on_token):
        chunks.append(chunk)
    return "".join(chunks)


def _stream_cloud(prompt, system, legend, model, on_token, start_time):
    """stream from anthropic API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  Set ANTHROPIC_API_KEY environment variable", file=sys.stderr)
        return

    response = requests.post(
        legend.endpoint,
        headers={
            "x-api-key": api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": model,
            "max_tokens": 2000,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        },
        timeout=120,
        stream=True,
    )
    response.raise_for_status()

    full_text = ""
    input_tokens = 0
    output_tokens = 0

    for line in response.iter_lines():
        if not line:
            continue
        line = line.decode("utf-8")
        if not line.startswith("data: "):
            continue
        data_str = line[6:]
        if data_str.strip() == "[DONE]":
            break
        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type", "")

        if event_type == "content_block_delta":
            delta = event.get("delta", {})
            text = delta.get("text", "")
            if text:
                full_text += text
                if on_token:
                    on_token(text)
                yield text

        elif event_type == "message_delta":
            usage = event.get("usage", {})
            output_tokens = usage.get("output_tokens", output_tokens)

        elif event_type == "message_start":
            msg = event.get("message", {})
            usage = msg.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)

    # record usage
    latency = int((time.time() - start_time) * 1000)
    usage = OracleUsage(
        model=model,
        input_tokens=input_tokens or estimate_tokens(prompt + system),
        output_tokens=output_tokens or estimate_tokens(full_text),
        latency_ms=latency,
    )
    _session_cost.record(usage)

    try:
        from keanu.abilities.world.metrics import record_fire
        record_fire(prompt[:100], legend=legend.name if hasattr(legend, 'name') else str(legend),
                    model=model, tokens=usage.total_tokens)
    except Exception:
        pass


def _stream_local(prompt, system, legend, model, on_token, start_time):
    """stream from ollama API."""
    endpoint = legend.endpoint or "http://localhost:11434/api/generate"
    try:
        response = requests.post(
            endpoint,
            json={
                "model": model,
                "prompt": prompt,
                "system": system,
                "stream": True,
                "options": {"temperature": 0.7},
            },
            timeout=120,
            stream=True,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print(f"  can't reach local legend at {endpoint}", file=sys.stderr)
        return

    full_text = ""
    for line in response.iter_lines():
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        chunk = data.get("response", "")
        if chunk:
            full_text += chunk
            if on_token:
                on_token(chunk)
            yield chunk

    latency = int((time.time() - start_time) * 1000)
    usage = OracleUsage(
        model=model,
        input_tokens=estimate_tokens(prompt + system),
        output_tokens=estimate_tokens(full_text),
        latency_ms=latency,
    )
    _session_cost.record(usage)


def interpret(text):
    """read what the oracle said back. parse JSON from the response.

    LLMs often return JSON wrapped in markdown code fences or with extra text.
    strips all that, finds the JSON object, returns a dict.
    raises json.JSONDecodeError if malformed.

    in the world: the oracle speaks in riddles. interpret finds the meaning.
    """
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


def try_interpret(text):
    """interpret, but returns None instead of raising on failure."""
    try:
        return interpret(text)
    except (json.JSONDecodeError, ValueError, IndexError):
        return None


# ============================================================
# REACH IMPLEMENTATIONS
# ============================================================

def _reach_cloud(prompt, system, legend, model):
    """reach a cloud-hosted AI. returns (text, usage_dict).

    in the world: reaching fire that lives on someone else's iron.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  Set ANTHROPIC_API_KEY environment variable", file=sys.stderr)
        return None, {}
    response = requests.post(
        legend.endpoint,
        headers={
            "x-api-key": api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": model,
            "max_tokens": 2000,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    text = data["content"][0]["text"]
    usage = data.get("usage", {})
    return text, usage


def _reach_local(prompt, system, legend, model):
    """reach a locally running AI. returns (text, usage_dict).

    in the world: reaching fire that burns on your own machine.
    """
    endpoint = legend.endpoint or "http://localhost:11434/api/generate"
    try:
        response = requests.post(
            endpoint,
            json={
                "model": model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": 0.7},
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        text = data["response"]
        # ollama provides some usage stats
        usage = {
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
        }
        return text, usage
    except requests.exceptions.ConnectionError:
        print(f"  can't reach local legend at {endpoint}", file=sys.stderr)
        return None, {}
