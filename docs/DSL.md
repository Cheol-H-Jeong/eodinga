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
| type filter | File, dir, symlink, empty, or duplicate | `is:empty` |
| case mode | Toggle case-sensitive matching | `case:true README` |
| regex mode | Promote plain terms into regex path/name filters | `regex:true report-\\d+` |
| negation | Exclude a term or operator | `-path:node_modules` |
| grouping | Combine branches safely | `(invoice | receipt) ext:pdf` |

## Relative Dates

- `date:today`
- `date:yesterday`
- `date:this-week`
- `date:last-week`
- `date:this-month`
- `date:last-month`
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

## Operator Notes

- Path/name terms are case-insensitive unless `case:true` is set.
- Content operators only match indexed document text; unsupported files fall back to filename/path search.
- `date:`, `modified:`, and `created:` accept `today`, `yesterday`, `this-week`, `this-month`, a single ISO date, open-ended ISO ranges, full ISO ranges, and exact ISO datetimes.
- `size:` comparisons use binary suffixes, so `10M` means `10 * 1024 * 1024` bytes.
- `is:duplicate` matches entries that share a content hash with at least one other indexed file.
- `is:file` matches regular files only, `is:dir` matches non-symlink directories only, and `is:symlink` remains available when you want the link entries themselves.
- `is:empty` matches zero-byte files and directories with no indexed descendants.
- `regex:true` only changes how plain terms are interpreted; explicit `/pattern/flags` literals still work without it.
- Negation applies to the next term or the entire parenthesized group.

## Precedence And Scoping

- Spaces are implicit `AND`, so `ext:pdf invoice` means both constraints must match.
- `|` splits OR branches at the current group level, so `(invoice | receipt) ext:pdf` is safer than `invoice | receipt ext:pdf`.
- A leading `-` only negates the next atom unless you wrap the branch: `-path:cache report` differs from `-(path:cache report)`.
- Structured operators keep their own scope even when `regex:true` is enabled; `path:docs regex:true report-[0-9]+` still treats `path:docs` as a literal path filter.

## Debugging Queries

- If a query returns too many filename hits, move the critical term into `content:` or quote it as a phrase.
- If a regex feels broader than expected, replace `regex:true` with explicit field-scoped literals such as `content:/todo|fixme/i`.
- If a date filter feels off around midnight, remember relative windows use the local machine timezone, not UTC day boundaries.
- If `is:file` or `is:dir` misses a symlink entry, use `is:symlink`; the structural filters are intentionally strict about regular files versus real directories.

## Practical Limits

- Regex terms are evaluated against the candidate set after SQL filtering, so broad regex queries are naturally slower than indexed term searches.
- `content:` and plain quoted phrases need content indexing enabled for document-body matches.
- Exact duplicate detection depends on parsed content and stored hashes; unsupported formats still participate in filename/path search but may not be marked as duplicates.
