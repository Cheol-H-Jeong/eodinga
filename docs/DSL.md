# Query DSL Cheatsheet

The v0.1 parser is lexical and local-only. Spaces mean `AND`, `|` means `OR`, and a leading `-` negates a term or group.

| Pattern | Meaning | Example |
| --- | --- | --- |
| plain term | Match filename, path, or parsed text | `report` |
| phrase | Exact text span | `"design review"` |
| regex | Regex search with optional flags | `/todo|fixme/i` |
| regex alias | Explicit path/name regex operator | `regex:/todo|fixme/i` |
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
-(draft | scratch) /todo|fixme/i
```

## Boolean And Negation Patterns

| Goal | Query | Why it works |
| --- | --- | --- |
| require two terms | `invoice receipt` | spaces are implicit `AND` |
| accept either branch | `invoice | receipt` | `|` keeps either side as a valid match |
| exclude one noisy subtree | `report -path:archive` | term-level negation removes the next operator only |
| exclude either grouped branch | `-(draft | scratch) ext:md` | group negation applies to the whole parenthesized branch |
| combine groups with a structural filter | `(invoice | receipt) is:file` | the structural operator still applies after the grouped match |

If a query feels ambiguous, add parentheses. The parser is predictable, but explicit grouping is easier to review and easier to debug later.

## Regex Forms

| Form | Example | Use it when |
| --- | --- | --- |
| literal regex term | `/todo|fixme/i` | you want a regex without toggling global regex mode |
| operator-style regex alias | `regex:/todo|fixme/i path:src` | you want the query to read like the other operators |
| plain-term regex mode | `regex:true report-\\d+` | several following plain terms should be interpreted as regex path/name patterns |

- Supported flags are `i`, `m`, and `s`.
- Embedded `/` characters stay valid inside the pattern when escaped, for example `/api\\/v1\\/health/i`.
- Regex literals and `regex:/pattern/flags` stay local to the query; `regex:true` changes how plain terms are read until another `regex:` operator overrides it.

## Operator Notes

- Path/name terms are case-insensitive unless `case:true` is set.
- Content operators only match indexed document text; unsupported files fall back to filename/path search.
- `date:`, `modified:`, and `created:` accept `today`, `yesterday`, `this-week`, `this-month`, a single ISO date, open-ended ISO ranges, full ISO ranges, and exact ISO datetimes.
- `size:` comparisons use binary suffixes, so `10M` means `10 * 1024 * 1024` bytes.
- `is:duplicate` matches entries that share a content hash with at least one other indexed file.
- `is:file` matches regular files only, `is:dir` matches non-symlink directories only, and `is:symlink` remains available when you want the link entries themselves.
- `is:empty` matches zero-byte files and directories with no indexed descendants.
- `regex:true` only changes how plain terms are interpreted; explicit `/pattern/flags` literals still work without it.
- `regex:/pattern/flags` is an explicit alias for a path/name regex term when you want the query to read like an operator list.
- Negation applies to the next term or the entire parenthesized group.

## Practical Limits

- Regex terms are evaluated against the candidate set after SQL filtering, so broad regex queries are naturally slower than indexed term searches.
- `content:` and plain quoted phrases need content indexing enabled for document-body matches.
- Exact duplicate detection depends on parsed content and stored hashes; unsupported formats still participate in filename/path search but may not be marked as duplicates.
