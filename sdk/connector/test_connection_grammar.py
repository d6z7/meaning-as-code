"""test_connection_grammar — the connection ENVELOPE, held to its reject classes.

WHY THIS FILE EXISTS
--------------------
The envelope's whole value is a set of things it REFUSES: a third key beside {mode, ref}, a vendor
noun promoted out of `config`, a connector identity written into the overridable deployment file, a
credential handle sitting beside a mode that has nothing to fetch. None of those refusals is visible
in a passing bundle validation, because no bundle in this repository ships a connection file yet --
so without this file the guarantees would be prose, and prose is what this design exists to replace.
Every refusal below would loosen SILENTLY under a later "just add one more key" edit.

The accept cases matter exactly as much, and for a measured reason: the failure this stage is
forbidden to produce is a currently-green manifest turning red. `test_live_connector_values_still_
validate` pins the two values actually found in the estate.

WHAT THIS FILE DELIBERATELY DOES NOT TEST
-----------------------------------------
Anything touching `answerable`. That evaluation is blocked pending an operator ruling, nothing here
reads or writes it, and a test asserting over it would be this stage quietly doing the blocked half.

Nor does it test ROUTING: nothing yet routes a connection file to $defs/ConnectionFile, so these
definitions are reachable by name and not yet applied by validate_schema.py. That is stated in
sdk/connector/README.md rather than papered over -- a definition nothing enumerates is a definition
nothing applies, and a test that implied otherwise would be the false green.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

_ROOT = Path(__file__).resolve().parent.parent.parent
_SCHEMA = json.loads((_ROOT / "mac.schema.json").read_text(encoding="utf-8"))
_CONNECTOR_DIR = _ROOT / "sdk" / "connector"


def _validator(which: str) -> Draft202012Validator:
    """A validator for ONE $def, the way tools/validate_schema.py:292 builds one -- the root `oneOf`
    is dropped, because that is how the real gate validates and a test that validated differently
    would be testing a schema nobody runs."""
    s = dict(_SCHEMA)
    s.update(_SCHEMA["$defs"][which])
    s.pop("oneOf", None)
    return Draft202012Validator(s)


def _accepts(which: str, doc) -> bool:
    return not list(_validator(which).iter_errors(doc))


# ---------------------------------------------------------------------------
# $defs/connectorRef -- pattern, never an enum
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("value", [
    "mac.connector.athena",             # measured live, twice, in the estate
    "mac.connector.athena/2",           # a pinned config-contract major
    "mac.connector.duckdb/1",
    "acme.connector.example/1",         # third party: legal grammar, not a framework reference
    "mac.connector.demo",               # the demo-gate fixture must stay valid
])
def test_connector_ref_accepts(value):
    assert _accepts("connectorRef", value)


@pytest.mark.parametrize("value", [
    "./tools/conn.py",                  # code injection wearing a spelling mistake
    "/etc/passwd",
    "../../outside/conn.py",
    "mac.connector.Athena",             # case is part of the identity
    "mac.connector.athena/",            # a major marker with no major
    "mac.connector.athena/v2",          # the major is an integer, not a label
    "mac.connector",                    # a namespace is not an id
    "athena",                           # a bare engine name is not an id
])
def test_connector_ref_rejects(value):
    assert not _accepts("connectorRef", value), f"{value!r} must not be a legal connector id"


def test_a_path_shaped_connector_is_refused_by_construction():
    """§6.1: a name that looks like a path is a contract violation, not a typo. The point is that the
    PATTERN refuses it, so no separate 'is this a path?' check can be forgotten or removed."""
    for path_shaped in ("./c.py", "c/../../etc/shadow", "~/conn.py", "file:///tmp/c.py"):
        assert not _accepts("connectorRef", path_shaped)


# ---------------------------------------------------------------------------
# $defs/credentialRef -- exactly two keys, and a handle is never a value
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("doc", [
    {"mode": "ambient"},
    {"mode": "ambient", "ref": None},
    {"mode": "named_profile", "ref": "a-profile-name"},
    {"mode": "secret_manager", "ref": "a/path/in/the/manager"},
    {"mode": "client_certificate", "ref": "a-certificate-handle"},
    {"mode": "interactive"},
    {"mode": "none"},
])
def test_credential_ref_accepts(doc):
    assert _accepts("credentialRef", doc)


@pytest.mark.parametrize("doc,why", [
    ({"mode": "ambient", "password": "hunter2xyz"}, "a third key spelled as a password"),
    ({"mode": "ambient", "value": "hunter2xyz"}, "a third key spelled `value` -- the measured hole"),
    ({"mode": "ambient", "aws_secret_access_key": "x"}, "a third key spelled as a driver secret"),
    ({"mode": "ambient", "token": "x"}, "a third key the residual scan would MISS"),
    ({"mode": "named_profile"}, "a mode that names something to fetch, with no handle"),
    ({"mode": "secret_manager", "ref": ""}, "an empty handle is not a handle"),
    ({"mode": "ambient", "ref": "a-real-handle"}, "a handle beside a mode with nothing to fetch"),
    ({"mode": "plaintext", "ref": "x"}, "a mode outside the closed set"),
    ({"mode": "aws-chain"}, "a vendor spelling is a connector alias, never canon"),
    ({"ref": "x"}, "a handle with no mode"),
    ({}, "an empty credentials block says nothing"),
])
def test_credential_ref_rejects(doc, why):
    assert not _accepts("credentialRef", doc), why


def test_there_is_nowhere_to_put_a_secret():
    """THE structural guarantee, asserted as a property rather than as a list of names: whatever a
    third key is called, it has nowhere to sit. This is what the security posture rests on, and it is
    why it survives secret names MAC has never heard of -- unlike the residual scan over `config:`,
    which is AWS-shaped by construction and misses client_secret, api_key, token and passphrase."""
    for key in ("password", "passwd", "secret", "client_secret", "api_key", "apiKey", "token",
                "auth_token", "passphrase", "private_key_path", "credential", "value", "pwd"):
        assert not _accepts("credentialRef", {"mode": "ambient", key: "anything-at-all"}), key


# ---------------------------------------------------------------------------
# $defs/ConnectionFile -- the envelope, and where the payload begins
# ---------------------------------------------------------------------------
def test_envelope_accepts_a_credentialed_remote_shape():
    assert _accepts("ConnectionFile", {
        "spec_version": "mac.connector/1",
        "credentials": {"mode": "ambient"},
        "config": {"region": "eu-west-1", "workgroup": "a-workgroup"},
    })


def test_envelope_accepts_a_connector_with_no_credential_at_all():
    """The DuckDB case, and the reason `credentials` is not in `required`: absence is the honest
    spelling of 'no credential required', and forcing {mode: none} would make a bundle restate a fact
    its own silence already states."""
    assert _accepts("ConnectionFile", {
        "spec_version": "mac.connector/1",
        "config": {"database": "local.duckdb"},
    })


@pytest.mark.parametrize("doc,why", [
    ({}, "an empty file is a stated reject class, and carries no forbidden key to trip on"),
    ({"credentials": {"mode": "ambient"}}, "no spec_version -- this is the legacy flat shape"),
    ({"spec_version": "1"}, "an unversioned spec_version"),
    ({"spec_version": "mac.container/1"}, "the wrong spec family"),
    ({"spec_version": "mac.connector/1", "aws_secret_access_key": "x"},
     "a driver secret at the top level"),
    ({"spec_version": "mac.connector/1", "region": "eu-west-1"},
     "a vendor noun promoted OUT of config and into the envelope"),
    ({"spec_version": "mac.connector/1", "workgroup": "w"}, "likewise"),
    ({"spec_version": "mac.connector/1", "connector": "mac.connector.athena"},
     "the connector identity in the OVERRIDABLE file -- an override may change where you point, "
     "never what code runs"),
])
def test_envelope_rejects(doc, why):
    assert not _accepts("ConnectionFile", doc), why


def test_the_payload_is_the_only_open_object():
    """`config` is deliberately unconstrained -- that IS the delegation line. If a later edit types
    these keys, the grammar has learned one vendor's nouns and every new engine becomes a schema
    bump. This test fails loudly if that happens."""
    for payload in ({"region": "x", "workgroup": "y", "catalog": "z"},
                    {"database": "f.duckdb", "read_only": True},
                    {"a_noun_mac_has_never_heard_of": {"nested": ["anything"]}}):
        assert _accepts("ConnectionFile",
                        {"spec_version": "mac.connector/1", "config": payload})


# ---------------------------------------------------------------------------
# The manifest key, and the values that are already in the wild
# ---------------------------------------------------------------------------
def test_runtime_is_no_longer_an_untyped_object():
    rt = _SCHEMA["$defs"]["ProjectFile"]["properties"]["runtime"]
    assert rt.get("additionalProperties") is False, "runtime must be closed"
    assert set(rt["properties"]) == {"source", "connector", "connection", "interpreter",
                                     "model_catalog"}
    assert "required" not in rt, ("no runtime key may be required -- a measured manifest carries "
                                  "only {source, connection, connector}")


def test_a_credential_has_nowhere_to_sit_in_the_manifest_either():
    """The measured hole §5.2 names: `runtime: {credentials: {mode: plaintext, value: hunter2xyz}}`
    validated CLEAN against the untyped object, and the secrets gate missed it because the manifest
    is allowlisted and the key is spelled `value`."""
    pf = _validator("ProjectFile")
    doc = {"planes": {"data": "data"},
           "runtime": {"credentials": {"mode": "plaintext", "value": "hunter2xyz"}}}
    assert list(pf.iter_errors(doc)), "a credential inside runtime: must not validate"


def test_a_manifest_with_no_runtime_block_is_still_well_formed():
    """contoso, tpch, shop and 16 others. Well-formed, readable, renderable -- and not answerable."""
    assert not list(_validator("ProjectFile").iter_errors({"planes": {"data": "data"}}))


@pytest.mark.parametrize("value", ["mac.connector.athena"])
def test_live_connector_values_still_validate(value):
    """Measured across the 27 reachable mac.project.yaml manifests: 2 already declare
    runtime.connector, both with this value. Typing the key must not turn either red."""
    doc = {"planes": {"data": "data"}, "runtime": {"source": "s", "connection": "connection.yaml",
                                                   "connector": value}}
    assert not list(_validator("ProjectFile").iter_errors(doc))


# ---------------------------------------------------------------------------
# The shipped index and the two payload contracts
# ---------------------------------------------------------------------------
#: JSON has no comment syntax, and this codebase's style is that the WHY lives beside the thing. A
#: leading underscore is the conventional workaround, and `index.json` is DATA shipped in the wheel —
#: a reader who opens it does not have the README to hand. So metadata keys are permitted and
#: skipped, rather than the explanation being moved somewhere the reader is not.
def _connector_ids(index: dict) -> list:
    return [k for k in index if not k.startswith("_")]


def test_index_entries_resolve_to_a_real_and_valid_schema():
    index = json.loads((_CONNECTOR_DIR / "index.json").read_text(encoding="utf-8"))
    assert _connector_ids(index), "an index over zero connectors is not an index"
    ref = _validator("connectorRef")
    for cid in _connector_ids(index):
        entry = index[cid]
        base = cid.split("/")[0]
        assert not list(ref.iter_errors(cid)) or not list(ref.iter_errors(base)), cid
        target = _CONNECTOR_DIR / entry["config_schema"]
        assert target.is_file(), f"{cid} names a config schema that is not there: {target}"
        Draft202012Validator.check_schema(json.loads(target.read_text(encoding="utf-8")))


def test_every_first_party_id_in_the_index_is_mac_namespaced():
    """Only this repository's own index may make a `mac.`-prefixed id real. An id in another
    namespace appearing here would be this distribution vouching for someone else's code."""
    index = json.loads((_CONNECTOR_DIR / "index.json").read_text(encoding="utf-8"))
    for cid in _connector_ids(index):
        assert cid.startswith("mac.connector."), cid


def test_a_metadata_key_is_permitted_but_a_bogus_id_is_not():
    """The skip must not become a hole. `_comment` is metadata; `not.an.id` is a claim that some
    connector exists, and the index is the only thing that makes a first-party id real."""
    assert _connector_ids({"_comment": "x", "mac.connector.duckdb/1": {}}) == ["mac.connector.duckdb/1"]
    assert _connector_ids({"not.an.id": {}}) == ["not.an.id"]      # NOT skipped — it must be judged


def _payload_validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(
        json.loads((_CONNECTOR_DIR / "schemas" / name).read_text(encoding="utf-8")))


def test_an_account_id_can_never_be_sealed_into_a_bundle():
    """Typed as null, so 'NEVER shipped' is checkable rather than a comment beside a free-text key."""
    v = _payload_validator("athena.1.json")
    assert not list(v.iter_errors({"region": "eu-west-1", "workgroup": "w", "account": None}))
    assert list(v.iter_errors({"region": "eu-west-1", "workgroup": "w",
                               "account": "123456789012"}))


def test_neither_payload_admits_a_secret():
    for name in ("athena.1.json", "duckdb.1.json"):
        v = _payload_validator(name)
        base = ({"region": "eu-west-1", "workgroup": "w"} if name.startswith("athena")
                else {"database": "f.duckdb"})
        for key in ("password", "secret", "api_key", "token", "aws_secret_access_key"):
            assert list(v.iter_errors({**base, key: "x"})), f"{name} admitted {key}"


def test_the_second_connector_is_not_athena_shaped():
    """THE KILL CRITERION, as a test. If making a second engine fit ever requires an Athena noun,
    the seam was never a seam. DuckDB's contract must refuse every one of them."""
    v = _payload_validator("duckdb.1.json")
    assert not list(v.iter_errors({"database": "local.duckdb"}))
    for alien in ("region", "workgroup", "catalog", "output", "glue_databases", "account"):
        assert list(v.iter_errors({"database": "local.duckdb", alien: "x"})), \
            f"an engine noun from another connector leaked into duckdb: {alien}"


def test_duckdb_requires_a_database():
    """An embedded engine that silently opens an empty in-memory database answers every question
    with zero rows and no error -- the quietest possible wrong answer."""
    assert list(_payload_validator("duckdb.1.json").iter_errors({}))


def test_the_core_grammar_never_learned_the_payload_nouns():
    """The line, asserted directly against the file. These nouns live in sdk/connector/ and nowhere
    above it; if one appears as a KEY in mac.schema.json, the canon has become a vendor catalogue."""
    keys = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "properties" and isinstance(v, dict):
                    keys.update(v)
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(_SCHEMA)
    for noun in ("region", "workgroup", "catalog", "glue_databases", "output_location",
                 "read_only", "extensions"):
        assert noun not in keys, f"the core grammar has learned a connector's noun: {noun}"
