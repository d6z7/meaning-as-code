#!/usr/bin/env python3
"""harvest_model.py — the harvest's model layer (Phase 6): STARTUP model-id validation and
a single **model-swappable** builder that dispatches on the model-id PREFIX.

* :func:`validate_model_id` — a cheap SHAPE check run at STARTUP (before any Athena /
  Bedrock call) so a typo fails loud for $0 rather than mid-harvest for real money.
* :func:`build_harvest_model` / :func:`make_invoker` — the single construction path.
  It dispatches on the id prefix (``eu.``/``us.``/``global.`` → Bedrock Converse;
  ``openai.``/``gpt-`` → Mantle GPT) and calls the provider builder DIRECTLY. On the
  Converse path it forwards a ``thinking_budget`` knob — the higher-level
  ``okf_aws.model_factory.build_model`` forwards NONE (it hard-wires adaptive
  thinking+effort), so effort alone can't drive a token budget; we call
  ``build_bedrock_converse`` directly to expose it.

The idempotency cache that WRAPS these calls lives in ``sdk.project.harvest_cache`` (the
write-once gate confines SSOT writes to operations.py, so the cache's derived, gitignored
output is authored from the project/derived tree, not from an authoring head). It injects
:func:`make_invoker` as its ``invoke_fn``, so a cache hit never touches the network.

All framework imports (``langchain_*``, ``okf_aws``) are DEFERRED inside the builder /
invoker, so importing this module — and unit-testing validation — never needs the AWS SDKs
or a real Bedrock.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# ---- provider prefixes (the model-swap dispatch surface) -----------------------------------
# Bedrock Converse (Anthropic inference profiles) are region-scoped: eu./us./global.
# Mantle GPT (OpenAI-compatible on Bedrock) are openai./gpt-. These are the ONLY shapes a
# harvest model id may take; anything else is a typo we refuse at startup.
_CONVERSE_PREFIXES = ("eu.", "us.", "global.")
_OPENAI_PREFIXES = ("openai.", "gpt-")
ALLOWED_PREFIXES = _CONVERSE_PREFIXES + _OPENAI_PREFIXES


def is_openai_model(model: str) -> bool:
    """True when ``model`` names a Mantle GPT id (openai./gpt-). Mirrors
    okf_aws.model_factory.is_openai_model but needs no import (used pre-flight)."""
    return isinstance(model, str) and any(model.startswith(p) for p in _OPENAI_PREFIXES)


def validate_model_id(model: str) -> str:
    """Fail loud on a malformed / unknown model id — BEFORE any AWS call.

    Returns the id unchanged when its provider prefix is recognised; raises
    ``ValueError`` otherwise. This is a SHAPE gate (does the id name a provider we can
    route?), not an entitlement check — whether the account may actually invoke the id is
    Bedrock's authority and surfaces at invoke time, per the codebase's no-client-allow-list
    posture. Keeping it to the shape is what lets a brand-new dataset pick any current model
    without us shipping a per-model allow-list.
    """
    if not model or not isinstance(model, str):
        raise ValueError(f"harvest model id must be a non-empty string, got {model!r}")
    if not any(model.startswith(p) for p in ALLOWED_PREFIXES):
        raise ValueError(
            f"unknown/malformed harvest model id {model!r}: expected a provider prefix, one of "
            f"{ALLOWED_PREFIXES} — Bedrock Converse (eu./us./global.anthropic.*) or Mantle GPT "
            f"(openai.*/gpt-*). Set MAC_HARVEST_MODEL / harvest.yaml / --model to a valid id."
        )
    return model


# ---- the single model-swap builder ---------------------------------------------------------

# Mantle GPT lives in us-east-2 / us-west-2 independent of the harvest's AWS_REGION.
_DEFAULT_MANTLE_REGION = "us-east-2"


def build_harvest_model(
    model: str,
    effort: str,
    max_tokens: int,
    *,
    region: str,
    thinking_budget: int | None = None,
    botocore_config: Any = None,
    mantle_region: str | None = None,
):
    """Construct the harvest chat model, dispatching on the model-id prefix.

    * ``openai.``/``gpt-`` → ``build_mantle_openai`` in ``mantle_region`` (GPT reasoning
      effort maps 1:1; ``thinking_budget`` is a Converse-only token-budget concept and is
      not applicable on this path — ignored, not silently mis-encoded).
    * everything else → ``build_bedrock_converse`` in ``region`` with adaptive thinking,
      forwarding ``thinking_budget`` when given (the budget encoding for pre-adaptive
      generations, or an explicit budget the caller wants). ``build_model`` forwards no
      such knob, which is exactly why this path calls the converse builder directly.

    Validated first, so a bad id never reaches the (billable) provider SDK.
    """
    validate_model_id(model)
    from okf_aws import model_factory as mf  # deferred: importing this module stays SDK-free

    if is_openai_model(model):
        return mf.build_mantle_openai(
            model,
            effort,
            max_tokens,
            region=mantle_region or _DEFAULT_MANTLE_REGION,
        )
    return mf.build_bedrock_converse(
        model,
        effort,
        max_tokens,
        region=region,
        botocore_config=botocore_config,
        thinking=True,
        thinking_budget=thinking_budget,
    )


def _content_text(content: Any) -> str:
    """Flatten a LangChain message ``content`` (str | list[block]) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        ).strip()
    return str(content or "")


def make_invoker(
    model: str,
    effort: str,
    max_tokens: int,
    *,
    region: str,
    thinking_budget: int | None = None,
    botocore_config: Any = None,
) -> Callable[[str, str], str]:
    """Return a ``(system, user) -> completion_text`` callable.

    This is the REAL Bedrock/Mantle call, wrapped so it presents the same tiny surface a
    fake presents in tests. All framework imports live inside the returned closure, so a
    caller (and the cache) can hold an invoker without importing langchain until it fires.
    Returns the RAW completion text (no fence-stripping) so the cache stores exactly what
    the model produced and callers apply their own deterministic post-processing.
    """

    def _invoke(system: str, user: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        m = build_harvest_model(
            model,
            effort,
            max_tokens,
            region=region,
            thinking_budget=thinking_budget,
            botocore_config=botocore_config,
        )
        resp = m.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return _content_text(resp.content)

    return _invoke
