# REI-1.0 Security and Research Limitations

REI is a **research prototype**, not a production security system or verified truth engine.

## Inherited trust boundary

The v0.4+ evidence verifier remains a separate process and accepts signed reviewer decisions; the v0.5+ verifier can check Ed25519 signatures without reviewer private keys. An authentic signature proves a reviewer signed *that decision*, not that the observation is true. Legacy HMAC compatibility remains in the older service. Restrict host users, credentials, socket access, database privileges and network egress as documented in the archived v0.9 security model (`docs/REI_0.9_SECURITY_ARCHIVE.md`).

## New v1.0 workspace boundary

The SQLite platform database is a locally trusted research index, not a remotely authenticated ledger. Owner-only permissions, transactionality, write-once triggers, event-chain validation and external head comparison reduce accidental corruption and allow detection of many changes. A sufficiently privileged attacker can replace all files and recompute consistent digests unless a prior audit head is anchored elsewhere. WAL and backup files also need appropriate OS protection.

Experiment import requires evaluator-only grading keys, but those keys are never saved to the workspace. The original report *is* stored and may include sensitive model text; store the workspace only on trusted machines and avoid unencrypted shared backups. `platform-report` is redacted and written with 0600 permissions by the CLI.

The dashboard binds to 127.0.0.1; it is read-only, has a defensive Host check and HTML escaping, and does not serve raw files. It **does not require login**. Other local processes/users may still reach the port; do not forward it or use it on an untrusted shared host. The UI is not designed for production deployment or remotely exposed use.

## External model endpoints

Live requests require an explicit `--live --model ... --acknowledge-live-costs` combination and a credential in `REI_LLM_API_KEY`, with an HTTPS Chat Completions-compatible endpoint. The provider may charge for trials, and a crash mid-trial may lead to repeated charges. Frozen model IDs do not prove actual served model binaries, and plain API transcripts are not provider-signed attestations.

Do not put answer keys, reviewer private keys, signing secrets, or external authority credentials in model prompts. Separate the authoring, execution, grading, and approval roles when conducting real research.

## Known limitations

No independent factual truth guarantee, no attestable chronology from local hashes, no guarantee that separate reviewers are genuinely independent merely because their names differ, no strict equal-compute causal estimate from similar call ceilings, no verified superiority claim, and no network-backed live-model evaluation in this release.
