#!/usr/bin/env python3
"""harvest_cache.py — the content-addressed LLM response cache for the harvest (Phase 6).

Key = ``sha256(model, effort, thinking_budget, system_prompt, user_input)``. On a HIT the
stored completion is returned verbatim, so an UNCHANGED authoring input re-runs
BYTE-IDENTICALLY across processes — the idempotency lever the onboarding contract leans on.
A MISS calls the injected ``invoke_fn`` (the real Bedrock/Mantle call from
``sdk.authoring.harvest_model.make_invoker``) and stores its bytes. ``refresh=True`` bypasses
reads (always a miss + overwrite) — the ``--refresh`` escape hatch.

IDEMPOTENCY (documented, not hidden): the cache converges the LLM stages for unchanged
inputs. The residual nondeterminism that cannot be removed — thinking-ON decode sampling on a
genuine MISS — is bounded by (a) this cache (each input is decoded ONCE, then frozen) and (b)
the human review gate before publish. We do not pretend the raw call is deterministic; we make
its RESULT reproducible once observed.

WHY THIS LIVES IN sdk/project: the write-once gate (sdk/gate/check_write_paths.py) confines
SSOT writes to operations.py and forbids write primitives in the authoring heads. The cache
writes DERIVED, gitignored, non-SSOT output (under ``.harvest_cache/``) — the same category as
the read-view projector — so its home is the derived-output plane, injected UP into the
authoring call as a plain object (the heads only call ``cache.complete(...)``; they hold no
write primitive of their own). Stdlib only — importing this never needs the AWS SDKs, so the
cache is unit-testable with a fake ``invoke_fn``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


def cache_key(
    model: str, effort: str, thinking_budget: int | None, system_prompt: str, user_input: str
) -> str:
    """sha256 over the FULL decode-determining input. Any change to the model, the effort,
    the thinking budget, the system prompt, or the user input yields a different key — so a
    stale completion can never be returned for a changed request, and an UNCHANGED request
    always hits. Canonical JSON (sorted keys) makes the digest stable across processes."""
    payload = json.dumps(
        {
            "model": model,
            "effort": effort,
            "thinking_budget": thinking_budget,
            "system": system_prompt,
            "user": user_input,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class HarvestCache:
    """A content-addressed cache of LLM completions under ``cache_dir`` (``.harvest_cache/``,
    gitignored). Keyed by :func:`cache_key`; the completion bytes are stored verbatim so a hit
    reproduces the prior run exactly. Tracks hit/miss counts for the reproducibility ledger."""

    cache_dir: Path
    refresh: bool = False
    hits: int = 0
    misses: int = 0

    def complete(
        self,
        system: str,
        user: str,
        *,
        model: str,
        effort: str,
        thinking_budget: int | None,
        invoke_fn: Callable[[str, str], str],
    ) -> str:
        """Return the completion for (system, user) — served from the cache when present,
        else computed via ``invoke_fn`` and stored. ``invoke_fn`` is the ONLY thing that talks
        to Bedrock, so a hit never touches the network. Idempotent for a fixed
        (model, effort, thinking_budget, system, user) tuple."""
        key = cache_key(model, effort, thinking_budget, system, user)
        path = Path(self.cache_dir) / f"{key}.txt"
        if path.exists() and not self.refresh:
            self.hits += 1
            return path.read_text(encoding="utf-8")
        text = invoke_fn(system, user)
        self.misses += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return text

    @property
    def stats(self) -> dict:
        return {"hits": self.hits, "misses": self.misses}
