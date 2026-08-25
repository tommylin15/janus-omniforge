# Core Iceberg schemas

Core tables use Iceberg format v2 and immutable snapshots. OHLCV is partitioned
by trade month and a 32-bucket symbol hash to avoid one partition per symbol or
day. Natural keys are `symbol`, `market`, and `trade_date`; writes must merge
without replacing an existing non-null value with a newer null.

Schema field IDs are stable. Additive evolution receives new IDs; changing the
meaning or unit of an existing field requires a new table version.
