# Recursive Epistemic Intelligence — REI-1.0

**Version 1.0.0** · Python 3.10+ · `cryptography>=42,<50` · local platform + legacy 0.1–0.9 components.

REI-1.0 is the project's first **integrated local research platform**. It adds a SQLite-based audit workspace, a read-only browser dashboard, validated artifact import, and a unified `platform-run` interface to the existing preregistered experiment engine. It retains the prior typed epistemic graph, bounded recursive inquiry, independent evidence review, source provenance, belief revision, benchmarks, repeated-trial studies, and experimental controls.

> **Scientific status: No live-model empirical findings have been produced by this release.** Offline fixtures validate software behavior only. Equal maximum budgets do not imply matched actual computation; author signatures authenticate decisions, not truth. REI is a research hypothesis, not a demonstrated superior model.

## Quick start — no API key or network needed

From the extracted project root:

```sh
python -m pip install .
python -m unittest discover -s tests -p 'test_*.py' -v
python -m rei0 platform-demo --workspace research.sqlite
python -m rei0 platform-verify --workspace research.sqlite
python -m rei0 platform-report --workspace research.sqlite --output research_summary.json
python -m rei0 platform-serve --workspace research.sqlite --port 8787
```

Open **http://127.0.0.1:8787/** in your browser while the last command is running; press `Ctrl+C` in the terminal to stop. The dashboard and `/api/summary` endpoint serve *redacted aggregate summaries*, never raw prompts, source artifacts, review private keys, or held-out grading keys. The service binds only to `127.0.0.1` and permits GET/HEAD, not modification. This is a local research viewer, not an internet-facing server or authentication system.

`platform-demo` uses a deliberately **synthetic** four-arm comparison and a small example graph. It neither calls a language model nor establishes any scientific result.

## Validate and import earlier REI artifacts

Initialize an empty workspace:

```sh
python -m rei0 platform-init --workspace research.sqlite
```

Import an existing epistemic graph with full event replay:

```sh
python -m rei0 platform-import --workspace research.sqlite \
  --kind graph --file examples/inquiry_graph.json
```

Import a revision journal (not the separate `revision-demo` summary). Revision journals receive integrity/replay validation; rule-signature and source-truth verification are separate procedures documented in the older revision protocol:

```sh
python -m rei0 platform-import --workspace research.sqlite \
  --kind revision --file YOUR_REVISION_JOURNAL.json
```

Import a v0.9 experiment with **independent regrading at import**, using the four original dataset files and adjudication manifest. This example is a synthetic fixture:

```sh
python -m rei0 platform-import --workspace research.sqlite \
  --kind experiment --file examples/experiment09_demo_report.json \
  --calibration-cases rei0/data/study_calibration_cases.json \
  --calibration-keys rei0/data/study_calibration_keys.json \
  --evaluation-cases rei0/data/study_evaluation_cases.json \
  --evaluation-keys rei0/data/study_evaluation_keys.json \
  --adjudications examples/experiment09_SYNTHETIC_adjudications.json
```

`platform-import` refuses an experiment without its original answer keys and adjudication metadata, rejects modified grades or protocol mismatches, and only commits after the inherited `verify_experiment` passes. The *keys and manifest are read but not copied into the workspace*. The database stores the original report (which may contain model text), its digest, a redacted summary, and an audit event. Protect the file and run the dashboard only in a trusted local environment.

## Real-model research workflow (opt-in, no live tests have been executed)

**First:** Prepare independently reviewed, non-overlapping calibration and evaluation sets and protected answer keys. Use `python -m rei0 experiment-adjudication-template --help` for a declaration format, have an actual independent reviewer inspect sources, and store source proofs separately. A reviewer name in a JSON file is not cryptographic authentication.

**Second:** Freeze a preregistration *before* running held-out evaluations using `experiment-preregister`. Example (replace the four paths, adjudications, model, and study ID):

```sh
python -m rei0 experiment-preregister \
  --study-id REI10-PILOT-001 --repetitions 3 \
  --calibration-cases cal_cases.json --calibration-keys cal_keys.json \
  --evaluation-cases eval_cases.json --evaluation-keys eval_keys.json \
  --adjudications adjudications.json \
  --live --model YOUR_SUPPORTED_MODEL_ID --acknowledge-live-costs \
  --output preregistration.json
```

Publish or independently timestamp the preregistration hash before running evaluation. Dataset quality and reviewer independence must be established outside this software.

**Third:** Execute and import the preregistered experiment in one operator step (API key stays in your environment):

```sh
export REI_LLM_API_KEY='YOUR_PRIVATE_PROVIDER_KEY'
python -m rei0 platform-init --workspace research.sqlite
python -m rei0 platform-run \
  --workspace research.sqlite --prereg preregistration.json \
  --calibration-cases cal_cases.json --calibration-keys cal_keys.json \
  --evaluation-cases eval_cases.json --evaluation-keys eval_keys.json \
  --adjudications adjudications.json \
  --report experiment_report.json --checkpoint experiment_checkpoint.json \
  --live --model YOUR_SUPPORTED_MODEL_ID --acknowledge-live-costs
```

`platform-run` requires all three flags `--live`, `--model` and `--acknowledge-live-costs`, and the provider must match the frozen identity. **External calls may incur charges.** A crash during a trial may repeat network requests and costs on resume; only completed trials are checkpointed. The provider/endpoint may change independently; a model identifier is not a remotely attested model version.

**Fourth:** Run the independent evaluator again with the held-out keys:

```sh
python -m rei0 experiment-verify \
  --report experiment_report.json --adjudications adjudications.json \
  --calibration-cases cal_cases.json --calibration-keys cal_keys.json \
  --evaluation-cases eval_cases.json --evaluation-keys eval_keys.json
```

**Fifth:** Inspect the workspace dashboard and prespecified comparison. Flag any experiment where *actual* token/call use is imbalanced; do not claim equal-cost causal improvement based on matching maximum limits or post-hoc filtered subsets. Use multiple case clusters, external review, and independent replication before making research claims.

## Workspace and dashboard commands

| Command | Effect |
| --- | --- |
| `platform-init` | Creates a private (0600) SQLite research workspace; refuses overwrite |
| `platform-demo` | Runs a no-network, synthetic integrated study and graph import |
| `platform-import` | Validates a graph, journal, or experiment **before** atomic import |
| `platform-run` | Executes a frozen existing experiment and imports it with regrading |
| `platform-list` | Lists validated artifact summaries |
| `platform-verify` | Checks workspace event chain, content hashes, and graph/journal replay |
| `platform-report` | Exports a redacted aggregate summary JSON |
| `platform-serve` | Runs a read-only local dashboard on loopback |

Use `python -m rei0 COMMAND --help` for all parameters. `platform-verify --expected-head HEX` compares against a previously archived independent audit head. **A hash chain without a separately trusted anchor does not prove history was not rolled back or replaced.** Importing graph/journal with `--expected-head` similarly checks a separately held chain head.

## Prior functionality preserved

```sh
python -m rei0 inquiry-demo
python -m rei0 source-demo
python -m rei0 service-demo
python -m rei0 revision-demo
python -m rei0 benchmark-demo --output benchmark.json
python -m rei0 study-demo --output study.json
python -m rei0 experiment-demo --output-dir rei09_demo
```

Existing database, graph, revision, evidence, and research schema formats are unchanged; the new platform storage is separate and additive. The original v0.9 manual remains in `docs/REI_0.9_README_ARCHIVE.md`.

## Boundaries and threats

- Every epistemic claim remains challengeable; operational safeguards are enforced outside ordinary inference.
- Source content, reviewer declaration, evidence authenticity, logical entailment, and factual truth are **different** concepts. REI does not automatically establish them.
- A validated experimental record is independently *regraded* against caller-supplied keys, not independently *authenticated* as having been run by the named model. A synthetic fixture is explicitly tagged.
- The local workspace uses append-only SQL triggers and hash chaining. A privileged local attacker can replace or truncate the entire file; use external head anchoring, protected backups, separate OS accounts, and database permissions where necessary.
- The dashboard has no authentication and must not be exposed beyond loopback or run on an untrusted shared workstation; it deliberately returns only summary information. Neither SQLite nor the web UI is a production-grade security boundary.
- Real-model calls are **disabled by default** and have not been exercised for this release.

For precise mathematical and operational semantics read `docs/PLATFORM_PROTOCOL_10.md`, `docs/EXPERIMENT_PROTOCOL_09.md`, and `SECURITY.md`. The master philosophical foundation is `docs/REI_Master_Blueprint_v1.md`.
