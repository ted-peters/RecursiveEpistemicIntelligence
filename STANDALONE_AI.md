# REI Standalone AI — Local, Open-Weight Runtime (Experimental)

This is the first **usable standalone application built around the REI
research engine**, rather than a scripted showcase. It supplies a browser
chat UI, a small HTTP API other programs can call, an independent
open-weight language model served by Ollama, and a bounded REI epistemic
inquiry pass before each answer.

**REI is an orchestration/reasoning engine, not a trained foundation model.**
You still need an open-weight model (for example Qwen3 4B Instruct) for text
generation. Nothing requires ChatGPT, a paid inference API, or access to
OpenAI's model servers. The model weights download once and run on your own
machine or server.

## Genuine Qwen3 4B end-to-end smoke test — verified

The REI local chat runtime completed a real model inference smoke test on
GitHub Actions:
[successful run #43650863646](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43650863646).

- Direct Qwen mode: **one model call, 108 server-reported tokens**.
- REI mode: a genuine Qwen-generated claim, **two validated bounded inquiry
  expansions**, an auditable typed REI graph, and final Qwen synthesis,
  totaling **four model calls and 2,090 server-reported tokens**.
- The signed-review system was not invoked: this was provisional
  model-origin reasoning and **not verified external evidence**.
- Localhost Host/Origin checks passed. No model weights or credentials
  were published in the results.
- The independent standalone integration suite and full REI regressions
  passed on the research implementation branch as well.

Earlier real-model runs failed because the original 256-token JSON
expansion was truncated. The current compact, JSON-schema-constrained
expansion uses a larger **bounded** 512-token output allowance while
retaining strict graph and structured-response validation.

The test computer and model server shut down when GitHub Actions completes.
This is not a hosted persistent AI service. Start the local application
using the Docker or Ollama setup below to use it yourself.

## Apple Silicon quick start (recommended)

On an Apple Silicon Mac (M-series), native Ollama can use Apple's Metal
acceleration. The repo includes a small, inspectable Bash launcher, which
checks Python and Ollama, creates a project-only Python virtual environment,
downloads the chosen model if absent, and runs the localhost web UI.

First install [Ollama for macOS](https://ollama.com/download/mac) and
**Python 3.10 or newer**. Then, in Terminal:

```bash
git clone --branch challenge8-structured-output \
  https://github.com/ted-peters/RecursiveEpistemicIntelligence.git
cd RecursiveEpistemicIntelligence
bash scripts/start_rei_mac.sh
```

Open **http://127.0.0.1:7861/** in Safari once Terminal says the server is
running. You can use `Ctrl+C` in Terminal to stop it. Later sessions from
the same folder only need `bash scripts/start_rei_mac.sh`.
The script does not need Docker, run a downloaded shell installer,
publish any public port, or require paid model API keys. It is not a
signed/notarized macOS application bundle. If your Python is old, the
launcher will tell you to install a supported version instead of silently
changing the system Python installation.

**Quality gate:** There is an optional direct-vs-REI comparison suite under
`research/standalone_eval/`, with six public objective questions and an
independent, rule-based grader. Its fixture run is software-only; the live
run requires a local Qwen model. This is a development check, not evidence
of general intelligence or model quality superiority.

## Option A — one command with Docker Desktop

Prerequisites: Docker Engine or Docker Desktop with Compose support,
sufficient disk/RAM to run a ~2.5 GB Qwen3 4B model, and an internet
connection **for the initial model download**.

From the checked-out repository directory:

```bash
docker compose up --build
```

The Compose stack starts a private Ollama model server, downloads
`qwen3:4b-instruct` to a persistent Docker volume if needed, then starts
REI's web application. Open **http://127.0.0.1:7861/**.

All three containers run locally. The UI is bound to
`127.0.0.1:7861` on the host. The Ollama port is not published; it is
available only to the other containers. The application deliberately has
no login/authentication or TLS, so **do not publish it to the internet**.
The first model download may be several gigabytes. Subsequent starts reuse
the persistent model volume.

Stop: `Ctrl+C` (when run attached), or `docker compose down` from another
terminal. `down` preserves the downloaded model volume; **do not use
`down -v`** unless you intend to delete the weights.

Docker Desktop on macOS may run local inference on the CPU rather than
using Apple's Neural Engine/Metal acceleration. If performance is poor,
use the native Ollama setup below.

## Option B — native Ollama, better performance on some Macs

1. Install [Ollama](https://ollama.com/download) on your device, start it,
   and download the open-weight model using `ollama pull qwen3:4b-instruct`.
2. Install Python 3.10 or newer. In this repository:
   `python -m pip install .`
3. Verify access: `rei-local-ai doctor`
4. Start the UI: `rei-local-ai serve`
5. Open **http://127.0.0.1:7861/**.

The commands also work without an installed console script:

```bash
python -m rei0.local_ai_cli doctor
python -m rei0.local_ai_cli serve
python -m rei0.local_ai_cli ask "What assumptions must I test before trusting this claim?"
python -m rei0.local_ai_cli ask --mode direct "Give me a short explanation of Bayes' theorem."
```

The default local model is `qwen3:4b-instruct`. Choose another
Ollama-installed model with `REI_MODEL` (or `--model` placed **before**
the subcommand). For example:

```bash
rei-local-ai --model qwen3:8b doctor
rei-local-ai --model qwen3:8b serve
```

The model must be available in Ollama first. RAM/VRAM requirements vary
with model, context length and inference engine.

## Using REI as the engine of your own application

Two modes exist:

- `rei` (default): a local model proposes a tentative claim and a small
  challenge frontier. **The real `rei0.inquiry.InquiryEngine`** pursues
  up to two questions, building a typed audit graph. The local model
  synthesizes a conversational answer from that *explicitly unverified*
  scaffold. Costs about 2–4 model requests depending on the question.
- `direct`: the same underlying model answers without REI, typically
  in one model request. It is useful as a cost/quality baseline.

The local AI provides a **minimal non-streaming OpenAI-compatible endpoint**:

```bash
curl -s http://127.0.0.1:7861/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"rei-local","stream":false,"mode":"rei","messages":[{"role":"user","content":"How could I test the key assumption in this idea?"}]}'
```

The reply includes a normal `choices[0].message.content`, a `usage`
record with **total tokens only**, and an extra `rei_audit` object with
model calls, measured tokens, unanswered questions, stop reason and graph
audit digest. This is **not a full OpenAI API implementation**. Streaming,
tool calls, images, system messages supplied by clients, and other advanced
provider settings are unsupported and rejected.

You can also use it as a Python library without HTTP:

```python
from rei0.local_ai import StandaloneREI

assistant = StandaloneREI(
    model="qwen3:4b-instruct",
    endpoint="http://127.0.0.1:11434",
)

result = assistant.answer(
    [{"role": "user", "content": "What evidence would falsify this claim?"}],
    mode="rei",
)
print(result["answer"])
print(result["audit"])
```

To customize it, build a subclass implementing the tiny model contract
(`initial`, `expand`, `complete`), then pass
`StandaloneREI(provider_factory=your_factory)`. The runtime uses the
same invariant-checking `InquiryEngine` and keeps the user interface,
model inference, and REI graph separate. This is a starting point for
a domain-specific assistant, not a new trained foundation model.

## Safety and evidence integrity

- All model-origin arguments, objections and conclusions remain
  **provisional/unverified**. The runtime does not fabricate a signed
  source approval, and it does **not** silently treat a graph's
  `NEITHER` status as proof that a proposition is false.
- No browsing, shell execution, external search, arbitrary plugins or
  background agents are exposed to model text. They can be added later
  only through explicit, permissioned tool adapters.
- Local Ollama connections are restricted to loopback, or the
  dedicated `ollama` Compose hostname; the client does not follow HTTP
  redirects and never sends remote API credentials.
- The browser/API binds to loopback by default, validates its Host and
  Origin, requires bounded JSON requests, and limits concurrent
  generations to one. **Do not expose it publicly without a separate
  authentication, network and security review.** Docker's
  `--allow-remote-bind` is used only inside its container, while the
  host port remains explicitly loopback-only.
- Conversation history is kept in the browser session and sent with each
  request. There is no persistent chat memory, file ingestion, retrieval
  augmented generation, or durable user account in this initial runtime.
- Audit hashes detect accidental local modification, not external
  timestamping or authentic model execution; use signed evidence ledgers
  in the existing REI research modules when trusted reviewers exist.
- Server-reported token usage is required, not silently replaced with
  zero. A failed model call can have unreported usage, so the runtime
  makes no claim to have metered incomplete attempts perfectly.

## Development and tests

```bash
python -m pip install .
python -m unittest discover -s tests -p test_local_ai_standalone.py -v
python -m unittest discover -s tests -v
```

The new tests fake the model to verify **real REI graph construction,
independent direct-mode baseline, model failure semantics, response
formatting, token accounting, loopback protection and browser/API
integration**. These tests require neither Ollama nor model downloads.

### What is still unproven?

This is a functional standalone **REI-based assistant**, not a claim that
a trained REI-native neural model exists or that the REI reasoning pass
consistently improves answer quality. The 12-case research experiment
compared conventional exact Bayesian planning to Qwen self-critique on
a public synthetic investigation task: 12/12 versus 10/12 realized
decisions, with 48 model calls for Qwen. That planner itself is a standard
mathematical algorithm. A full research evaluation must compare
this `rei` chat runtime to `direct` and a capable self-critique
baseline on independent, held-out factual and user tasks with matched
actual inference costs and verified external facts.
