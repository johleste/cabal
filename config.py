OLLAMA_BASE_URL = "http://localhost:11434"

# Model assignments — each role picks the model best suited to its job
MODELS = {
    "commander":  "deepseek-r1:8b",               # orchestrates, reasons, decides
    "researcher": "deepseek-coder-v2:latest",      # research, analysis, structured output
    "coder":      "deepseek-coder-v2:latest",      # code generation and review
    "recon":      "wizard-vicuna-uncensored:latest",# attack postulating, no refusals
    "analyst":    "dolphin-llama3:8b",             # synthesis, summaries, writing
}

SESSION_DIR = "./sessions"

MAX_ROUNDS = 10  # commander dispatch rounds; override per-run with --rounds
