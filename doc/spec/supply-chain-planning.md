# Supply-chain Intelligence Planning

Status: `WBS-5-SUPPLY-INTELLIGENCE-PLANNING` planning evidence, 2026-09-16.
This document is a contract and planning boundary. It does not authorize a new
adapter, crawler, schema, migration, paid source, or GCP resource.

## 1. Scope and foundation

The planning scope covers six domains: AI Server／Semiconductor, Memory, EV,
Networking, Apple supply chain, and Industrial automation. The same semantic
model is used for market, industry, company, product, facility, and indicator
evidence; a domain is not considered ingestion-ready merely because a provider
credential exists.

### 1.1 Common ontology

| Concept | Minimum meaning | Required time／evidence |
|---|---|---|
| `supply_chain_node` | company, supplier, customer, product／component, facility, geography, demand driver, market, or indicator entity | stable identity, identifiers, jurisdiction, `effective_from`／`effective_to`, provenance |
| `supply_chain_edge` | directed relationship such as supplies, buys-from, uses, manufactures, sells-to, substitutes, or competes-with | upstream／downstream node, relationship type, product／component, effective interval, evidence class, confidence |
| `company_exposure` | company-level cost, revenue, capacity, demand, substitution, geography, or regulatory exposure to a node／edge | exposure interpretation, affected metric／period, effective interval, evidence refs |
| `leading_indicator_definition` | versioned definition of a measurable demand, capacity, price, inventory, shipment, or policy indicator | expected metric, unit, lead-time hypothesis, cadence, source and approval status |
| `leading_indicator_observation` | one as-of observation of a defined indicator | value／unit, `observed_at`, `published_at`, `recorded_at`, PIT status, provenance |
| `supply_chain_signal` | deterministic mapping from qualified indicator observation to exposure and expected impact | analysis-as-of, feature／signal revision, evidence, missing-data status |
| `expectation_signal` | market expectation, priced-in assessment, and expectation gap linked to the same evidence boundary | expectation period, basis, confidence, evidence, no unsupported numeric fill |

Relationship evidence uses four controlled classes:

- `confirmed`: directly supported by authoritative filing, contract, or other
  reviewed primary evidence.
- `reported`: attributed statement or disclosure that is not independently
  confirmed by Janus.
- `inferred`: deterministic inference from confirmed／reported evidence; it
  must retain the rule and input references.
- `hypothesis`: testable planning assumption only; it cannot become a fact or
  deterministic published signal.

All nodes, edges, exposures, observations, and signals carry `provenance_id`,
`source_id`, `source_revision`, `observed_at`, `published_at` when available,
`recorded_at`, `effective_from`, `effective_to`, and a quality／approval state.
`analysis_as_of` filters out anything published after the analysis boundary;
unknown or missing time is explicit, never inferred from fetch time.

## 2. Six-domain Source Matrix

The matrix is intentionally conservative. `official` refers to the existing
registry status of a source endpoint, not approval to derive a supply-chain
relationship from it. Unknown license, quota, cost, retention, PIT, or coverage
remains `Unknown` until evidence is reviewed.

| Domain | Candidate indicators／expected metric | Source candidates／class | Approval | Lead time／PIT／coverage／cadence | License／retention／quota／cost／fallback | Provenance |
|---|---|---|---|---|---|---|
| AI Server／Semiconductor | wafer／packaging capacity, accelerator／server demand, inventory, capex／shipments | MOPS／TWSE／TPEx filings and events (`official`); company IR／market-data enrichment (`external`) | official endpoints retain their current scope; IR and relationship claims `candidate` | publication time is source-dependent; daily market context exists; lead time and supply coverage `Unknown` | terms, retention, quota, quotation／redistribution, cost and fallback `Unknown` | source document／endpoint, publication time, retrieval time and revision required |
| Memory | DRAM／NAND pricing or inventory, bit demand, utilization, capex／shipment | company filings (`official` where applicable); IR／research／pricing provider (`external`) | relationship and pricing providers `candidate` | lead time, cadence, historical depth, PIT and coverage `Unknown` | license, retention, quota, cost and fallback `Unknown` | filing／provider observation, publication time, retrieval time and revision required |
| EV | deliveries, battery／cell capacity, raw-material exposure, utilization, order／policy demand | MOPS／regulatory／exchange disclosures (`official`); company IR／provider (`external`) | official disclosures retain their current scope; cross-company edges `candidate` | publication／effective time required; lead time, coverage and cadence source-specific／`Unknown` | license, retention, quota, PII／redistribution, cost and fallback `Unknown` | disclosure／observation ID, publication time, retrieval time and revision required |
| Networking | switch／optical／datacenter demand, capacity, backlog, shipment and inventory | filings／official events (`official`); company IR／provider (`external`) | official facts retain their current scope; enrichment `candidate` | metric definition and PIT source-specific; lead time／coverage `Unknown`; daily market context only | license, retention, quota, cost and fallback `Unknown` | filing／event／observation reference, publication time, retrieval time and revision required |
| Apple supply chain | supplier exposure, product cycle, capacity／shipment, geographic and component concentration | regulatory／company filings (`official` where applicable); IR／provider (`external`) | own-company public facts retain their current scope; supplier edges `candidate` | effective interval and publication time required; lead time, coverage and cadence `Unknown` | Apple／supplier redistribution rights, retention, quota, cost and fallback `Unknown` | filing／statement reference, publication time, retrieval time and revision required |
| Industrial automation | order／book-to-bill, factory-automation demand, backlog, utilization, capex／inventory | MOPS／TWSE／TPEx／government disclosures (`official`); company IR／provider (`external`) | official facts retain their current scope; derived graph edges `candidate` | PIT required; lead time, coverage and cadence require source evidence | license, retention, quota, cost and fallback `Unknown` | disclosure／observation reference, publication time, retrieval time and revision required |

Shared source review status:

| Source／credential class | Current status | Planning treatment |
|---|---|---|
| TWSE／TPEx／MOPS／TAIEX／TPEx benchmark | `official` in the existing registry and existing ingestion path | usable for approved market／filing facts; supply-chain edge extraction still needs evidence mapping |
| FinMind | `approved_fallback` in the registry | fallback only after the corresponding official dataset is missing／unavailable; current token does not change approval scope |
| Fugle／Shioaji／Tiingo | `candidate`; credentials are present in `janus-market-data-bundle` but no adapter is enabled | do not collect or publish until identity, target indicator, API terms, PIT, retention, quota, cost, provenance and fallback are individually approved |
| CMoney／FactSet／Yahoo／Google and research／news providers | `candidate` | no adapter, crawler, or production collection; review legal／API／citation／redistribution scope first |
| PTT／Dcard／Podcast／other social text | `candidate`／potentially `blocked` | creator／platform permission, PII, deletion, citation and redistribution policy required before collection |

## 3. Seed graph planning

The first seed graph is a reviewable set of typed records, not a graph
database. Each proposed seed must include:

```yaml
seed_id: string
domain: one_of_six_domains
upstream_node_id: string
downstream_node_id: string
relationship_type: string
product_or_component: string|null
effective_from: date|null
effective_to: date|null
evidence_class: confirmed|reported|inferred|hypothesis
provenance_refs: string[]
confidence: number|null
status: candidate|approved|rejected|stale
```

Identity matching is a reviewed operation: symbol／legal identifier, name
aliases, product and facility identifiers, and jurisdiction must be retained
with the evidence used to resolve them. `inferred` and `hypothesis` records are
never silently promoted to `confirmed`; conflicts remain visible. No crawler,
complete company list, Graph DB, or automatic article-to-fact conversion is
authorized by this planning slice.

## 4. Signal／Mart contract planning

The canonical chain is:

`leading indicator → company exposure → expected impact → market expectation → expectation gap`.

The future deterministic signal record must contain at least:

```yaml
signal_id: string
indicator_definition_id: string
observation_id: string
exposure_id: string
analysis_as_of: date
lead_time_days: integer|null
direction: up|down|mixed|unknown
magnitude: number|null
confidence: number|null
affected_node_ids: string[]
affected_company_ids: string[]
expected_metric: string|null
expected_period: string|null
market_expectation: string|null
priced_in_status: unknown|not_priced_in|partially_priced_in|priced_in
expectation_gap: number|null
evidence_refs: string[]
feature_revision: string
signal_revision: string
quality_status: good|warning|critical|unknown
```

`magnitude` and `expectation_gap` are nullable until a reviewed deterministic
formula exists. LLM output may summarize evidence or explain contradictions,
but may not calculate exposure, score, magnitude, or fill missing values. The
future implementation must reuse existing Stage → Core → Mart, PIT,
provenance, immutable snapshot, and Cloud Run boundaries.

## 5. Pilot measurement and epoch design

Each materially affecting run belongs to an immutable named epoch. The minimum
epoch lineage is:

```yaml
epoch_id: string
analysis_as_of: date
code_sha: string
core_snapshot_id: string
governance_revision: string
prompt_revision: string|null
feature_revision: string
signal_revision: string
source_matrix_revision: string
```

For each eligible signal, reuse the existing Pilot outcome artifact and measure
5／20／60 trading-day outcomes, benchmark-relative outcome, MFE, MAE, and
valid／excluded status with exclusion provenance. Candidate evaluation views are
coverage／freshness／PIT leakage, lead-time calibration, directional outcome,
benchmark-relative distribution, MFE／MAE, and incremental value versus the
approved baseline. No metric is interpreted as a trading guarantee.

Exclusions are explicit for missing entry, stale／future data, unavailable
benchmark, unresolved identity, corporate-action distortion, or conflicting
evidence; no excluded observation is imputed to zero. A new source, formula,
provider, or material threshold creates a new feature／signal revision and
epoch; it cannot rewrite historical epoch artifacts.

## 6. Gate status and next unlock

- **Gate A — ready for review:** ontology, evidence classes, effective-time／PIT
  rules, six-domain Source Matrix, seed graph record, signal contract, and Pilot
  measurement／epoch design are documented here.
- **Gate B — pending per source:** the presence of credentials in
  `janus-market-data-bundle` is not approval. Fugle／Shioaji／Tiingo and all
  external candidates remain `candidate` until their individual evidence is
  reviewed.
- **Gate C — locked:** no schema／migration／adapter implementation is unlocked
  by this planning document.
- **Gate D — locked:** no supply-chain Mart signal implementation is authorized
  before at least one approved source completes PIT, provenance, replay, and
  bounded DQ evidence.
- **Gate E — not requested:** no new GCP resource, IAM expansion, or paid API was
  created by this WBS.

The next implementation decision is a source-by-source Gate B review. Until
then the market-data bundle remains credential storage only.
