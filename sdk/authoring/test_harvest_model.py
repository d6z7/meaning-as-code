"""Unit tests for the Phase-6 harvest model layer: STARTUP model-id validation + the
model-swap dispatch surface. No Bedrock, no AWS — the builder's provider SDKs are deferred,
so validation is testable in isolation and dispatch is asserted by prefix, not by invoking."""

import pytest

from sdk.authoring import harvest_model as hm

# --- model-id shape validation (the startup gate) --------------------------------------------


@pytest.mark.parametrize(
    "model",
    [
        "global.anthropic.claude-opus-4-6-v1",
        "eu.anthropic.claude-sonnet-4-5-v1",
        "us.anthropic.claude-haiku-4-5-v1",
        "openai.gpt-5.6-sol",
        "gpt-5.6-luna",
    ],
)
def test_validate_accepts_known_provider_prefixes(model):
    assert hm.validate_model_id(model) == model


@pytest.mark.parametrize(
    "bad",
    [
        "",
        None,
        "claude-opus-4-6",  # no region/provider prefix
        "anthropic.claude-opus",  # bare 'anthropic.' is not a routable Converse profile prefix
        "bedrock/opus",
        "foo.bar.baz",
    ],
)
def test_validate_fails_loud_on_malformed_id(bad):
    with pytest.raises(ValueError):
        hm.validate_model_id(bad)


def test_is_openai_model_dispatch():
    assert hm.is_openai_model("openai.gpt-5.6-sol")
    assert hm.is_openai_model("gpt-5.6-luna")
    assert not hm.is_openai_model("eu.anthropic.claude-sonnet-4-5-v1")
    assert not hm.is_openai_model("global.anthropic.claude-opus-4-6-v1")


# --- the single builder dispatches on prefix + forwards thinking_budget (Converse only) ------


@pytest.fixture
def fake_okf_aws(monkeypatch):
    """Install a fake ``okf_aws`` module whose ``.model_factory`` records builder calls, so the
    prefix dispatch is testable without langchain / a real Bedrock. Returns the recorder dict."""
    import sys
    import types

    calls = {}

    class _FakeMF:
        def build_bedrock_converse(
            self,
            model,
            effort,
            max_tokens,
            *,
            region,
            botocore_config=None,
            thinking=True,
            thinking_budget=None,
        ):
            calls["converse"] = {
                "model": model,
                "effort": effort,
                "max_tokens": max_tokens,
                "region": region,
                "thinking": thinking,
                "thinking_budget": thinking_budget,
            }
            return "CONVERSE_MODEL"

        def build_mantle_openai(self, model, effort, max_tokens, *, region):
            calls["mantle"] = {
                "model": model,
                "effort": effort,
                "max_tokens": max_tokens,
                "region": region,
            }
            return "MANTLE_MODEL"

    pkg = types.ModuleType("okf_aws")
    pkg.model_factory = _FakeMF()
    monkeypatch.setitem(sys.modules, "okf_aws", pkg)
    monkeypatch.setitem(sys.modules, "okf_aws.model_factory", pkg.model_factory)
    return calls


def test_builder_routes_converse_with_thinking_budget(fake_okf_aws):
    out = hm.build_harvest_model(
        "eu.anthropic.claude-sonnet-4-5-v1",
        "high",
        12000,
        region="eu-central-1",
        thinking_budget=4096,
    )
    assert out == "CONVERSE_MODEL"
    assert "mantle" not in fake_okf_aws  # openai builder must NOT run
    assert (
        fake_okf_aws["converse"]["thinking_budget"] == 4096
    )  # the knob build_model does NOT forward
    assert fake_okf_aws["converse"]["thinking"] is True
    assert fake_okf_aws["converse"]["region"] == "eu-central-1"


def test_builder_routes_openai_to_mantle(fake_okf_aws):
    out = hm.build_harvest_model(
        "openai.gpt-5.6-sol", "xhigh", 16000, region="eu-central-1", thinking_budget=9999
    )
    assert out == "MANTLE_MODEL"
    assert "converse" not in fake_okf_aws  # converse builder must NOT run
    # thinking_budget is Converse-only; the Mantle path ignores it (no mis-encoding).
    assert fake_okf_aws["mantle"]["model"] == "openai.gpt-5.6-sol"
    assert (
        fake_okf_aws["mantle"]["region"] == "us-east-2"
    )  # Mantle default region, not the AWS region


def test_builder_validates_before_dispatch(fake_okf_aws):
    with pytest.raises(ValueError):
        hm.build_harvest_model("not-a-real-id", "high", 12000, region="eu-central-1")
    assert fake_okf_aws == {}  # failed BEFORE any provider builder ran
