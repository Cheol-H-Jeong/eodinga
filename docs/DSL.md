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

Calendar macros expand in local time. Use explicit ISO ranges when you need cross-timezone reproducibility in scripts or release notes.

## Structural Filters

| Filter | Meaning | Example |
| --- | --- | --- |
| `is:file` | regular files only | `is:file ext:md` |
| `is:dir` | directories only | `is:dir roadmap` |
| `is:symlink` | symbolic links only | `is:symlink path:bin` |
| `is:empty` | zero-byte files or empty directories | `is:empty -is:dir` |
| `is:duplicate` | content-hash duplicates with at least one peer | `is:duplicate size:>1M` |

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

## Regex Flags

| Flag | Meaning | Example |
| --- | --- | --- |
| `i` | case-insensitive | `regex:/todo|fixme/i` |
| `m` | `^` and `$` match line boundaries | `regex:/^TODO:/m content:notes` |
| `s` | `.` matches newlines | `regex:/release.*checklist/s` |

Flags follow the trailing delimiter, so `/pattern/im` is valid while bare `regex:true` changes how plain terms are interpreted.

## Operator Notes

- Path/name terms are case-insensitive unless `case:true` is set.
- Content operators only match indexed document text; unsupported files fall back to filename/path search.
- `date:`, `modified:`, and `created:` accept `today`, `yesterday`, `this-week`, `this-month`, a single ISO date, open-ended ISO ranges, full ISO ranges, and exact ISO datetimes.
- `size:` comparisons use binary suffixes, so `10M` means `10 * 1024 * 1024` bytes.
- `is:duplicate` matches entries that share a content hash with at least one other indexed file.
- `is:file`, `is:dir`, `is:symlink`, and `is:empty` are also available for structural filtering.
- `regex:true` only changes how plain terms are interpreted; explicit `/pattern/flags` literals still work without it.
- Negation applies to the next term or the entire parenthesized group.
- Group-level negation is valid, so `-(invoice | receipt) ext:pdf` excludes both branches before the extension filter is applied.
- Phrase search stays lexical; it can cross normalized token boundaries in fallback scans, but it does not become semantic matching.

## Practical Limits

- Regex terms are evaluated against the candidate set after SQL filtering, so broad regex queries are naturally slower than indexed term searches.
- `content:` and plain quoted phrases need content indexing enabled for document-body matches.
- Exact duplicate detection depends on parsed content and stored hashes; unsupported formats still participate in filename/path search but may not be marked as duplicates.
