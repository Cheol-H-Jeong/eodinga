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

## Evaluation Rules

1. Parentheses bind first.
2. `-` negates the next term or parenthesized group.
3. Adjacent terms combine with `AND`.
4. `|` joins sibling branches with `OR`.

Practical examples:

```text
invoice receipt
-path:node_modules ext:py
(invoice | receipt) ext:pdf
-(path:build | path:dist) report
```

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
-(path:build | path:dist) ext:py
case:true README
```

## Regex And Escaping

- Use `/pattern/flags` for explicit regex literals, for example `regex:/todo|fixme/im`.
- Supported regex flags are `i`, `m`, and `s`.
- Use `regex:true` when you want plain terms to compile as regex without `/.../` delimiters.
- Escape `/` inside regex literals as `\/`.
- Escape `"` inside quoted phrases as `\"`.
- Backslashes stay significant in regex mode, so Windows-style path filters often read better as quoted literals than as regex.

Examples:

```text
regex:/src\/(core|query)\//i
path:"C:\\Users\\me\\Documents"
content:"said \"ship it\""
regex:true report-\d{4}
```

## Operator Matrix

| Operator | Accepts | Notes |
| --- | --- | --- |
| `ext:` | extension without leading `.` | case-insensitive unless `case:true` is set |
| `path:` | plain term, phrase, or regex literal | matches normalized stored paths |
| `content:` | plain term or phrase | requires content indexing support for body matches |
| `size:` | comparison (`>10M`, `<=1K`) or range (`100K..500K`) | suffixes are binary units |
| `date:` | relative macro, ISO day, ISO datetime, or ISO range | targets the primary timestamp field |
| `modified:` / `created:` | same date syntax as `date:` | targets a specific timestamp column |
| `is:` | `file`, `dir`, `symlink`, `empty`, `duplicate` | `duplicate` depends on stored content hashes |
| `case:` | `true` or `false` | toggles case-sensitive matching for plain terms |
| `regex:` | `true`, `false`, or `/pattern/flags` | `true` promotes plain terms into regex mode |

## Operator Notes

- Path/name terms are case-insensitive unless `case:true` is set.
- Content operators only match indexed document text; unsupported files fall back to filename/path search.
- `date:`, `modified:`, and `created:` accept `today`, `yesterday`, `this-week`, `this-month`, a single ISO date, open-ended ISO ranges, full ISO ranges, and exact ISO datetimes.
- `size:` comparisons use binary suffixes, so `10M` means `10 * 1024 * 1024` bytes.
- `is:duplicate` matches entries that share a content hash with at least one other indexed file.
- `regex:true` only changes how plain terms are interpreted; explicit `/pattern/flags` literals still work without it.
- Negation applies to the next term or the entire parenthesized group.

## Practical Limits

- Regex terms are evaluated against the candidate set after SQL filtering, so broad regex queries are naturally slower than indexed term searches.
- `content:` and plain quoted phrases need content indexing enabled for document-body matches.
- Exact duplicate detection depends on parsed content and stored hashes; unsupported formats still participate in filename/path search but may not be marked as duplicates.

## Troubleshooting Query Shape

| Symptom | First adjustment |
| --- | --- |
| Too many results | add `ext:`, `path:`, `size:`, or a date filter before reaching for regex |
| Phrase not matching body text | confirm content indexing is enabled, then retry with `content:"..."` |
| Regex feels slow | narrow with `path:` or `ext:` first so fewer candidates reach fallback evaluation |
| Case-sensitive term is missed | add `case:true` before the affected term |
| Exclusion removes too much | wrap the excluded branch in parentheses to make the negation boundary explicit |
