"""Challenge 6: real, independent, locally executed LLM benchmark.

Uses the unchanged REI-1.0 benchmark engine for all four arms. Model output is
never marked verified; no answer key appears in prompts. CPU inference uses a
separate loopback-only llama.cpp server with no secret/API token.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import urllib.error
import urllib.request

from rei0.benchmark import (
    Limits, _STAGE_SYSTEM, read_json, run_benchmark, verify_report,
)
from rei0.inquiry import ModelTurn

BASE = Path(__file__).resolve().parent
MODEL_ALIAS = "qwen3-4b-instruct-2507-q4_k_m"
# Third-party Apache-2.0 GGUF mirror: see research/challenge6/README.md
EXPECTED_MODEL_SHA256 = "85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9"
ENDPOINT = "http://127.0.0.1:8099/v1/chat/completions"


class LocalGGUFProvider:
    kind = "live_local_model_real_inference"

    def __init__(self, model_digest: str, engine_commit: str):
        self.fingerprint = hashlib.sha256(json.dumps({
            "model": MODEL_ALIAS, "model_sha256": model_digest,
            "engine": "llama.cpp", "engine_commit": engine_commit,
            "temperature": 0.0, "seed": 711,
            "response_format": "json_object", "endpoint": "127.0.0.1:8099",
            "api": "chat-completions",
        }, sort_keys=True).encode()).hexdigest()
        self.calls = 0

    def respond(self, *, case_id: str, arm: str, stage: str, context: dict,
                max_output_tokens: int, timeout: float) -> ModelTurn:
        self.calls += 1
        system = _STAGE_SYSTEM[stage]
        user = json.dumps({"stage": stage, "arm": arm, "context": context},
                          ensure_ascii=False, sort_keys=True)
        body = {
            "model": MODEL_ALIAS,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "seed": 711,
            "max_tokens": max_output_tokens,
            "stream": False,
        }
        req = urllib.request.Request(ENDPOINT,
                  data=json.dumps(body).encode("utf-8"), method="POST",
                  headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                data = res.read(65537)
            if len(data) > 65536:
                raise ValueError("oversized model response")
            doc = json.loads(data)
            message = doc["choices"][0]["message"]["content"]
            parsed = json.loads(message)
            tokens = doc["usage"]["total_tokens"]
            if type(tokens) is not int or tokens <= 0 or not isinstance(parsed, dict):
                raise ValueError("model usage/JSON invalid")
            return ModelTurn(parsed, tokens)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError,
                KeyError, TypeError, ValueError) as exc:
            # Benchmark runner records this as a failed model turn, not a correct abstention.
            raise ValueError(f"local model request failed ({type(exc).__name__})") from exc


def check_model(path: Path) -> str:
    hashval = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            hashval.update(chunk)
    sha = hashval.hexdigest()
    if sha != EXPECTED_MODEL_SHA256:
        raise RuntimeError("model file SHA-256 differs from pinned third-party quantization")
    return sha


def write_results(path: Path, report: dict, model_sha256: str, engine_commit: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    report["challenge6_environment"] = {
        "model": MODEL_ALIAS, "model_sha256": model_sha256,
        "llama_cpp_commit": engine_commit,
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "model_access": "open_weights_cpu_inference_no_external_model_api",
        "study_class": "exploratory_6_case_pilot_not_preregistered_blind_holdout",
    }
    # Original benchmark report checksum/verification deliberately excludes this
    # separate environment manifest to preserve inherited report semantics.
    env = report.pop("challenge6_environment")
    path.write_text(json.dumps({"report": report, "environment": env}, indent=2), encoding="utf-8")
    return env


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--model-file", type=Path, required=True)
    p.add_argument("--engine-commit", required=True)
    p.add_argument("--output", type=Path, default=Path("challenge6-results/pilot.json"))
    p.add_argument("--verify-only", action="store_true")
    args = p.parse_args(argv)
    cases = read_json(BASE / "cases.json")
    keys = read_json(BASE / "keys.json")
    if args.verify_only:
        recorded = json.loads(args.output.read_text())
        info = verify_report(recorded["report"], cases, keys)
        print("PASS independently regraded:", json.dumps(info))
        return 0
    sha = check_model(args.model_file)
    provider = LocalGGUFProvider(sha, args.engine_commit)
    limits = Limits(max_calls=3, max_tokens=2600, max_seconds=140,
                    max_output_tokens=320, steps=1)
    report = run_benchmark(cases, keys, provider, limits=limits, seed=24011)
    check = verify_report(report, cases, keys)
    env = write_results(args.output, report, sha, args.engine_commit)
    print("MODEL_JSON_REPORT:", args.output)
    print("VERIFIED:", check)
    print("SUMMARY:", json.dumps(report["summary"], indent=2))
    print("PAIRED:", json.dumps(report["paired_comparisons"], indent=2))
    print("PROVIDER CALLS:", provider.calls)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## REI Challenge 6 — Real open-weight LLM pilot\n\n")
            f.write("Model: `Qwen3-4B-Instruct-2507` Q4_K_M, locally run through llama.cpp. Six illustrative tasks; one trial per arm.\n\n")
            f.write("| Arm | Correct (of 6) | Errors | Model calls | Reported tokens |\n")
            f.write("|---|---:|---:|---:|---:|\n")
            for arm in ("baseline", "self_critique", "fixed_depth", "rei"):
                x = report["summary"][arm]
                f.write(f"| {arm} | {round(x['overall_success']*6)} | {x['failed_runs']} | {x['total_model_calls']} | {x['total_reported_tokens']} |\n")
            f.write("\n**Research limitation:** Small open model, nonblind public questions, no independent evidence access, unequal *consumed* compute, and no established superiority. See downloadable JSON artifact for cases and errors.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
