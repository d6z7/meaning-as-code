# RULED 2026-10-02 — a projected document's layout is DECLARED and FROZEN

> "i cannto stand that you every time invent new layout for the same document !?!?!? it is either
> you define mandatory rules for the layout or crate tempalte that you will only populate."
> — the operator, 2026-10-02

## The ruling

RULES, not a template. A template for these pages would carry a conditional table and a
two-direction join list, which makes it a second program in a templating language and moves the
drift rather than stopping it. So the layout is **data** — `delivers.<artifact>.shape` in
`guardrails/` — and a renderer **asks** for it.

Rules alone were not enough. They cannot see a sentence reworded, a bullet rephrased or a cell
reordered, which is most of what "a new layout for the same document" actually was. So a second
mechanism: a committed **golden** per document, compared byte for byte. An unintended change fails;
an intended one is `--accept` and a reviewable `git diff tests/golden/` in the commit.

## The three pieces

| piece | what it is |
|---|---|
| `sdk/project/layout.py` | the ONE reader: artifact → ordered sections, which are `always`, the empty sentence, declared table columns, and the renderer the producers name |
| `tools/check_document_layout.py` | the generic gate: the rules on any bundle, the freeze always, `--self-test`, `--accept` |
| `tests/golden/<artifact>/<document>.md` | the frozen documents |

## Declaring a new document's layout

Add it to a `guardrails/` topic — no code:

```yaml
delivers:
  my_page:
    shape:
      empty_section_says: "_Nothing declared for this section._"
      sections:
        - {heading: What it is, required: always}
        - {heading: Where it comes from, required: always}
      fields_table_columns: [column, type, role]      # optional; any `*_columns` key is read
    producers:
      - {tool: sdk/project/my_page.py, role: builds it, renders: documents}
```

Then in the renderer: `LAYOUT = layout.layout("my_page")`, iterate `LAYOUT.sections`, and emit each
through `layout.section(heading, body, LAYOUT.empty_section_says)`. `renders` names a callable on the
producer's own module taking a bundle root and returning `{document name: markdown}` — that is what
makes the artifact checkable. Freeze it once with `--accept` and commit the goldens.

An artifact that declares `sections` and no `renders` is a delivered FILE: `tools/check_page_shape.py`
holds those against the same declaration. The gate prints it as `n/a` **with that reason** rather
than counting it held.

## Why the goldens live beside the tests, cut from the exemplar bundle

They ARE the test's expected value, so `tests/golden/`. They are rendered from
`sdk/authoring/exemplars/bundle` because a golden must be reproducible on any machine, and the only
concept bundles in this repository are the exemplars — a golden cut from a bundle under a private
sources repository would freeze a document nobody else can render. The goldens are never read
back into a page: the rendering keeps one author.

## Verify / accept

```
python3 tools/check_document_layout.py              # rules + freeze
python3 tools/check_document_layout.py --self-test  # 12 cases, one mutant per reject class
python3 tools/check_document_layout.py --accept     # intended change; then git diff tests/golden/
python3 -m pytest tests/test_document_layout.py -q
```

## Open, not fixed here

* `concept_sections` appends a 9th heading, `## Data`, on a bundle with a data plane (measured:
  3 of 17 concepts on contoso5). `delivers.concept_page.shape` does not declare it. The governed
  surface is `page_body`, so the gate holds the body; the pointer is news for the declaration's
  owner — either declare the section or move the pointer inside `Source of record`.
* `sdk/cli/harvest.py:639` calls `knowledge.build(...)`, which the module no longer defines (it was
  rewritten to `project()` earlier the same day). Pre-existing; unrelated to the layout move.
