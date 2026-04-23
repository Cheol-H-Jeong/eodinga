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

## Operator Precedence

1. Parenthesized groups evaluate first.
2. A leading `-` negates the next term or the whole parenthesized group.
3. Adjacent terms combine with implicit `AND`.
4. `|` joins sibling branches as `OR`.

Examples:

```text
invoice ext:pdf | ext:docx
(invoice ext:pdf) | ext:docx
-(ext:log | ext:tmp) report
-path:cache report
```

That means `invoice ext:pdf | ext:docx` is read as `(invoice AND ext:pdf) OR ext:docx`. Use parentheses whenever you want a whole branch negated or OR-ed together.

## Relative Dates

- `date:today`
- `date:yesterday`
- `date:this-week`
- `date:this-month`
- `date:last-week`
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
size:100K..500K ext:pdf
date:last-week path:docs
modified:today created:2026-04-23
date:2026-04-01.. modified:..2026-04-23
modified:2026-04-23T09:15:30+00:00
regex:true report-\d+
regex:/^todo.*release$/im
is:file path:src
is:dir path:projects
is:symlink
-(ext:log | ext:tmp) report
-is:duplicate -path:node_modules
(invoice | receipt) ext:pdf
regex:/launch|ship/i path:docs
```

## Operator Notes

- Path/name terms are case-insensitive unless `case:true` is set.
- Content operators only match indexed document text; unsupported files fall back to filename/path search.
- `date:`, `modified:`, and `created:` accept `today`, `yesterday`, `this-week`, `this-month`, a single ISO date, open-ended ISO ranges, full ISO ranges, and exact ISO datetimes.
- `last-week` and `last-month` use calendar boundaries in local time rather than "last 7 days" or "last 30 days".
- `size:` comparisons use binary suffixes, so `10M` means `10 * 1024 * 1024` bytes.
- `size:100..500K` is inclusive on both ends; reversed ranges are normalized by the compiler before execution.
- `is:` supports `file`, `dir`, `symlink`, `empty`, and `duplicate`.
- `is:duplicate` matches entries that share a content hash with at least one other indexed file.
- `regex:true` only changes how plain terms are interpreted; explicit `/pattern/flags` literals still work without it.
- Explicit regex literals support the standard `i`, `m`, and `s` flags.
- Negation applies to the next term or the entire parenthesized group.

## Practical Limits

- Regex terms are evaluated against the candidate set after SQL filtering, so broad regex queries are naturally slower than indexed term searches.
- `content:` and plain quoted phrases need content indexing enabled for document-body matches.
- Exact duplicate detection depends on parsed content and stored hashes; unsupported formats still participate in filename/path search but may not be marked as duplicates.
