"""REI-0 command-line interface. Run `python -m rei0 --help`."""
import argparse
import sys
import json
from importlib.resources import files
from pathlib import Path

from .adapters import ChatCompletionsAdapter, ScriptedAdapter
from .demo import build_demo, report
from .graph import EpistemicGraph, GraphError
from .inquiry import InquiryEngine, InquiryError, InquiryLimits, InquirySession
from .evidence_cli import add_evidence_commands, handle_evidence_command
from .evidence import EvidenceError
from .review import ReviewError


def _add_inquiry_options(parser):
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--script", type=Path, help="JSON scripted model fixture (offline)")
    source.add_argument("--live", action="store_true", help="explicitly use external HTTPS LLM API")
    parser.add_argument("--model", help="model ID, required with --live")
    parser.add_argument("--endpoint", default="https://api.openai.com/v1/chat/completions",
                        help="HTTPS Chat Completions endpoint; only used with --live")
    parser.add_argument("--max-steps", type=int, default=4)
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument("--max-seconds", type=float, default=30)
    parser.add_argument("--max-model-calls", type=int, default=6)
    parser.add_argument("--checkpoint", type=Path, help="write resumable session JSON")
    parser.add_argument("--save-graph", type=Path, help="write separately auditable graph JSON")
    parser.add_argument("--report", type=Path, help="write readable JSON report")


def _adapter(args):
    if args.live:
        if not args.model:
            raise InquiryError("--model is required with --live")
        return ChatCompletionsAdapter(model=args.model, endpoint=args.endpoint)
    if args.model:
        raise InquiryError("--model requires --live")
    if args.script is None:
        raise InquiryError("select --script PATH for offline replay or --live --model MODEL for HTTPS inference")
    return ScriptedAdapter.load(args.script)


def main() -> int:
    from .platform_cli import PLATFORM_COMMANDS, main_platform
    if len(sys.argv) > 1 and sys.argv[1] in PLATFORM_COMMANDS:
        return main_platform(sys.argv[1:])
    from .experiment_cli import EXPERIMENT_COMMANDS, main_experiment
    if len(sys.argv) > 1 and sys.argv[1] in EXPERIMENT_COMMANDS:
        return main_experiment(sys.argv[1:])
    from .study_cli import COMMANDS as STUDY_COMMANDS, main_study
    if len(sys.argv) > 1 and sys.argv[1] in STUDY_COMMANDS:
        return main_study(sys.argv[1:])
    from .benchmark_cli import COMMANDS as BENCHMARK_COMMANDS, main_benchmark
    if len(sys.argv) > 1 and sys.argv[1] in BENCHMARK_COMMANDS:
        return main_benchmark(sys.argv[1:])
    from .revision_cli import REVISION_COMMANDS, main_revision
    if len(sys.argv) > 1 and sys.argv[1] in REVISION_COMMANDS:
        return main_revision(sys.argv[1:])
    from .service_cli import SERVICE_COMMANDS, main_service
    if len(sys.argv) > 1 and sys.argv[1] in SERVICE_COMMANDS:
        return main_service(sys.argv[1:])
    parser = argparse.ArgumentParser(prog="rei0", description="REI-1.0 epistemic graph, inquiry, verification, revision, benchmarking, repeated studies",
        epilog="""Additional commands: revision-demo, revision-rule-sign,
revision-assess, revision-verify, service-demo, source-demo. Run
`python -m rei0 COMMAND --help` for usage; benchmark-demo, benchmark-run, benchmark-verify, study-demo, study-run, study-verify, experiment-demo, experiment-preregister, experiment-run, experiment-verify.""",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="deterministic v0.1 four-state evidence demo")
    demo.add_argument("--save", metavar="PATH", help="save full graph as JSON")
    assess = commands.add_parser("assess", help="assess claim from a saved graph")
    assess.add_argument("path", type=Path)
    assess.add_argument("claim_id")
    verify = commands.add_parser("verify", help="verify graph audit chain by replay")
    verify.add_argument("path", type=Path)
    inquire = commands.add_parser("inquire", help="run bounded recursive inquiry")
    inquire.add_argument("question", help="the user question; scripted fixtures are illustrative only")
    _add_inquiry_options(inquire)
    inquiry_demo = commands.add_parser("inquiry-demo", help="run the included OFFLINE illustrative scenario")
    _add_inquiry_options(inquiry_demo)
    resume = commands.add_parser("resume", help="resume a previously saved inquiry checkpoint")
    resume.add_argument("path", type=Path)
    _add_inquiry_options(resume)
    checkpoint_verify = commands.add_parser("verify-checkpoint", help="validate inquiry session & graph replay")
    checkpoint_verify.add_argument("path", type=Path)
    add_evidence_commands(commands)
    args = parser.parse_args()
    try:
        if args.command in {"review-key", "evidence-demo", "evidence-init", "evidence-submit",
                            "evidence-review", "evidence-sign", "evidence-accept", "evidence-check-artifact",
                            "evidence-assess", "evidence-verify"}:
            payload = handle_evidence_command(args)
        elif args.command == "demo":
            graph = build_demo()
            if args.save:
                graph.save(args.save)
            payload = report(graph)
            if args.save:
                payload["saved_graph"] = args.save
        elif args.command == "assess":
            payload = EpistemicGraph.load(args.path).assess(args.claim_id).to_dict()
        elif args.command == "verify":
            graph = EpistemicGraph.load(args.path)
            payload = {"valid": True, "event_count": len(graph.events), "audit_head": graph.audit_head,
                       "nodes": len(graph.nodes), "edges": len(graph.edges)}
        elif args.command == "verify-checkpoint":
            session = InquirySession.load(args.path)
            payload = {"valid": True, "steps": session.steps, "open_questions": len(session.queue),
                       "graph_audit_head": session.graph.audit_head}
        else:
            limits = InquiryLimits(max_steps=args.max_steps, max_depth=args.max_depth,
                                   max_tokens=args.max_tokens, max_seconds=args.max_seconds,
                                   max_model_calls=args.max_model_calls)
            if args.command == "inquiry-demo":
                if args.live or args.script or args.model:
                    raise InquiryError("inquiry-demo always uses the bundled offline fixture")
                model = ScriptedAdapter.load(files("rei0").joinpath("data/inquiry_script.json"))
            else:
                model = _adapter(args)
            engine = InquiryEngine(model, limits)
            if args.command == "resume":
                session = engine.run(resume=InquirySession.load(args.path))
            elif args.command == "inquiry-demo":
                session = engine.run("Should an AI explanation make its conclusions more trustworthy?")
            else:
                session = engine.run(args.question)
            payload = session.report()
            if args.checkpoint:
                session.save(args.checkpoint)
                payload["checkpoint_path"] = str(args.checkpoint)
            if args.save_graph:
                session.graph.save(args.save_graph)
                payload["graph_path"] = str(args.save_graph)
            if args.report:
                args.report.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
    except (InquiryError, GraphError, ReviewError, EvidenceError, ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"REI-0 error: {exc}\n")
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
