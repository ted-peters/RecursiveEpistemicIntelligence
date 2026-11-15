"""Entrypoint: python -m rei0.local_ai_cli (serve | ask | doctor).

The Ollama server and model weights are installed separately or started by
the optional Docker Compose bundle. No external API key is required.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .local_ai import LocalAIError, LocalOllamaModel, StandaloneREI


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description="REI standalone local AI chat runtime")
    p.add_argument("--model",default=os.getenv("REI_MODEL","qwen3:4b-instruct"))
    p.add_argument("--ollama-url",default=os.getenv(
        "REI_OLLAMA_URL","http://127.0.0.1:11434"))
    sub=p.add_subparsers(dest="action",required=True)
    server=sub.add_parser("serve",help="Run local browser chat and HTTP API")
    server.add_argument("--host",default="127.0.0.1")
    server.add_argument("--port",type=int,default=7861)
    server.add_argument("--allow-remote-bind",action="store_true",
                        help="Unsafe without an external proxy/access boundary; Docker publishes only loopback")
    ask=sub.add_parser("ask",help="Ask one question and print a response")
    ask.add_argument("question",help="The question to investigate")
    ask.add_argument("--mode",choices=("rei","direct","adaptive"),default="adaptive")
    ask.add_argument("--json",action="store_true",help="Also print audit in machine-readable JSON")
    sub.add_parser("doctor",help="Check model-server connectivity and downloaded tags")
    args=p.parse_args(argv)
    try:
        provider=LocalOllamaModel(model=args.model,endpoint=args.ollama_url)
        if args.action=="doctor":
            result=provider.doctor()
            print(json.dumps(result,indent=2))
            return 0 if result["model_downloaded"] else 2
        engine=StandaloneREI(model=args.model,endpoint=args.ollama_url)
        if args.action=="ask":
            answer=engine.answer([{"role":"user","content":args.question}],
                                 mode=args.mode)
            if args.json:
                print(json.dumps(answer,indent=2,ensure_ascii=False))
            else:
                print(answer["answer"])
                print("\n[REI audit: "+str(answer["audit"]["model_calls"])+
                      " model calls, "+str(answer["audit"]["model_reported_tokens"])+
                      " tokens reported; evidence unverified]",file=sys.stderr)
            return 0
        from .local_ai_server import make_server
        srv=make_server(engine,host=args.host,port=args.port,
                        allow_remote_bind=args.allow_remote_bind)
        try:
            print("REI Local AI listening at http://127.0.0.1:"+str(args.port)+"/",
                  flush=True)
            print("Requires local Ollama model:",args.model,flush=True)
            srv.serve_forever(poll_interval=.3)
        except KeyboardInterrupt:
            return 0
        finally:
            srv.server_close()
        return 0
    except LocalAIError as exc:
        print("REI local AI error:",str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
