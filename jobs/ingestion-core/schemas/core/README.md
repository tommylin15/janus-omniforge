# Core Iceberg schemas

Core tables use Iceberg format v2 and immutable snapshots. OHLCV is partitioned
by trade month and a 32-bucket symbol hash to avoid one partition per symbol or
day. Natural keys are `symbol`, `market`, and `trade_date`; writes must merge
without replacing an existing non-null value with a newer null.

Schema field IDs are stable. Additive evolution receives new IDs; changing the
meaning or unit of an existing field requires a new table version.

## Financial PIT compatibility fence

`financials_v1` keeps its existing `published_at` natural-key/partition field for
backward compatibility. It is **not** automatically authoritative filing
publication time. New snapshot-source writes add `availability_at` from the
actual fetch time and `publication_time_authoritative=false`; MOPS `出表日期` is
preserved separately as `source_report_date`, while fallback fiscal-period dates
are preserved as `fiscal_period_end`.

Consumers doing PIT analysis must use explicit `availability_at` unless
`publication_time_authoritative=true`. Legacy financial rows without a reliable
availability timestamp are fail-closed and require controlled repair/backfill;
they must not be treated as historically available merely because
`published_at` or a fiscal-period date exists.
