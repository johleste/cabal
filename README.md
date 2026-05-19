# Cabal

```
  █▀▀ ▄▀█ █▄▄ ▄▀█ █░░
  █▄▄ █▀█ █▄█ █▀█ █▄▄
  local multi-agent AI
```

Local multi-agent AI system. deepseek-r1:8b commands a council of specialist
Ollama models for research, agentic coding, recon, and attack postulating.

No cloud. No telemetry. Runs entirely on Ollama.

---

## Agents

| Agent      | Model                      | Role                                              |
|------------|----------------------------|---------------------------------------------------|
| Commander  | `deepseek-r1:8b`           | Orchestrates, reasons, dispatches, synthesizes    |
| Researcher | `deepseek-coder-v2:latest` | Technical research, OSINT, structured analysis    |
| Coder      | `deepseek-coder-v2:latest` | Code generation, review, debugging                |
| Recon      | `wizard-vicuna-uncensored` | Attack postulating, red team reasoning, no refusals |
| Analyst    | `dolphin-llama3:8b`        | Synthesis, report writing, summarization          |
| Executor   | *(no model — runs code)*   | Executes scripts, returns exit code + output      |

Commander dispatches to agents using a `DISPATCH: <AGENT> | <task>` protocol and
synthesizes their output into a `FINAL:` answer. deepseek-r1's chain-of-thought
reasoning (`<think>` blocks) drives all dispatch decisions.

---

## Commands

### `cabal run "task"` — orchestrated multi-agent task

Commander reasons about the task, dispatches to whichever agents it needs,
and synthesizes a final answer.

```bash
cabal run "research CVE-2024-12345 and write a proof-of-concept detector"
cabal run "write a Python script that parses Suricata EVE JSON and test it"
./c.sh run "audit the attack surface of a default Alpine Linux install"
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--rounds N` | 10 | Max Commander dispatch rounds per attempt |
| `--attempts N` | 1 | Max retry attempts. `0` = unlimited |
| `--claude` | off | Consult Claude Code when genuinely stuck (see below) |
| `--confirm` | off | Prompt before Executor runs each script |
| `--timeout N` | 30 | Executor script timeout in seconds |

### `cabal ask "question"` — direct Commander query

Commander answers without dispatching agents. Use for questions that need
reasoning but not specialist agent work.

```bash
cabal ask "what attack surface does a default Alpine Linux install expose?"
cabal ask "explain how CrowdSec bouncer decisions propagate"
```

### `cabal research "topic"` — direct to Researcher

Bypasses Commander. Sends directly to Researcher (deepseek-coder-v2).

```bash
cabal research "how does SMB relay work"
cabal research "passive OS fingerprinting techniques"
```

### `cabal code "task"` — direct to Coder

Bypasses Commander. Sends directly to Coder (deepseek-coder-v2).

```bash
cabal code "write a Python script to parse Suricata EVE JSON alerts"
cabal code "review this function for off-by-one errors: ..."
```

### `cabal recon "scenario"` — direct to Recon

Bypasses Commander. Sends directly to Recon (wizard-vicuna-uncensored).
No refusals. Adversarial thinking only.

```bash
cabal recon "target: nginx reverse proxy in front of a Flask app"
cabal recon "attacker has SSH access as www-data — what next?"
```

### `cabal analyse "task"` — direct to Analyst

Bypasses Commander. Sends directly to Analyst (dolphin-llama3:8b).

```bash
cabal analyse "summarise these Suricata findings: ..."
cabal analyse "write an executive summary of this recon output: ..."
```

### `cabal pull` — print latest session

Prints the most recent session file. Useful mid-run to check progress.

```bash
cabal pull              # print session contents
cabal pull --path       # print session file path only
```

---

## Write-Test-Fix Loop (--attempts)

When writing and testing scripts, Commander uses the Executor agent to run
code and fix errors iteratively. Use `--attempts` to enable retries.

```bash
# Retry indefinitely until the script passes
cabal run --attempts 0 "write a Python script that parses /etc/passwd and prints all users"

# Retry up to 5 times
cabal run --attempts 5 --rounds 15 "write and test a script that monitors open ports"

# Prompt before each execution
cabal run --attempts 0 --confirm "write and test a nftables rule parser"
```

**How it works:**

1. Commander dispatches `CODER` to write a script
2. Commander dispatches `EXECUTOR` to run it
3. Executor returns `exit_code`, `stdout`, `stderr`
4. If `exit_code != 0`, Commander dispatches `CODER` again with the error
5. Rounds repeat until success or `--rounds` is exhausted
6. If the attempt fails, a new attempt starts with **fresh conversation** but
   carrying forward a notes block of everything tried and failed:

```
=== Prior Attempts — read before proceeding ===

Attempt 1:
  Code written:
    ```python
    [last code...]
    ```
  Exit code: 1
  Error:
    AttributeError: 'NoneType' object ...

These approaches failed. Try a meaningfully different strategy.
```

Commander sees what failed without the noise of all the prior rounds.

**Rule of thumb:** budget `--rounds` at ~3× the expected fix iterations, since
each write→test cycle consumes 2 rounds minimum.

---

## Claude Consultation (--claude)

When Commander is genuinely stuck — same error, same exit code, no progress
across two consecutive failed attempts — `--claude` triggers a consultation
with Claude Code for a hint.

```bash
cabal run --attempts 0 --claude "write and test a script that parses kernel logs"
```

**What happens:**

1. After 2 consecutive attempts produce identical errors, Cabal calls `claude --print`
2. It sends: the task, the prior attempt summaries (code written + errors)
3. Claude responds with a specific technical hint or alternative approach
4. The guidance is injected into the next attempt's context as a clearly marked block:

```
=== Claude Consultation ===

The issue is likely that your regex isn't accounting for multi-line log entries.
Try using re.DOTALL or splitting on the timestamp pattern instead of newlines.
[example snippet if provided]

Apply the consultation guidance above in your next attempt.
```

5. Commander reads it and tries a different approach

**Rules:**
- Consultation only fires when stagnant (same error twice in a row) — not on every retry
- Only between attempts, never mid-round
- Commander still does all the work; Claude only provides direction
- Requires `claude` CLI available in PATH
- If the CLI is unavailable or times out, the loop continues without guidance

---

## Executor Agent

Executor runs scripts produced by Coder. It does not call Ollama.

- Extracts the **last fenced code block** from whatever Commander passes it
- Detects language from the fence tag (`python`, `bash`, `sh`) — defaults to `python3`
- Saves the script to a session-scoped file (`sessions/<stamp>_code_NNN.<ext>`) before running
- Executes it, captures stdout/stderr/exit code
- Returns a structured result Commander can reason about:

```
exit_code: 1
elapsed: 0.3s
stderr:
  Traceback (most recent call last):
    File "sessions/20260518_161234_run_code_001.py", line 4, in <module>
      result = re.search(pattern, line).group(1)
  AttributeError: 'NoneType' object has no attribute 'group'
```

Every script is kept permanently — whether the run succeeds or fails — so you
can inspect, diff, or re-run any version that was attempted.

With `--confirm`, Executor prints the script to stderr and prompts `[y/N]`
before running. Answering `n` reports cancellation back to Commander.

Timeout is 30 seconds by default. Override with `--timeout N` or permanently
in `config.py` via `EXECUTOR_TIMEOUT`.

### Sandbox Rules

Two rules are always enforced — they cannot be overridden at runtime:

**1. No install commands.**
The following are blocked before execution. Any script containing them is
rejected and the error is returned to Commander:

```
pip install     pip3 install    apt install     apt-get install
npm install     yarn add        cargo install   gem install
conda install   brew install    snap install    pipx install
```

**2. Tools folder only.**
The subprocess `PATH` is set exclusively to `./tools/`. Scripts may only
invoke external binaries placed there. System binaries (`curl`, `nmap`,
`jq`, etc.) are not accessible unless copied or symlinked into the
appropriate subfolder.

---

## Tools Folder

External binaries available to Cabal scripts go in `./tools/`. The folder
structure is organised by category:

```
tools/
  OSINT/       — reconnaissance and intelligence gathering tools
  Pentest/     — exploitation and assessment tools
  Network/     — network scanning, capture, and analysis tools
  Code/        — code analysis, decompilers, linters
  Payloads/    — payload generators and delivery tools
```

**To make a tool available to Cabal:**

```bash
cp $(which nmap) tools/Network/
cp $(which jq)   tools/OSINT/
```

Or symlink:

```bash
ln -s $(which nmap) tools/Network/nmap
```

The folder structure is tracked in git. **Contents are not** — every file
inside `tools/` and its subfolders is gitignored and stays local.

### Built-in Adapters

Two adapters ship with Cabal and live in `tools/Code/` after building.
They bridge language translation and endpoint interaction for scripts
running under Cabal's sandboxed executor.

#### `adapter` — Java Adapter

Translates between Python and Java, and calls Java endpoints.
Requires JDK 17+. Build with `./java/build.sh`.

```
adapter py2java <file.py> [-o out.java]     Translate Python → Java
adapter java2py <file.java> [-o out.py]     Translate Java → Python
adapter call <url> [METHOD] [json_body]     HTTP call to a Java endpoint
adapter probe <url>                         Probe endpoint reachability and headers
```

Useful for interacting with Spring Boot, Tomcat, JMX, and other JVM services.

#### `go-adapter` — Go Adapter

Translates between Python/Java and Go, compiles and runs Go code, and calls
endpoints. Compiles to a static binary — no runtime required.
Requires Go 1.21+. Build with `./go/build.sh`.

```
go-adapter py2go   <file.py>   [-o out.go]     Translate Python → Go
go-adapter go2py   <file.go>   [-o out.py]     Translate Go → Python
go-adapter java2go <file.java> [-o out.go]     Translate Java → Go
go-adapter go2java <file.go>   [-o out.java]   Translate Go → Java
go-adapter run     <file.go>   [-- args...]    Compile and run a Go file
go-adapter build   <file.go>   [-o binary]     Compile Go to a binary
go-adapter call    <url>       [METHOD] [body] HTTP call to an endpoint
go-adapter probe   <url>                       Probe endpoint reachability
```

`build` is particularly useful for compiling Go security tools directly into
a `tools/` subfolder so Cabal scripts can invoke them:

```bash
go-adapter build scanner.go -o tools/Network/scanner
```

**Building both adapters:**

```bash
./java/build.sh
./go/build.sh
```

Both translators call the local Ollama instance (`deepseek-coder-v2`).
Set `OLLAMA_BASE_URL` to override.

---

## Sessions and Output Files

Every run writes files to `./sessions/` with a shared timestamp prefix:

```
sessions/
  20260518_161234_run.txt            ← full session log (always written)
  20260518_161234_run_code_001.py    ← first script Executor ran
  20260518_161234_run_code_002.py    ← second script (after a fix attempt)
  20260518_161234_run_notes.txt      ← failure notes (only on failed runs)
```

**Session log (`_run.txt`):** full raw log — Commander rounds including
`<think>` blocks, every agent call and response, dispatch decisions, Executor
results, and the final answer. Written incrementally (line-buffered) so you
can tail it mid-run:

```bash
tail -f $(cabal pull --path)
```

**Code files (`_code_NNN.<ext>`):** every script the Executor runs is saved
with a sequential counter. Files persist whether the run succeeds or fails —
use them to inspect, diff, or re-run any version that was attempted.

**Failure notes (`_notes.txt`):** written only when all attempts are exhausted
without success. Contains a structured summary of every attempt:

```
CABAL FAILURE NOTES
════════════════════════════════════════════════════════════
task     : write a script that monitors open ports
attempts : 3
session  : sessions/20260518_161234_run.txt

────────────────────────────────────────────────────────────
ATTEMPT HISTORY
────────────────────────────────────────────────────────────

Attempt 1:
  exit_code : 1
  error     :
    AttributeError: 'NoneType' object has no attribute 'group'
  code      :
    import re
    result = re.search(pattern, line).group(1)

Attempt 2:
  exit_code : 1
  error     :
    IndexError: list index out of range
  code      :
    ...

────────────────────────────────────────────────────────────
LAST KNOWN STATE
────────────────────────────────────────────────────────────
exit_code : 1
...

════════════════════════════════════════════════════════════
All 3 attempt(s) exhausted without a passing execution.
Full session log: sessions/20260518_161234_run.txt
════════════════════════════════════════════════════════════
```

---

## LLM Logging

Raw model output — including deepseek-r1 `<think>` blocks — streams to stderr
in real time so you can follow what each model is doing.

```
╔═ COMMANDER  round 1 ══════════...
║  <think>The task requires...
╚═══════════════════════════════...
  → CODER  write a script that...

┌─ CODER  deepseek-coder-v2:latest
│  write a script that...
│  ```python
│  ...
└───────────────────────────────...
```

Suppress with `CABAL_QUIET=1` or the `quiet` subcommand in `c.sh`:

```bash
./c.sh quiet run "task"
CABAL_QUIET=1 cabal run "task"
```

Session files are always written regardless of `CABAL_QUIET`.

---

## Configuration (`config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `MODELS["commander"]` | `deepseek-r1:8b` | Commander model |
| `MODELS["researcher"]` | `deepseek-coder-v2:latest` | Researcher model |
| `MODELS["coder"]` | `deepseek-coder-v2:latest` | Coder model |
| `MODELS["recon"]` | `wizard-vicuna-uncensored:latest` | Recon model |
| `MODELS["analyst"]` | `dolphin-llama3:8b` | Analyst model |
| `SESSION_DIR` | `./sessions` | Session file output directory |
| `MAX_ROUNDS` | `10` | Default Commander rounds per attempt |
| `EXECUTOR_TIMEOUT` | `30` | Script execution timeout (seconds) |

---

## Installation

**1. Install Python dependency:**

```bash
pip3 install requests
```

**2. Install Ollama:** https://ollama.ai

**3. Pull required models:**

```bash
./pull_models.sh
```

Models are stored in `~/.ollama/models` by default. To store them locally
inside the project folder instead:

```bash
OLLAMA_MODELS="$(pwd)/models" ./pull_models.sh
```

**Required models:**

| Model | Role | ~Size |
|-------|------|-------|
| `deepseek-r1:8b` | Commander — orchestration, chain-of-thought reasoning | 4.9 GB |
| `deepseek-coder-v2:latest` | Researcher + Coder — technical research, code gen | 8.9 GB |
| `wizard-vicuna-uncensored:latest` | Recon — red team reasoning, no refusals | 3.8 GB |
| `dolphin-llama3:8b` | Analyst — synthesis, report writing | 4.7 GB |

Total: ~22 GB. Ollama must be running (`ollama serve`) before use.

**4. Build adapters (optional):**

```bash
./java/build.sh    # requires JDK 17+
./go/build.sh      # requires Go 1.21+
```

---

## Quick Reference

```
cabal run "task"                      Commander orchestrates agents
cabal run "task" --attempts 0         Retry until script passes
cabal run "task" --attempts 5         Retry up to 5 times
cabal run "task" --rounds 20          More rounds per attempt
cabal run "task" --claude             Consult Claude Code when stuck
cabal run "task" --confirm            Prompt before each script execution
cabal run "task" --timeout 60         Executor timeout 60s
cabal ask "question"                  Commander direct answer
cabal research "topic"                Direct to Researcher
cabal code "task"                     Direct to Coder
cabal recon "scenario"                Direct to Recon
cabal analyse "task"                  Direct to Analyst
cabal pull                            Print latest session
cabal pull --path                     Print session file path
./c.sh quiet run "task"               Run with LLM logging suppressed
```

---

*Red-Macaw · Alpine Shield Project*
