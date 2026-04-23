# Query DSL Cheatsheet

The v0.1 parser is lexical and local-only. Spaces mean `AND`, `|` means `OR`, and a leading `-` negates a term or group.

| Pattern | Meaning | Example |
| --- | --- | --- |
| plain term | Match filename, path, or parsed text | `report` |
| phrase | Exact text span | `"design review"` |
| regex | Regex search with optional flags | `/todo|fixme/i` |
| extension | Restrict by file extension | `ext:pdf invoice` |
| path filter | Restrict to a path substring | `path:projects release` |
| content filter | Require parsed document text | `content:"launch checklist"` |
| size filter | Compare byte size with `B/K/M/G/T` suffixes | `size:>10M` |
| date filter | Relative or ISO date windows | `date:this-week` |
| timestamp alias | Target modified or created timestamps directly | `modified:today`, `created:2026-04-23` |
| type filter | File, dir, symlink, or duplicate | `is:duplicate` |
| case mode | Toggle case-sensitive matching | `case:true README` |
| regex mode | Promote plain terms into regex path/name filters | `regex:true report-\\d+` |
| negation | Exclude a term or operator | `-path:node_modules` |
| grouping | Combine branches safely | `(invoice | receipt) ext:pdf` |

## Relative Dates

- `date:today`
- `date:yesterday`
- `date:this-week`
- `date:this-month`
- `date:2026-04-23`
- `date:2026-04-01..2026-04-23`
- `date:2026-04-01..`
- `created:..2026-04-23`
- `modified:2026-04-23T09:15:30+00:00`

## Common Combos

```text
ext:pdf content:"release notes"
size:>10M date:this-month
modified:today created:2026-04-23
date:2026-04-01.. modified:..2026-04-23
modified:2026-04-23T09:15:30+00:00
regex:true report-\d+
-is:duplicate -path:node_modules
(invoice | receipt) ext:pdf
regex:/launch|ship/i path:docs
```

## Query Building Patterns

| Goal | Pattern | Notes |
| --- | --- | --- |
| Restrict all terms to one tree | `path:docs (release | changelog)` | `path:` compiles early, so this is cheaper than broad regex. |
| Exclude noisy folders | `term -path:node_modules -path:.git` | Negation applies to each following operator or group. |
| Keep one branch positive and another negative | `(invoice | receipt) -ext:tmp` | Grouping prevents `|` from leaking across unrelated terms. |
| Search timestamps precisely | `modified:2026-04-23T09:15:30+00:00` | Datetime values stay exact; they do not round to whole days. |
| Use regex only where needed | `path:src /todo|fixme/i` | Prefer indexed terms plus one regex over `regex:true` for the whole query. |
| Find empty files but not folders | `is:empty -is:dir` | `is:empty` includes zero-byte files and empty directories. |

## Operator Notes

- Path/name terms are case-insensitive unless `case:true` is set.
- Content operators only match indexed document text; unsupported files fall back to filename/path search.
- `date:`, `modified:`, and `created:` accept `today`, `yesterday`, `this-week`, `this-month`, a single ISO date, open-ended ISO ranges, full ISO ranges, and exact ISO datetimes.
- `size:` comparisons use binary suffixes, so `10M` means `10 * 1024 * 1024` bytes.
- `is:duplicate` matches entries that share a content hash with at least one other indexed file.
- `regex:true` only changes how plain terms are interpreted; explicit `/pattern/flags` literals still work without it.
- Negation applies to the next term or the entire parenthesized group.

## Execution Hints

- Prefer structured filters first: `ext:`, `path:`, `date:`, and `size:` keep the candidate set small before phrase or regex evaluation.
- Plain quoted phrases can match across token boundaries in indexed content, but still require content indexing to see document-body text.
- Broad regex queries are evaluated after candidate fetch, so pair them with `path:` or `ext:` whenever possible.
- `--root PATH` on `eodinga search` scopes the search surface without changing the query text, which is useful for scripts that reuse one query against several roots.

## Practical Limits

- Regex terms are evaluated against the candidate set after SQL filtering, so broad regex queries are naturally slower than indexed term searches.
- `content:` and plain quoted phrases need content indexing enabled for document-body matches.
- Exact duplicate detection depends on parsed content and stored hashes; unsupported formats still participate in filename/path search but may not be marked as duplicates.
