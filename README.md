# AI-Powered Restaurant Recommendation System

Zomato-inspired restaurant recommender that combines structured filtering over a real dataset with Groq LLM ranking and explanations.

An AI-powered restaurant recommendation service inspired by Zomato. The system intelligently suggests restaurants based on user preferences by combining structured data with a Large Language Model (LLM).

## Documentation

| Document | Description |
|----------|-------------|
| [DOCS/context.md](DOCS/context.md) | Problem statement and requirements |
| [DOCS/architecture.md](DOCS/architecture.md) | System design and Groq integration |
| [DOCS/implementation-plan.md](DOCS/implementation-plan.md) | Phase-wise build plan |
| [DOCS/edge-case.md](DOCS/edge-case.md) | Edge cases and corner scenarios |

## Prerequisites

- Python 3.11+
- Node.js & npm (for the React frontend)
- [Groq API key](https://console.groq.com/)

## Setup

1. **Clone and enter the project**

   ```bash
   git clone https://github.com/tkvp023/Zomato-AI-matchmaker-build-hours-.git
   cd "Zomato-AI-matchmaker-build-hours-"
   ```

2. **Backend Setup**

   ```bash
   python -m venv .venv
   source .venv/Scripts/activate  # Windows
   pip install -r requirements.txt
   copy .env.example .env
   ```
   Edit `.env` and set your `GROQ_API_KEY`.

3. **Frontend Setup**

   ```bash
   cd frontend
   npm install
   ```

## Run the Application

Start the backend (FastAPI):
```bash
python -m uvicorn app.api.main:app --reload
```

Start the frontend (React + Vite):
```bash
cd frontend
npm run dev
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HF_DATASET_ID` | No | `ManikaSaini/zomato-restaurant-recommendation` | Hugging Face dataset ID |
| `GROQ_API_KEY` | Yes | — | Groq API key |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model name |
| `TOP_K_CANDIDATES` | No | `25` | Max candidates sent to Groq |
| `TOP_N_RECOMMENDATIONS` | No | `5` | Recommendations returned to user |

## License

MIT
