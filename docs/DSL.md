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
| type filter | File, dir, symlink, or duplicate | `is:duplicate` |
| case mode | Toggle case-sensitive matching | `case:true README` |
| negation | Exclude a term or operator | `-path:node_modules` |
| grouping | Combine branches safely | `(invoice | receipt) ext:pdf` |

## Relative Dates

- `date:today`
- `date:yesterday`
- `date:this-week`
- `date:this-month`
- `date:2026-04-23`
- `date:2026-04-01..2026-04-23`

## Common Combos

```text
ext:pdf content:"release notes"
size:>10M date:this-month
-is:duplicate -path:node_modules
(invoice | receipt) ext:pdf
regex:/launch|ship/i path:docs
```

## Notes

- Path/name terms are case-insensitive unless `case:true` is set.
- Content operators only match indexed document text; unsupported files fall back to filename/path search.
- Negation applies to the next term or the entire parenthesized group.
