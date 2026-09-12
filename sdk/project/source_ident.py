#!/usr/bin/env python3
"""source_ident.py — resolve a source's IDENTITY strings from its ``mac.project.yaml`` so
the generic instrument (data-plane authoring prompt, edges, the read-view projector) carries
NO source literal. De-ACMEs the harvest: instead of a hardcoded ``'ACME'`` / ``'acme.'`` /
a hardcoded source name, each generic step reads what THIS project is from its manifest.

Resolved fields:
  * ``data_domain`` — ``metadata.data_domain`` (e.g. ``sales``)
  * ``dataset``     — ``metadata.dataset``     (e.g. ``orders``)
  * ``label``       — the human/source label: ``runtime.source``, else the first key under
    ``sources.yaml:sources``, else the dataset upper-cased (e.g. ``ACME``)
  * ``view_schema`` — the curated serving-view database/schema the ontology binds to:
    ``connection.yaml:view_schema`` (else ``view_database``), else ``dataset``
    (for ``<domain>/<dataset>`` this is ``<dataset>`` — matches the data-plane prompt's ``schema: <dataset>`` /
    ``relation: <dataset>.<view>``)

REFACTOR-SAFE: for an existing project this resolves to
``(acme, acme, ACME, acme)`` — exactly the strings that were hardcoded — so the projection is
BYTE-IDENTICAL. Missing manifest fields fall back gracefully (a bare tmp dir never crashes).
Deterministic, stdlib+yaml only, no AWS.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SourceIdent:
    data_domain: str
    dataset: str
    label: str
    view_schema: str


def _read_yaml(p: Path) -> dict:
    try:
        return yaml.safe_load(Path(p).read_text()) or {}
    except Exception:
        return {}


def resolve(content_root) -> SourceIdent:
    """Resolve the identity strings for the source rooted at ``content_root``."""
    cr = Path(content_root)
    mp = _read_yaml(cr / "mac.project.yaml")
    meta = mp.get("metadata") or {}
    data_domain = str(meta.get("data_domain") or cr.parent.name)
    dataset = str(meta.get("dataset") or cr.name)

    label = (mp.get("runtime") or {}).get("source")
    if not label:
        srcs = _read_yaml(cr / "sources.yaml").get("sources")
        if isinstance(srcs, dict) and srcs:
            label = next(iter(srcs))
    if not label:
        label = dataset.upper()

    conn = _read_yaml(cr / "connection.yaml")
    view_schema = conn.get("view_schema") or conn.get("view_database") or dataset

    return SourceIdent(
        data_domain=data_domain,
        dataset=dataset,
        label=str(label),
        view_schema=str(view_schema),
    )
