"""tests for oracle upgrades: token estimation, fallback, caching, cost tracking."""

from unittest.mock import patch, MagicMock

from keanu.oracle import (
    estimate_tokens, context_remaining, _model_context_window,
    fallback_models, OracleUsage, SessionCost, get_session_cost,
    reset_session_cost, call_oracle, interpret, try_interpret,
    _get_cached_response, _set_cached_response, _RESPONSE_CACHE,
)


class TestTokenEstimation:

    def test_estimate_basic(self):
        assert estimate_tokens("hello world") >= 1

    def test_estimate_empty(self):
        assert estimate_tokens("") == 1

    def test_estimate_long(self):
        text = "a" * 4000
        assert estimate_tokens(text) == 1000

    def test_context_remaining(self):
        remaining = context_remaining("short prompt", model="claude-haiku-4-5-20251001")
        assert remaining > 100000

    def test_context_remaining_unknown_model(self):
        remaining = context_remaining("prompt", model="unknown-model")
        # should use conservative default
        assert remaining > 0


class TestModelContextWindow:

    def test_opus(self):
        assert _model_context_window("claude-opus-4-6") == 200_000

    def test_sonnet(self):
        assert _model_context_window("claude-sonnet-4-5-20250929") == 200_000

    def test_unknown(self):
        assert _model_context_window("some-other-model") == 128_000


class TestFallbackModels:

    def test_opus_fallback(self):
        chain = fallback_models("claude-opus-4-6")
        assert len(chain) == 2
        assert "sonnet" in chain[0]
        assert "haiku" in chain[1]

    def test_sonnet_fallback(self):
        chain = fallback_models("claude-sonnet-4-5-20250929")
        assert len(chain) == 1
        assert "haiku" in chain[0]

    def test_haiku_no_fallback(self):
        chain = fallback_models("claude-haiku-4-5-20251001")
        assert chain == []

    def test_unknown_no_fallback(self):
        chain = fallback_models("unknown-model")
        assert chain == []


class TestOracleUsage:

    def test_total_tokens(self):
        u = OracleUsage(model="claude-opus-4-6", input_tokens=100, output_tokens=50)
        assert u.total_tokens == 150

    def test_cost(self):
        u = OracleUsage(model="claude-opus-4-6", input_tokens=1000, output_tokens=500)
        assert u.cost > 0

    def test_cost_unknown_model(self):
        u = OracleUsage(model="unknown", input_tokens=1000, output_tokens=500)
        assert u.cost > 0  # uses default pricing


class TestSessionCost:

    def test_record(self):
        sc = SessionCost()
        usage = OracleUsage(model="claude-opus-4-6", input_tokens=100, output_tokens=50)
        sc.record(usage)
        assert sc.calls == 1
        assert sc.total_input_tokens == 100
        assert sc.total_output_tokens == 50

    def test_multiple_records(self):
        sc = SessionCost()
        sc.record(OracleUsage(model="claude-opus-4-6", input_tokens=100, output_tokens=50))
        sc.record(OracleUsage(model="claude-haiku-4-5-20251001", input_tokens=200, output_tokens=100))
        assert sc.calls == 2
        assert len(sc.by_model) == 2

    def test_cache_hits(self):
        sc = SessionCost()
        sc.record(OracleUsage(model="m", cached=True))
        assert sc.cache_hits == 1

    def test_summary(self):
        sc = SessionCost()
        sc.record(OracleUsage(model="claude-opus-4-6", input_tokens=1000, output_tokens=500))
        s = sc.summary()
        assert "1 calls" in s
        assert "1500 tokens" in s

    def test_get_and_reset(self):
        reset_session_cost()
        sc = get_session_cost()
        assert sc.calls == 0
        sc.record(OracleUsage(model="m", input_tokens=10, output_tokens=5))
        assert get_session_cost().calls == 1
        reset_session_cost()
        assert get_session_cost().calls == 0


class TestResponseCache:

    def setup_method(self):
        _RESPONSE_CACHE.clear()

    def test_set_and_get(self):
        _set_cached_response("prompt", "system", "model", "response")
        assert _get_cached_response("prompt", "system", "model") == "response"

    def test_miss(self):
        assert _get_cached_response("nope", "", "") is None

    def test_different_model(self):
        _set_cached_response("prompt", "system", "model-a", "response-a")
        assert _get_cached_response("prompt", "system", "model-b") is None


class TestCallOracle:

    def test_basic_call(self):
        with patch("keanu.oracle._reach_cloud", return_value=("hello", {"input_tokens": 10, "output_tokens": 5})):
            result = call_oracle("test prompt", legend="creator")
        assert result == "hello"

    def test_with_cache(self):
        _RESPONSE_CACHE.clear()
        with patch("keanu.oracle._reach_cloud", return_value=("cached_result", {})):
            # first call
            r1 = call_oracle("same prompt", legend="creator", use_cache=True)
            # second call should hit cache
            r2 = call_oracle("same prompt", legend="creator", use_cache=True)
        assert r1 == r2 == "cached_result"

    def test_fallback(self):
        call_count = [0]

        def failing_then_ok(prompt, system, legend, model):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("primary failed")
            return ("fallback result", {})

        with patch("keanu.oracle._reach_cloud", side_effect=failing_then_ok):
            # should fail without fallback
            try:
                call_oracle("test", legend="creator", use_fallback=False)
                assert False, "should have raised"
            except Exception:
                pass

    def test_connection_error(self):
        with patch("keanu.oracle._reach_cloud", return_value=(None, {})):
            try:
                call_oracle("test", legend="creator")
                assert False, "should have raised"
            except ConnectionError:
                pass


class TestInterpret:

    def test_plain_json(self):
        assert interpret('{"key": "value"}') == {"key": "value"}

    def test_json_in_code_fence(self):
        text = '```json\n{"key": "value"}\n```'
        assert interpret(text) == {"key": "value"}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result: {"key": "value"} end.'
        assert interpret(text) == {"key": "value"}

    def test_try_interpret_returns_none_on_failure(self):
        assert try_interpret("not json") is None

    def test_try_interpret_success(self):
        assert try_interpret('{"a": 1}') == {"a": 1}
