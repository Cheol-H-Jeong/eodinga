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

## Operator Matrix

| Operator | Accepted values | Notes |
| --- | --- | --- |
| `ext:` | extension token such as `pdf`, `md`, `py` | Matches the normalized stored extension, without a leading dot. |
| `path:` | substring or quoted phrase | Best when combined with a positive term so broad path-only scans stay cheap. |
| `content:` | substring or quoted phrase | Requires parsed content; unsupported files still participate in name/path search only. |
| `size:` | `>`, `>=`, `<`, `<=`, `=`, or `A..B` with `B/K/M/G/T` suffixes | `size:100..500K` and `size:>10M` both use binary units. |
| `date:` / `modified:` / `created:` | relative macro, ISO date, ISO datetime, open or closed range | Range endpoints may mix absolute and relative values. |
| `is:` | `file`, `dir`, `symlink`, `empty`, `duplicate` | Structural filters can be stacked, such as `is:dir is:empty`. |
| `case:` | `true`, `false` | Affects term and phrase matching; explicit regex literals keep their own flags. |
| `regex:` | `true`, `false`, or `/pattern/flags` | Use the literal form when you want regex flags attached to one term only. |

## Regex Flags

- `i`: case-insensitive regex matching such as `regex:/todo|fixme/i`
- `m`: multi-line anchors for line-oriented content scans such as `regex:/^TODO:/m`
- `s`: dot-all mode when a pattern needs to cross newline boundaries

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

## Grouping and Negation Patterns

```text
(invoice | receipt) ext:pdf
-(archive | backup) path:projects
date:last-month -(is:duplicate | path:tmp)
```

Use parentheses when the exclusion or OR branch should stay logically tied together. Without grouping, negation only applies to the next term.

## Operator Notes

- Path/name terms are case-insensitive unless `case:true` is set.
- Content operators only match indexed document text; unsupported files fall back to filename/path search.
- `date:`, `modified:`, and `created:` accept `today`, `yesterday`, `this-week`, `this-month`, a single ISO date, open-ended ISO ranges, full ISO ranges, and exact ISO datetimes.
- `size:` comparisons use binary suffixes, so `10M` means `10 * 1024 * 1024` bytes.
- `is:duplicate` matches entries that share a content hash with at least one other indexed file.
- `is:file`, `is:dir`, `is:symlink`, and `is:empty` are also available for structural filtering.
- `regex:true` only changes how plain terms are interpreted; explicit `/pattern/flags` literals still work without it.
- Negation applies to the next term or the entire parenthesized group.

## Practical Limits

- Regex terms are evaluated against the candidate set after SQL filtering, so broad regex queries are naturally slower than indexed term searches.
- `content:` and plain quoted phrases need content indexing enabled for document-body matches.
- Exact duplicate detection depends on parsed content and stored hashes; unsupported formats still participate in filename/path search but may not be marked as duplicates.
