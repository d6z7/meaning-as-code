"""Unit tests for the Phase-6 content-addressed LLM response cache — key derivation + the
hit/miss/refresh contract — driven by a FAKE completion fn (no Bedrock, no AWS)."""

from sdk.project.harvest_cache import HarvestCache, cache_key

# --- key derivation ---------------------------------------------------------------------------


def test_cache_key_is_stable_and_input_sensitive():
    base = {
        "model": "eu.anthropic.claude-sonnet-4-5-v1",
        "effort": "high",
        "thinking_budget": None,
        "system_prompt": "SYS",
        "user_input": "USER",
    }
    k = cache_key(**base)
    assert k == cache_key(**base)  # deterministic
    assert len(k) == 64 and all(c in "0123456789abcdef" for c in k)  # sha256 hex
    # every decode-determining field is in the key
    assert cache_key(**{**base, "model": "us.anthropic.claude-haiku-4-5-v1"}) != k
    assert cache_key(**{**base, "effort": "low"}) != k
    assert cache_key(**{**base, "thinking_budget": 4096}) != k
    assert cache_key(**{**base, "system_prompt": "SYS2"}) != k
    assert cache_key(**{**base, "user_input": "USER2"}) != k


# --- hit / miss / refresh ---------------------------------------------------------------------


def _counter_fn(store):
    """A fake invoke_fn that records how many times it actually ran (i.e. a cache MISS)."""

    def _fn(system, user):
        store["calls"] += 1
        return f"COMPLETION::{system}::{user}::{store['calls']}"

    return _fn


def test_miss_then_hit_is_byte_identical(tmp_path):
    store = {"calls": 0}
    cache = HarvestCache(cache_dir=tmp_path / ".harvest_cache")
    kw = {
        "model": "eu.anthropic.claude-sonnet-4-5-v1",
        "effort": "high",
        "thinking_budget": None,
        "invoke_fn": _counter_fn(store),
    }

    first = cache.complete("SYS", "USER", **kw)  # MISS: computes + stores
    second = cache.complete("SYS", "USER", **kw)  # HIT: returns stored bytes
    assert first == second  # byte-identical re-run (idempotency)
    assert store["calls"] == 1  # invoke_fn ran ONCE (second was cached)
    assert cache.stats == {"hits": 1, "misses": 1}


def test_changed_input_misses_again(tmp_path):
    store = {"calls": 0}
    cache = HarvestCache(cache_dir=tmp_path / ".harvest_cache")
    kw = {
        "model": "eu.anthropic.claude-sonnet-4-5-v1",
        "effort": "high",
        "thinking_budget": None,
        "invoke_fn": _counter_fn(store),
    }
    cache.complete("SYS", "USER", **kw)
    cache.complete("SYS", "USER-DIFFERENT", **kw)  # different user input -> new key -> MISS
    assert store["calls"] == 2
    assert cache.stats == {"hits": 0, "misses": 2}


def test_refresh_bypasses_the_cache(tmp_path):
    store = {"calls": 0}
    warm = HarvestCache(cache_dir=tmp_path / ".harvest_cache")
    kw = {
        "model": "eu.anthropic.claude-sonnet-4-5-v1",
        "effort": "high",
        "thinking_budget": None,
        "invoke_fn": _counter_fn(store),
    }
    warm.complete("SYS", "USER", **kw)  # warm the cache (MISS)
    assert store["calls"] == 1

    fresh = HarvestCache(cache_dir=tmp_path / ".harvest_cache", refresh=True)
    fresh.complete("SYS", "USER", **kw)  # --refresh: forced recompute despite a hit
    assert store["calls"] == 2
    assert fresh.stats == {"hits": 0, "misses": 1}


def test_second_process_reuses_on_disk_cache(tmp_path):
    """A brand-new cache object over the SAME dir hits the prior run's on-disk entry — the
    cross-process idempotency the onboarding contract relies on."""
    store = {"calls": 0}
    kw = {
        "model": "eu.anthropic.claude-sonnet-4-5-v1",
        "effort": "high",
        "thinking_budget": None,
        "invoke_fn": _counter_fn(store),
    }
    HarvestCache(cache_dir=tmp_path / ".harvest_cache").complete("SYS", "USER", **kw)
    # a fresh object (as a second `harvest` invocation would create) reads the same bytes
    out = HarvestCache(cache_dir=tmp_path / ".harvest_cache").complete("SYS", "USER", **kw)
    assert out == "COMPLETION::SYS::USER::1"
    assert store["calls"] == 1  # no recompute across the two objects
