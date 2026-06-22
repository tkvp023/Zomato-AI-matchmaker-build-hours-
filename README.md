# AI-Powered Restaurant Recommendation System

Zomato-inspired restaurant recommender that combines structured filtering over a real dataset with Groq LLM ranking and explanations.

## Documentation

| Document | Description |
|----------|-------------|
| [DOCS/context.md](DOCS/context.md) | Problem statement and requirements |
| [DOCS/architecture.md](DOCS/architecture.md) | System design and Groq integration |
| [DOCS/implementation-plan.md](DOCS/implementation-plan.md) | Phase-wise build plan |
| [DOCS/edge-case.md](DOCS/edge-case.md) | Edge cases and corner scenarios |

## Prerequisites

- Python 3.11+ (tested on 3.14; uses `pandas` 3.x wheels on newer runtimes)
- [Groq API key](https://console.groq.com/) (required from Phase 3 onward)

## Setup

1. **Clone and enter the project**

   ```bash
   cd "Build hours"
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv .venv
   ```

   Activate it:

   - Windows (PowerShell): `.venv\Scripts\Activate.ps1`
   - macOS/Linux: `source .venv/bin/activate`

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   ```bash
   copy .env.example .env
   ```

   Edit `.env` and set your `GROQ_API_KEY`.

5. **Verify Phase 0 setup**

   ```bash
   python -c "from app.config import settings; print(settings.hf_dataset_id)"
   pytest tests/test_config.py -v
   ```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HF_DATASET_ID` | No | `ManikaSaini/zomato-restaurant-recommendation` | Hugging Face dataset ID |
| `GROQ_API_KEY` | Phase 3+ | — | Groq API key |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model name |
| `TOP_K_CANDIDATES` | No | `25` | Max candidates sent to Groq |
| `TOP_N_RECOMMENDATIONS` | No | `5` | Recommendations returned to user |
| `CACHE_DIR` | No | `./data/cache` | Preprocessed dataset cache |

## Project Structure

```
app/
├── config.py          # Settings (pydantic-settings)
├── main.py            # Entry point
├── data/              # Dataset loader, preprocessor, repository (Phase 1)
├── models/            # Pydantic schemas (Phase 1–3)
├── services/          # Filter, Groq, orchestrator (Phase 2–4)
└── ui/                # Streamlit components (Phase 5)
data/cache/            # Cached dataset (gitignored)
tests/                 # pytest suite
DOCS/                  # Project documentation
```

## Run (after Phase 5)

```bash
streamlit run app/main.py
```

## Implementation Status

- [x] **Phase 0** — Project foundation
- [ ] Phase 1 — Data layer
- [ ] Phase 2 — Filtering
- [ ] Phase 3 — Groq engine
- [ ] Phase 4 — Orchestrator
- [ ] Phase 5 — Streamlit UI
- [ ] Phase 6 — Testing and hardening

## License

MIT (adjust as needed for your submission).
