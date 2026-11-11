# REI-1.0.0 Release Notes

## Integrated research platform

- New `rei0.platform`: SQLite immutable artifact index, one-transaction import, canonical SHA-256 artifact and summary IDs, append-only hash-linked ledger, replay validation, optional independent head anchoring.
- New `rei0.platform_cli`: `platform-init`, `platform-demo`, `platform-import`, `platform-run`, `platform-list`, `platform-report`, `platform-verify`, `platform-serve`.
- New `rei0.platform_web`: loopback-only, read-only local dashboard and summary JSON API, HTML escaping, strict browser headers, no raw artifact endpoint.
- Experiment imports require independently supplied held-out keys and reviewer declarations; metrics are recomputed through inherited `verify_experiment` before acceptance. Keys and adjudication manifest are not saved in the workspace.
- The `platform-run` workflow executes frozen v0.9 protocols then imports their independently graded reports; live network calls require explicit operator opt-in and credentials.
- All v0.9 public Python APIs, CLI commands, databases and existing schema formats are preserved.

## Testing

See `RELEASE_TEST_REPORT.json` for the final release verification results. No actual live-model provider calls were performed. Synthetic results are NOT evidence of improved model accuracy or intelligence.

## Remaining research work

Independent source curation and reviewer identity verification; properly matched actual-computation randomized experiments; external replication; third-party timestamping, provider attestation, and production-grade local/remote access controls.
