# Cabal

```
  █▀▀ ▄▀█ █▄▄ ▄▀█ █░░
  █▄▄ █▀█ █▄█ █▀█ █▄▄
  local multi-agent AI
```

Local multi-agent AI system. deepseek-r1:8b commands a council of specialist
Ollama models for research, agentic coding, and attack postulating.

No cloud. No telemetry. Runs entirely on Ollama.

---

## Agents

| Agent | Model | Role |
|---|---|---|
| Commander | `deepseek-r1:8b` | Orchestrates, reasons, dispatches, synthesizes |
| Researcher | `deepseek-coder-v2` | Technical research, structured analysis |
| Coder | `deepseek-coder-v2` | Code generation, review, debugging |
| Recon | `wizard-vicuna-uncensored` | Attack postulating, red team, no refusals |
| Analyst | `dolphin-llama3:8b` | Synthesis, report writing |

---

## Usage

```bash
# Commander orchestrates agents to complete a complex task
./c.sh run "research CVE-2024-12345 and write a proof-of-concept detector"

# Commander answers a direct question
./c.sh ask "what attack surface does a default Alpine Linux install expose?"

# Direct agent access
./c.sh research "how does SMB relay work"
./c.sh code "write a Python script to parse Suricata EVE JSON alerts"
./c.sh recon "target: nginx reverse proxy in front of a Flask app"
./c.sh analyse "summarise these findings: ..."

# Suppress LLM logging
./c.sh quiet run "task"
CABAL_QUIET=1 python3 cabal.py run "task"
```

---

## Installation

```bash
pip3 install requests
```

Requires Ollama running locally with models pulled:
```bash
ollama pull deepseek-r1:8b
ollama pull deepseek-coder-v2
ollama pull wizard-vicuna-uncensored
ollama pull dolphin-llama3:8b
```

---

## LLM Logging

Raw model output — including deepseek-r1 `<think>` blocks — is streamed to
stderr by default so you can follow what each model is actually doing.
Set `CABAL_QUIET=1` to suppress.

---

*Red-Macaw · Alpine Shield Project*
