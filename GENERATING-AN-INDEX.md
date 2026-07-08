# Generating a Tero index for any repo

`tero-mcp-lite` is a **server**, not a **builder** — it only ever reads a committed `index.json`. This
document is the honest, minimal contract that file must satisfy, so any repo (Mycelium or otherwise)
can produce one and drop this package on top of it.

## Where the schema comes from

The schema below is exactly what `crates/mycelium-tero`'s Rust `tero-index` binary emits for Mycelium
itself (see `crates/mycelium-tero/src/model.rs` `TeroIndexItem`/`TeroIndexReport`, and
`crates/mycelium-tero/src/emit.rs`), committed at `docs/tero-index/index.json` in this repo. This
package's `tero_mcp_lite/model.py` reads that exact shape.

## Top-level shape

```json
{
  "generated": "<free-text honesty banner — how this index was produced and its grading>",
  "item_tag": "<the uniform per-row extraction-honesty tag, e.g. 'Empirical/Declared'>",
  "siblings": [
    {
      "name": "api-index",
      "path": "docs/api-index/INDEX.md",
      "covers": "what domain this sibling index owns instead",
      "generator": "how it's regenerated"
    }
  ],
  "items": [ /* array of item rows — see below */ ],
  "flagged": [ /* array of {"item": "...", "reason": "..."} — never-silent extraction gaps */ ]
}
```

- `generated` / `item_tag`: free text, surfaced back to a caller in `identify`. Be honest about how
  the index was built (a line/regex heuristic over source files is `Empirical/Declared`, not
  `Proven` — see the Mycelium house rule this mirrors, CLAUDE.md "the transparency rule").
- `siblings`: optional; pointers to *other* indices you deliberately don't duplicate into this one
  (e.g. a separate symbol index for source code). May be `[]`.
- `items`: **required**, the actual searchable rows.
- `flagged`: optional (defaults to `[]` if absent) but strongly recommended — anything your extractor
  couldn't confidently place goes here instead of being silently dropped.

## One item row

```json
{
  "anchor": "some-stable-slug",
  "family": "doc",
  "kind": "section",
  "id": "RFC-0034",
  "title": "Human-readable title",
  "file": "docs/rfcs/RFC-0034.md",
  "line": 42,
  "status": "Accepted",
  "guarantee_tag": "Proven",
  "summary": "A one-line, verbatim-ish summary — never invented.",
  "epic": "E39-1",
  "depends_on": ["M-010"],
  "doc_refs": ["corpus:RFC-0003"],
  "gh_issue": "2",
  "tag": "Empirical/Declared"
}
```

| Field | Required | Notes |
|---|---|---|
| `anchor` | yes | Globally unique within the index. The citation/deep-link key. |
| `family` | yes | One of `doc`, `research`, `issue`, `changelog`, `skill`. This is a **closed set with a meaningful order** — see "Canonical sort order" below. A row that fits none of these families doesn't belong in this index (or extend `FAMILY_RANK` in `model.py` and document the addition). |
| `kind` | yes | Free-text sub-kind (`rfc`, `adr`, `note`, `section`, `issue`, `epic`, `release`, `entry`, `skill`, `record`, ...). Matched case-insensitively by `query_by_kind`. |
| `id` | no | The source's own id, if it has one. Omit the key entirely rather than sending `null` (though this reader tolerates either). |
| `title` | yes | Display title. |
| `file` | yes | Repo-relative source path. |
| `line` | yes | 1-based source line (integer). |
| `status` | no | A declared status string, if the source has one. Matched case-insensitively by `query_by_status`. |
| `guarantee_tag` | no | The *cited claim's* declared strength (`Exact`/`Proven`/`Empirical`/`Declared`), where the source states one — distinct from `tag` below. |
| `summary` | no | A one-line summary, verbatim-ish from source. `null`/absent is an honest "no summary in source," not a gap to paper over with an invented one. |
| `epic` | no | Issues only: parent epic id. |
| `depends_on` | no | Issues only: array of task ids this one depends on. Only entries resolving to another **issue** row are walkable by `cross_ref`. |
| `doc_refs` | no | Issues only: array of citation strings. Only `corpus:<DOC>[#<anchor>]`-shaped entries are resolvable by `cross_ref` today (an `api:`/`src:` entry is a valid citation but not walkable within this index — it's recorded as an *unresolved edge*, never silently dropped). |
| `gh_issue` | no | Issues only: the GitHub issue number, if resolved. |
| `tag` | yes | The row's own extraction-honesty tag — usually just `item_tag` copied onto every row. |

## Canonical sort order

The committed `items` array **must already be sorted** by `(family, file, line, anchor)`, where
`family` sorts by **declaration rank, not alphabetically**:

```text
doc < research < issue < changelog < skill
```

(This mirrors a Rust `#[derive(Ord)]` on an enum, which ranks by declaration order.) `tero_mcp_lite`
asserts this invariant on every query (`is_canonically_sorted` in `model.py`) and raises loudly if
it's violated — a silently-mis-sorted index would silently corrupt every "canonical order" ordering
claim in an `Explain` trace. If you add a new family, extend `FAMILY_RANK` in `model.py` to match
your own builder's rank, and re-sort your index the same way.

## Minimal example (hand-written, no builder needed)

```json
{
  "generated": "Declared — hand-authored fixture, not extracted",
  "item_tag": "Declared",
  "siblings": [],
  "items": [
    {
      "anchor": "hello-world",
      "family": "doc",
      "kind": "note",
      "id": "N-001",
      "title": "Hello, world",
      "file": "NOTES.md",
      "line": 1,
      "summary": "The very first note in this repo.",
      "tag": "Declared"
    }
  ],
  "flagged": []
}
```

Save that as `index.json`, point `tero-mcp-lite --index index.json` at it, and every tool works.

## Producing one for real

Two supported paths:

1. **Reuse the Rust builder.** If your repo can vendor/build `mycelium-tero`'s `tero-index` binary
   (it's a small, dependency-light Rust crate — see `crates/mycelium-tero/src/index.rs`,
   `walk.rs`, `docs.rs`, `issues.rs`, `changelog.rs`, `skills.rs`), point it at your own corpus
   conventions (or adapt its extractors — it's a corpus-shape-specific walker, not generic).
2. **Write your own extractor.** Any language/tool that emits the shape above works. Keep the same
   honesty discipline: a construct your extractor can't confidently place is a `flagged` entry, not a
   silently-dropped row or an invented field.

Either way, the *server* in this package doesn't care how the file was produced — only that it matches
the schema above.
