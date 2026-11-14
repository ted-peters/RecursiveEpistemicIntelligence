"""Loopback-only HTTP API + tiny browser UI for the local REI runtime.

No remote authentication system is implemented. Exposing this HTTP server
to the internet is unsafe; bind it to loopback, or run behind a deliberate
authenticated proxy if you know how to secure an external deployment.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import threading
import time

from .local_ai import StandaloneREI, LocalAIError, validate_messages
from .models import canonical_json

MAX_BODY_BYTES = 25_000


def make_server(engine: StandaloneREI, *, host: str = "127.0.0.1",
                port: int = 7861, allow_remote_bind: bool = False):
    if host not in ("127.0.0.1","localhost","0.0.0.0"):
        raise LocalAIError("Only local loopback or explicit container listening is permitted")
    if host=="0.0.0.0" and not allow_remote_bind:
        raise LocalAIError("Remote binding requires --allow-remote-bind and an external access boundary")
    if type(port) is not int or not 0<=port<=65535:
        raise LocalAIError("invalid listening port")
    lock=threading.BoundedSemaphore(value=1)

    class Handler(BaseHTTPRequestHandler):
        server_version = "REIStandalone/0.1"

        def log_message(self, fmt, *args):
            # Never log user prompts or model outputs. Use event only.
            return

        def _headers(self, code: int, *, mime: str, length: int):
            self.send_response(code)
            self.send_header("Content-Type",mime)
            self.send_header("Content-Length",str(length))
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Cache-Control","no-store")
            self.send_header("Referrer-Policy","no-referrer")
            self.send_header("X-Frame-Options","DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
                "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
            )
            self.end_headers()

        def _send(self, code: int, body: dict):
            raw=canonical_json(body).encode("utf-8")
            self._headers(code,mime="application/json; charset=utf-8",length=len(raw))
            self.wfile.write(raw)

        def _accept_host(self) -> bool:
            actual_port=self.server.server_address[1]
            expected={"localhost:"+str(actual_port),"127.0.0.1:"+str(actual_port)}
            supplied=self.headers.get("Host","")
            # DNS rebinding defense; do not treat arbitrary internal names as
            # browser-trusted just because the process is in a container.
            if supplied not in expected:
                self._send(403,{"error":"Only loopback Host headers are accepted"})
                return False
            return True

        def _accept_origin(self) -> bool:
            origin=self.headers.get("Origin")
            actual_port=self.server.server_address[1]
            if origin and origin not in ("http://localhost:"+str(actual_port),
                                         "http://127.0.0.1:"+str(actual_port)):
                self._send(403,{"error":"Cross-origin requests are not permitted"})
                return False
            return True

        def do_GET(self):
            if not self._accept_host():
                return
            if self.path=="/":
                raw=files("rei0").joinpath("local_ai_ui.html").read_bytes()
                self._headers(200,mime="text/html; charset=utf-8",length=len(raw))
                self.wfile.write(raw)
                return
            if self.path=="/health":
                self._send(200,{
                    "status":"server_up",
                    "model":engine.model,
                    "ollama_connection":"unchecked",
                    "external_tools":False,
                    "notes":"Local runtime is listening; check Ollama with the doctor command",
                })
                return
            if self.path=="/v1/models":
                self._send(200,{"object":"list","data":[{
                    "id":"rei-local","object":"model","owned_by":"local",
                }]})
                return
            self._send(404,{"error":"No such endpoint"})

        def do_POST(self):
            if not self._accept_host() or not self._accept_origin():
                return
            if self.path not in ("/api/chat","/v1/chat/completions"):
                self._send(404,{"error":"No such endpoint"})
                return
            if (self.headers.get("Content-Type","").split(";")[0].strip()
                !="application/json" or self.headers.get("Transfer-Encoding")):
                self._send(415,{"error":"POST requires JSON and a bounded Content-Length"})
                return
            header=self.headers.get("Content-Length","")
            if not header.isdecimal() or not 0<int(header)<=MAX_BODY_BYTES:
                self._send(413,{"error":"Request must declare a nonzero JSON body under 25k"})
                return
            raw=self.rfile.read(int(header))
            try:
                document=json.loads(raw)
            except (ValueError,UnicodeError):
                self._send(400,{"error":"Malformed JSON body"})
                return
            if not isinstance(document,dict):
                self._send(400,{"error":"JSON body must be an object"})
                return
            if not lock.acquire(blocking=False):
                self._send(429,{"error":"Local AI is busy; only one generation runs at a time"})
                return
            try:
                if self.path=="/api/chat":
                    if set(document)-{"message","history","mode"}:
                        raise LocalAIError("Unsupported chat input fields")
                    prompt=document.get("message")
                    history=document.get("history",[])
                    if not isinstance(history,list) or not isinstance(prompt,str):
                        raise LocalAIError("message must be text, history must be an array")
                    messages=validate_messages(history+[{"role":"user","content":prompt}])
                    result=engine.answer(messages,mode=document.get("mode","rei"))
                    self._send(200,result)
                else:
                    if set(document)-{"messages","model","mode","stream"}:
                        raise LocalAIError("Unsupported OpenAI-compatible request fields")
                    if document.get("model","rei-local")!="rei-local" or document.get("stream",False) is not False:
                        raise LocalAIError("Only model=rei-local and stream=false are supported")
                    messages=validate_messages(document.get("messages"))
                    response=engine.answer(messages,mode=document.get("mode","rei"))
                    self._send(200,{
                        "id":"rei-local-"+str(int(time.time()*1000)),
                        "object":"chat.completion",
                        "model":"rei-local",
                        "choices":[{
                            "index":0,
                            "message":{"role":"assistant","content":response["answer"]},
                            "finish_reason":"stop",
                        }],
                        "usage":{
                            # No reliable input/output split for all stages.
                            "total_tokens":response["audit"]["model_reported_tokens"],
                        },
                        "rei_audit":response["audit"],
                    })
            except (LocalAIError,ValueError) as exc:
                # Avoid returning prompt/model body in errors.
                self._send(422,{"error":str(exc)[:320]})
            except (OSError,TimeoutError) as exc:
                self._send(502,{"error":"Local generation failed ("+type(exc).__name__+")"})
            finally:
                lock.release()

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    return Server((host,port),Handler)
