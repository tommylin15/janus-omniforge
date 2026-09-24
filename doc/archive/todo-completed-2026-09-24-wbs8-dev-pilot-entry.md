# WBS-8-DEV-PILOT-ENTRY — completed 2026-09-24

Entry Gate passed at `2026-09-24T15:29:19Z`; this timestamp is the documented
`pilot_started_at` for the six-month evidence window.

- Existing GCP dev `janus-private-pipeline` was repaired through
  `scripts/gcp/deploy-dev.sh private-pipeline`. Cloud Build
  `b09efc62-93da-4afd-93ba-810a9def7ed2` succeeded and deployed immutable image
  `us-central1-docker.pkg.dev/gen-lang-client-0593591102/janusai-poc/private-pipeline@sha256:71cacb4cd012183f23a2a9f4b003a9ad1735a4fcc49eba1d3e50ffde45fe7cb1`.
- Job configuration remained bounded and owner-scoped: service account
  `janus-private-pipeline`, command `python -m services.api.private_pipeline`,
  one task, 30-minute timeout, one retry, and `JANUS_API_POSTGRES_BUNDLE` from
  `janus-runtime-bundle:latest`. Job condition was `Ready=True`.
- Runtime execution `janus-private-pipeline-dd77n` completed with
  `Completed=True`, `succeededCount=1`; start `2026-09-24T15:24:43Z`, completion
  `2026-09-24T15:29:19Z`.
- The previous Job and API shared the `api` Artifact Registry package, and API
  image cleanup could delete the Job's untagged digest. The deployment script
  now builds the same API Dockerfile into the separate `private-pipeline`
  package, isolating Job image retention from API cleanup.
- Other Entry prerequisites had current evidence: WBS-3 canary／full-market
  safety; ledger backup／isolated restore; pilot readiness schema and bounded
  privileges; outcome collection and usefulness feedback implementations;
  release baseline lineage; minimum DQ; security／privacy／FinOps; WBS-5 supply
  planning; and ChatGPT MCP Owner A/B read isolation.
- Live count remained one release baseline, zero outcome rows, zero feedback
  rows, and one feedback target. No sample outcome or feedback was fabricated;
  no baseline-linked report had yet produced outcome or feedback rows.
- No staging or production resources were created.

Latest complete evidence: [`../spec/operations-and-testing.md`](../spec/operations-and-testing.md).
