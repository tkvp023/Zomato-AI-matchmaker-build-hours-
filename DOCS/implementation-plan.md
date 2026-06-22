# Phase-Wise Implementation Plan

> AI-Powered Restaurant Recommendation System (Zomato Use Case)  
> Derived from [context.md](context.md) and [architecture.md](architecture.md)

---

## Overview

This plan breaks the project into **7 phases**, ordered by dependency. Each phase has clear goals, tasks, deliverables, and acceptance criteria. Phases 0–6 deliver a working **Streamlit MVP** with Groq-powered recommendations. Phase 7 is optional for a production-style REST API.

### Implementation Roadmap

```
Phase 0          Phase 1           Phase 2            Phase 3
Foundation  ──▶  Data Layer   ──▶  Filtering    ──▶  Groq Engine
(setup)          (ingest)          (integration)      (LLM)

Phase 4          Phase 5           Phase 6            Phase 7
Orchestrator ──▶ UI (Streamlit) ─▶ Test & Harden ──▶ API (optional)
(pipeline)       (display)         (quality)
```

### Requirements Coverage Map

| Context requirement | Phase(s) |
|---------------------|----------|
| Load Zomato dataset from Hugging Face | 1 |
| Preprocess and extract restaurant fields | 1 |
| Accept user preferences | 2, 5 |
| Filter dataset based on user input | 2 |
| Build LLM prompt with structured data | 3 |
| LLM ranks and generates explanations (Groq) | 3, 4 |
| Display name, cuisine, rating, cost, explanation | 5 |

---

## Phase 0: Project Foundation

**Goal:** Establish project structure, dependencies, configuration, and development environment so later phases can proceed without rework.

**Architecture refs:** §10 (Tech Stack), §11 (Project Structure), §17 (Deployment — env vars)

### Tasks

- [x] **0.1** Initialize Python project (Python 3.11+)
  - Create folder structure per architecture §11
  - Add `app/`, `app/data/`, `app/models/`, `app/services/`, `app/ui/`, `tests/`, `data/cache/`

- [x] **0.2** Create `requirements.txt` with pinned dependencies:
  ```
  datasets
  pandas
  pydantic
  pydantic-settings
  python-dotenv
  groq
  rapidfuzz
  streamlit
  pytest
  ```

- [x] **0.3** Implement `app/config.py` using `pydantic-settings`
  - `HF_DATASET_ID` (default: `ManikaSaini/zomato-restaurant-recommendation`)
  - `GROQ_API_KEY`, `GROQ_MODEL` (default: `llama-3.3-70b-versatile`)
  - `TOP_K_CANDIDATES` (default: 25), `TOP_N_RECOMMENDATIONS` (default: 5)
  - `CACHE_DIR` (default: `./data/cache`)

- [x] **0.4** Add `.env.example` and `.gitignore`
  - Ignore `.env`, `data/cache/`, `__pycache__/`, `.pytest_cache/`

- [ ] **0.5** Obtain Groq API key from [console.groq.com](https://console.groq.com/) and add to local `.env`

- [x] **0.6** Add minimal `README.md` with setup instructions (clone, venv, install, env vars, run)

### Deliverables

| Artifact | Path |
|----------|------|
| Project scaffold | `app/`, `tests/`, `data/cache/` |
| Config module | `app/config.py` |
| Dependencies | `requirements.txt` |
| Env template | `.env.example` |

### Acceptance Criteria

- [x] `pip install -r requirements.txt` succeeds
- [x] `from app.config import settings` loads without error when `.env` is present
- [x] Project structure matches architecture §11

**Estimated effort:** 1–2 hours

---

## Phase 1: Data Layer — Ingestion & Preprocessing

**Goal:** Load the Zomato dataset from Hugging Face, normalize it into a canonical schema, cache processed data, and expose a queryable in-memory repository.

**Architecture refs:** §4.1, §5, §6.2

**Context refs:** Data Ingestion workflow, Dataset section

### Tasks

- [ ] **1.1** Define Pydantic models in `app/models/restaurant.py`
  - `Restaurant` schema (id, name, location, city, cuisine, rating, cost_for_two, budget_tier, address, tags)

- [ ] **1.2** Implement `app/data/loader.py` — `DatasetLoader`
  - Fetch dataset via Hugging Face `datasets` library
  - Handle network errors with retry + backoff
  - Return raw records as pandas DataFrame or list of dicts

- [ ] **1.3** Implement `app/data/preprocessor.py` — normalization pipeline
  - Drop rows missing name, location, or rating
  - Normalize locations (lowercase → trim → alias map for common variants)
  - Normalize cuisines (split, title-case, deduplicate)
  - Parse `cost_for_two` from strings (e.g. `"₹600 for two"` → `600`)
  - Assign `budget_tier` (low / medium / high) from cost quantiles or fixed thresholds
  - Normalize ratings to float 0–5
  - Generate stable `id` if not present in source data

- [ ] **1.4** Implement local cache
  - Save preprocessed data to Parquet in `data/cache/`
  - On startup: load cache if exists; otherwise download → preprocess → save

- [ ] **1.5** Implement `app/data/repository.py` — `RestaurantRepository`
  - `get_all() -> List[Restaurant]`
  - `get_locations() -> List[str]` (sorted, unique)
  - `get_cuisines() -> List[str]` (sorted, unique)
  - `get_by_id(id) -> Restaurant | None`

- [ ] **1.6** Write unit tests in `tests/test_preprocessor.py`
  - Location normalization edge cases
  - Cost parsing from varied string formats
  - Budget tier assignment
  - Null row dropping

- [ ] **1.7** Smoke-test loader end-to-end
  - Script or pytest that loads dataset, prints record count, sample locations/cuisines

### Deliverables

| Artifact | Path |
|----------|------|
| Restaurant model | `app/models/restaurant.py` |
| Dataset loader | `app/data/loader.py` |
| Preprocessor | `app/data/preprocessor.py` |
| Repository | `app/data/repository.py` |
| Cached data | `data/cache/restaurants.parquet` |
| Tests | `tests/test_preprocessor.py` |

### Acceptance Criteria

- [ ] Dataset loads from Hugging Face on first run
- [ ] Second run uses cached Parquet (no re-download)
- [ ] Repository returns ≥ 1 valid `Restaurant` with all required fields populated
- [ ] `get_locations()` and `get_cuisines()` return non-empty sorted lists
- [ ] All preprocessor unit tests pass

**Estimated effort:** 4–6 hours

**Depends on:** Phase 0

---

## Phase 2: Filtering Service & User Preferences

**Goal:** Accept and validate user preferences; deterministically filter restaurants to a bounded candidate set (`TOP_K`) ready for LLM prompting.

**Architecture refs:** §4.2, §4.3, §7.1, §7.2

**Context refs:** User Input, Integration Layer (filtering)

### Tasks

- [ ] **2.1** Define `UserPreferences` in `app/models/preferences.py`
  ```python
  location: str                    # required
  budget: Literal["low","medium","high"]  # required
  cuisine: str | None              # optional
  min_rating: float = 0.0          # optional, default 0
  additional_preferences: str | None  # optional, max 500 chars
  ```

- [ ] **2.2** Implement preference validation
  - Fuzzy-match `location` against repository vocabulary (`rapidfuzz`, threshold ≥ 80)
  - Fuzzy-match `cuisine` if provided
  - Clamp `min_rating` to 0–5
  - Return validation errors with suggested closest locations on failure

- [ ] **2.3** Implement `app/services/filter_service.py`
  - Filter pipeline (in order):
    1. Location (case-insensitive substring or fuzzy)
    2. Rating (`rating >= min_rating`)
    3. Cuisine (token match in cuisine field)
    4. Budget (`budget_tier == prefs.budget`)
    5. Keyword scan on tags/name/cuisine for `additional_preferences` (soft boost, not hard exclude)
  - Cap results to `TOP_K_CANDIDATES` (pre-sort by rating desc)

- [ ] **2.4** Return filter metadata
  - Count before/after each filter stage (for debugging and UI display)
  - Empty candidate list with actionable message

- [ ] **2.5** Write unit tests in `tests/test_filter_service.py`
  - Single-filter tests (location only, budget only, etc.)
  - Combined filter tests
  - TOP_K cap behavior
  - Zero-result scenario

### Deliverables

| Artifact | Path |
|----------|------|
| Preferences model | `app/models/preferences.py` |
| Filter service | `app/services/filter_service.py` |
| Tests | `tests/test_filter_service.py` |

### Acceptance Criteria

- [ ] Valid preferences for "Indiranagar", medium budget return ≤ `TOP_K` candidates
- [ ] Impossible filter combo returns empty list without crashing
- [ ] Location fuzzy match resolves "indira nagar" → "Indiranagar"
- [ ] All filter unit tests pass

**Estimated effort:** 3–4 hours

**Depends on:** Phase 1

---

## Phase 3: Groq Integration & Prompt Engineering

**Goal:** Build the prompt template, integrate the Groq SDK, parse structured JSON responses, and implement a deterministic fallback ranker.

**Architecture refs:** §4.4, §4.5, §8

**Context refs:** Recommendation Engine, Integration Layer (prompt design)

### Tasks

- [x] **3.1** Define output models in `app/models/recommendation.py`
  - `Recommendation` (rank, restaurant_name, cuisine, rating, estimated_cost, location, explanation)
  - `RecommendationResponse` (recommendations, summary, total_candidates_considered, filters_applied)
  - `GroqRawResponse` (schema for parsed LLM JSON)

- [x] **3.2** Implement `app/services/prompt_builder.py`
  - System prompt: role, ranking rules, JSON schema, anti-hallucination constraints
  - User prompt: serialized preferences + compact JSON array of candidates (name, cuisine, rating, cost, location, tags)
  - Parameterize `top_n` in prompt
  - Unit test: prompt contains all user prefs and all candidate names

- [x] **3.3** Implement `app/services/groq_service.py` — `GroqProvider`
  - Initialize `Groq` client with `GROQ_API_KEY`
  - `rank_and_explain(messages, top_n) -> GroqRawResponse`
  - Use `temperature=0.3`, `response_format={"type": "json_object"}` where supported
  - Set client timeout (30s)
  - Handle `429` rate limits with exponential backoff (max 2 retries)

- [x] **3.4** Implement response parsing & merge logic
  - Parse Groq JSON output
  - Validate with Pydantic
  - Merge LLM rank + explanation with canonical fields from candidate records (rating, cost, cuisine)
  - Reject recommendations for restaurants not in candidate list

- [x] **3.5** Implement fallback ranker in `groq_service.py`
  - Deterministic scoring: rating (0.5) + budget match (0.3) + cuisine match (0.2) + keyword overlap
  - Template explanations when Groq fails or returns invalid JSON
  - Log when fallback is activated

- [x] **3.6** Write tests in `tests/test_groq_service.py` and `tests/test_prompt_builder.py`
  - Mock Groq client; no live API calls in CI
  - Malformed JSON → fallback triggered
  - Valid JSON → correct `Recommendation` objects
  - Prompt snapshot test (structure stable)

- [x] **3.7** Manual smoke test with live Groq API
  - Run against 5–10 real candidates; verify JSON parse and explanation quality

### Deliverables

| Artifact | Path |
|----------|------|
| Recommendation models | `app/models/recommendation.py` |
| Prompt builder | `app/services/prompt_builder.py` |
| Groq service + fallback | `app/services/groq_service.py` |
| Tests | `tests/test_prompt_builder.py`, `tests/test_groq_service.py` |

### Acceptance Criteria

- [x] Live Groq call returns valid JSON with `top_n` recommendations
- [x] Each explanation references at least one user preference
- [x] Invalid/missing Groq response triggers fallback without crashing
- [x] No restaurant appears in output that wasn't in the candidate list
- [x] All unit tests pass (mocked Groq)

**Estimated effort:** 5–7 hours

**Depends on:** Phase 2

---

## Phase 4: Orchestrator — End-to-End Pipeline

**Goal:** Wire all services into a single coordinator that executes the full recommendation flow from validated preferences to formatted response.

**Architecture refs:** §3 (Application Layer), §6.1 (Sequence Flow), §4.6

### Tasks

- [x] **4.1** Implement `app/services/orchestrator.py` — `RecommendationOrchestrator`
  - Pipeline steps:
    1. Validate `UserPreferences`
    2. Apply filters → candidates
    3. If zero candidates → return empty `RecommendationResponse` with suggestions
    4. Build prompt via `PromptBuilder`
    5. Call `GroqProvider.rank_and_explain`
    6. Merge and format into `RecommendationResponse`
  - Inject dependencies (repository, filter, prompt builder, groq service) for testability

- [x] **4.2** Implement output formatter logic (inline or separate module)
  - Format `estimated_cost` as human-readable string (e.g. `"₹600 for two"`)
  - Attach `filters_applied` and `total_candidates_considered` to response

- [x] **4.3** Add structured logging
  - Log: filter counts, candidate count, Groq latency, fallback activation

- [x] **4.4** Write integration tests in `tests/test_orchestrator.py`
  - Mock Groq; full pipeline from preferences → `RecommendationResponse`
  - Zero-candidate path
  - Fallback path when Groq raises exception

- [x] **4.5** CLI smoke script (optional)
  - `python -m app.main --cli` with hardcoded or stdin preferences for quick debugging

### Deliverables

| Artifact | Path |
|----------|------|
| Orchestrator | `app/services/orchestrator.py` |
| Integration tests | `tests/test_orchestrator.py` |

### Acceptance Criteria

- [x] End-to-end call with mocked Groq returns valid `RecommendationResponse`
- [x] Response contains exactly `TOP_N_RECOMMENDATIONS` items when enough candidates exist
- [x] Empty filter result returns structured empty response (not an exception)
- [x] Groq failure returns fallback recommendations with `explanation` populated
- [x] Full pytest suite passes

**Estimated effort:** 3–4 hours

**Depends on:** Phases 2, 3

---

## Phase 5A: FastAPI REST API — Backend for React Frontend

**Goal:** Expose the recommendation pipeline as a FastAPI REST service with CORS support, enabling the React frontend to consume it.

**Architecture refs:** §12, §17 (Production topology)

### Tasks

- [ ] **5A.1** Add FastAPI dependencies to `requirements.txt`
  ```
  fastapi
  uvicorn[standard]
  httpx  (for API tests)
  ```

- [ ] **5A.2** Implement API routes in `app/api/routes.py`
  - `POST /api/v1/recommendations` — body matches `UserPreferences` + optional `top_n`
    - Returns `RecommendationResponse` as JSON
  - `GET /api/v1/metadata` — returns `{ locations, cuisines, budget_tiers, rating_range }`
    - Used by React frontend to populate dropdowns
  - `GET /health` — returns `{ status, dataset_loaded, restaurant_count, groq_configured }`

- [ ] **5A.3** Implement FastAPI app entry in `app/api/main.py`
  - Wire startup event to load repository (same cache path)
  - Initialize orchestrator with all services
  - Enable CORS middleware for `localhost:5173` (Vite dev server) and production origins
  - Mount `/api/v1/` router

- [ ] **5A.4** Add request validation and error responses
  - `400` — invalid preferences (with suggestions)
  - `422` — Pydantic validation errors (auto-handled by FastAPI)
  - `502` — Groq upstream failure (but still return fallback results in body)
  - `503` — dataset not loaded yet

- [ ] **5A.5** API response models (Pydantic)
  - Reuse existing `RecommendationResponse` model
  - Add `MetadataResponse` model: `{ locations: list[str], cuisines: list[str], budget_tiers: list[str], rating_range: { min: 0, max: 5 } }`
  - Add `HealthResponse` model

- [ ] **5A.6** Write API integration tests in `tests/test_api.py`
  - Use `httpx.AsyncClient` + FastAPI `TestClient`
  - Mock Groq; test full request→response cycle
  - Test validation errors return 400 with suggestions
  - Test `/metadata` returns populated lists
  - Test `/health` returns correct status

### Deliverables

| Artifact | Path |
|----------|------|
| API routes | `app/api/routes.py` |
| API entry point | `app/api/main.py` |
| Response models | `app/api/models.py` (or extend existing) |
| API tests | `tests/test_api.py` |

### Acceptance Criteria

- [x] `uvicorn app.api.main:app --reload` starts and `/health` returns 200
- [x] `POST /api/v1/recommendations` returns valid JSON with recommendations
- [x] `GET /api/v1/metadata` returns populated location/cuisine lists
- [x] CORS headers present for frontend origins
- [x] API tests pass with mocked Groq
- [x] Error responses return structured JSON (not HTML stack traces)

**Estimated effort:** 3–4 hours

**Depends on:** Phase 4

---

## Phase 5B: React + Vite — Premium Frontend

**Goal:** Build a visually stunning, production-quality React SPA with a modern dark theme, glassmorphism effects, micro-animations, and rich interactivity — consuming the FastAPI backend via REST calls.

**Tech stack:** React 18+ · Vite · Vanilla CSS (custom design system) · Fetch API

### Design System

#### Color Palette (Dark Theme)
```
Background (primary):    #0F0F1A  (deep navy-black)
Background (secondary):  #161625  (slightly lighter)
Background (card):       rgba(255, 255, 255, 0.05) with backdrop-blur
Accent gradient:         linear-gradient(135deg, #667eea, #764ba2)  (indigo → purple)
Accent secondary:        #f093fb → #f5576c  (pink-rose)
Success accent:          #00d2ff → #3a7bd5  (cyan-blue)
Text primary:            #F0F0F5
Text secondary:          #9CA3AF
Text muted:              #6B7280
Rating stars:            #FFC107  (amber gold)
Budget badge - low:      #10B981  (emerald)
Budget badge - medium:   #F59E0B  (amber)
Budget badge - high:     #EF4444  (red)
Dividers / borders:      rgba(255, 255, 255, 0.08)
```

#### Typography
- **Primary font:** `'Inter', sans-serif` (Google Fonts)
- **Headings:** Semi-bold/Bold, tracked slightly wider
- **Body text:** 400 weight, 1.6 line-height
- **Monospace accents:** `'JetBrains Mono'` for metadata/stats

#### Design Tokens
- **Border radius:** 16px (cards), 12px (inputs), 24px (pills/badges)
- **Glassmorphism:** `background: rgba(255,255,255,0.05); backdrop-filter: blur(16px); border: 1px solid rgba(255,255,255,0.08)`
- **Shadows:** `0 8px 32px rgba(0, 0, 0, 0.3)` for elevated cards
- **Transitions:** `all 0.3s cubic-bezier(0.4, 0, 0.2, 1)` for hover effects

### Project Structure

```
frontend/
├── index.html
├── package.json
├── vite.config.js
├── public/
│   └── favicon.svg
├── src/
│   ├── main.jsx               # App entry
│   ├── App.jsx                # Root component + routing
│   ├── App.css                # Global styles + design system
│   ├── api/
│   │   └── client.js          # Fetch wrapper for FastAPI calls
│   ├── components/
│   │   ├── Hero.jsx           # Animated hero section
│   │   ├── Hero.css
│   │   ├── PreferenceForm.jsx # Search form with dropdowns
│   │   ├── PreferenceForm.css
│   │   ├── RecommendationCard.jsx  # Single result card
│   │   ├── RecommendationCard.css
│   │   ├── ResultsBanner.jsx  # Summary banner above cards
│   │   ├── ResultsBanner.css
│   │   ├── LoadingState.jsx   # Animated loading spinner
│   │   ├── LoadingState.css
│   │   ├── EmptyState.jsx     # No results view
│   │   ├── EmptyState.css
│   │   ├── ErrorState.jsx     # Error display
│   │   ├── ErrorState.css
│   │   ├── StatsBar.jsx       # Dataset stats counter
│   │   └── StatsBar.css
│   └── hooks/
│       ├── useMetadata.js     # Fetch locations/cuisines on mount
│       └── useRecommendations.js  # POST preferences, manage loading state
```

### Tasks

- [ ] **5B.1** Scaffold React + Vite project
  - `npx -y create-vite@latest frontend -- --template react` (or init in `frontend/`)
  - Configure `vite.config.js` with API proxy to `http://localhost:8000` for dev
  - Install no extra dependencies — use Vanilla CSS + Fetch API only

- [ ] **5B.2** Implement design system — `src/App.css`
  - CSS custom properties (`:root`) for all design tokens
  - Google Fonts import (`Inter`, `JetBrains Mono`)
  - Dark background gradient across full page
  - Glassmorphism utility classes (`.glass-card`, `.glass-panel`)
  - Animated gradient text utility (`.gradient-text`)
  - Responsive grid system for cards
  - Global resets and scrollbar styling
  - Keyframe animations: `fadeInUp`, `slideIn`, `pulse`, `shimmer`

- [ ] **5B.3** Build API client — `src/api/client.js`
  - `fetchMetadata()` → `GET /api/v1/metadata`
  - `fetchRecommendations(preferences)` → `POST /api/v1/recommendations`
  - `fetchHealth()` → `GET /health`
  - Error handling: network errors, 4xx/5xx responses → structured error objects
  - Base URL from env var (`VITE_API_URL`) or proxy fallback

- [ ] **5B.4** Build Hero component — animated header section
  - Animated gradient text title: "🍽️ Zomato AI Recommender"
  - Subtitle with fade-in: "Discover your next favourite restaurant, powered by AI"
  - Subtle animated gradient mesh background (CSS `@keyframes` gradients)
  - Stats bar showing: total restaurants, cuisines, locations (from `/metadata`)

- [ ] **5B.5** Build PreferenceForm component
  - **Layout:** Glassmorphism panel, centered, max-width 600px
  - **Location:** Custom-styled `<select>` populated from API metadata
  - **Budget:** Radio group with emoji icons (💰 Low · 💳 Medium · 💎 High)
  - **Cuisine:** `<select>` with "🌍 Any Cuisine" default
  - **Min rating:** Range slider (0.0–5.0, step 0.5) with live star preview
  - **Additional preferences:** `<textarea>` with placeholder: "e.g. rooftop seating, live music, vegan…"
  - **Submit button:** Large gradient button "✨ Get Recommendations" with hover glow + ripple effect
  - Client-side validation with inline error messages
  - Disable form during loading

- [ ] **5B.6** Build RecommendationCard component
  - **Card layout:** Glassmorphism with hover-lift animation (`transform: translateY(-4px)`)
  - **Rank badge:** Gradient circle — gold (#FFD700) for #1, silver (#C0C0C0) #2, bronze (#CD7F32) #3, muted for rest
  - **Restaurant name:** Large, bold, white `<h3>`
  - **Star rating:** Filled/empty star icons in amber gold + numeric `(4.2/5)`
  - **Cuisine tags:** Pill-shaped `<span>` badges with gradient backgrounds
  - **Location:** 📍 icon + location text
  - **Cost badge:** Colored pill (emerald/amber/red based on budget tier) — `₹600 for two`
  - **AI explanation:** Blockquote with gradient left border, italic text, subtle background
  - **Fallback indicator:** "📊 Ranked by data" vs "🤖 AI Ranked" badge
  - Staggered entrance animation (`animation-delay: calc(var(--i) * 0.1s)`)

- [ ] **5B.7** Build ResultsBanner component
  - Glassmorphism banner with gradient left border accent
  - LLM summary text (or fallback message)
  - Metadata: "Considered X candidates · Filtered from Y restaurants · Powered by Llama 3.3"
  - Fallback warning variant: amber border + "AI ranking unavailable" message

- [ ] **5B.8** Build UI state components
  - **LoadingState:** CSS-only animated spinner (3 pulsing gradient dots) + rotating status messages ("Analysing preferences…", "Consulting the AI…", "Ranking picks…") via `setInterval`
  - **EmptyState:** Large 🔍 icon, explanation text, suggestion pills ("Try lower rating", "Try another area") as clickable buttons that auto-fill form
  - **ErrorState:** 🛠️ icon, friendly message, "Try Again" button. If fallback results exist, render cards below

- [ ] **5B.9** Build custom hooks
  - `useMetadata()`: fetch on mount, cache in state, return `{ locations, cuisines, loading, error }`
  - `useRecommendations()`: `submit(prefs)` function, return `{ data, loading, error, submit }`

- [ ] **5B.10** Wire up App.jsx
  - Fetch metadata on mount via `useMetadata`
  - Render: Hero → PreferenceForm → (LoadingState | ResultsBanner + Cards | EmptyState | ErrorState)
  - Smooth scroll to results section after submission
  - SEO: proper `<title>`, `<meta>` tags in `index.html`

- [ ] **5B.11** Polish & micro-interactions
  - Button hover: gradient shift + scale(1.02) + box-shadow glow
  - Card hover: translateY(-4px) + border glow + shadow increase
  - Focus states: animated gradient border on inputs
  - Smooth scroll-to-results after form submit
  - Skeleton loading shimmer on stats bar during metadata fetch
  - Animated number counters for stats
  - Custom styled scrollbar (thin, accent-colored)

- [ ] **5B.12** Manual E2E testing matrix
  - Run FastAPI backend + Vite dev server simultaneously
  - Test locations: Indiranagar, Whitefield, Church Street, Koramangala
  - Test all 3 budget tiers with various cuisines
  - Test edge cases: no cuisine selected, max rating slider, long additional_preferences
  - Verify fallback UI when Groq key is invalid
  - Verify empty state renders with actionable suggestions
  - Verify loading animations are smooth
  - Verify responsive layout at 1440px, 1024px, 768px, 375px widths
  - Test error state when API is unreachable

### Deliverables

| Artifact | Path | Purpose |
|----------|------|---------|
| Vite project | `frontend/` | React SPA scaffold |
| Design system | `frontend/src/App.css` | Full dark theme, tokens, animations |
| API client | `frontend/src/api/client.js` | REST calls to FastAPI |
| Hero | `frontend/src/components/Hero.jsx` | Animated header + stats |
| Form | `frontend/src/components/PreferenceForm.jsx` | Preference input panel |
| Cards | `frontend/src/components/RecommendationCard.jsx` | Result display |
| State components | `frontend/src/components/Loading/Empty/ErrorState.jsx` | UI states |
| Hooks | `frontend/src/hooks/` | Data fetching logic |

### Visual Reference

```
┌─────────────────────────────────────────────────────────────┐
│                    ✦ gradient mesh bg ✦                      │
│                                                             │
│     🍽️  Z O M A T O   A I   R E C O M M E N D E R        │
│     Discover your next favourite restaurant, powered by AI  │
│                                                             │
│     ┌──────┐  ┌──────┐  ┌──────┐                           │
│     │ 8.2K │  │ 120+ │  │  45  │  ← animated counters      │
│     │Restaurants│Cuisines│Locations│                         │
│     └──────┘  └──────┘  └──────┘                           │
│                                                             │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ glassmorphism ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐    │
│  │  📍 Location  [Indiranagar                    ▼]   │    │
│  │  💰 Budget    (●) Low  (○) Medium  (○) High        │    │
│  │  🍕 Cuisine   [Italian                        ▼]   │    │
│  │  ⭐ Rating    ═══●════════════════════  3.5/5      │    │
│  │  📝 Notes     ┌─────────────────────────────┐      │    │
│  │               │ rooftop, romantic dinner     │      │    │
│  │               └─────────────────────────────┘      │    │
│  │                                                    │    │
│  │         ╔═══════════════════════════════╗          │    │
│  │         ║  ✨ Get Recommendations       ║ ← glow  │    │
│  │         ╚═══════════════════════════════╝          │    │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘    │
│                                                             │
│  ╔══ gradient border ═══════════════════════════════════╗   │
│  ║ 🤖 Found 5 great picks in Indiranagar               ║   │
│  ║    for a medium budget — Italian cuisine.            ║   │
│  ║    Considered 18 candidates · Powered by Llama 3.3   ║   │
│  ╚══════════════════════════════════════════════════════╝   │
│                                                             │
│  ┌─ glass card ─── fadeInUp delay:0s ────────────────┐     │
│  │  🥇                                               │     │
│  │  Toit Brewpub                      🤖 AI Ranked   │     │
│  │  ★★★★½ (4.5/5)     📍 Indiranagar                │     │
│  │  [Italian] [Continental]    💳 ₹800 for two       │     │
│  │                                                   │     │
│  │  ▎ "Perfect match for your romantic dinner —      │     │
│  │  ▎  rooftop seating with Italian specialties      │     │
│  │  ▎  and craft beers at a comfortable price."      │     │
│  └───────────────────────────────────────────────────┘     │
│                                                             │
│  ┌─ glass card ─── fadeInUp delay:0.1s ──────────────┐     │
│  │  🥈                                               │     │
│  │  Pasta Street                      🤖 AI Ranked   │     │
│  │  ★★★★ (4.2/5)      📍 Indiranagar                │     │
│  │  [Italian]                  💳 ₹600 for two       │     │
│  │                                                   │     │
│  │  ▎ "Authentic Italian pasta with a cozy           │     │
│  │  ▎  ambiance — great value in your budget."       │     │
│  └───────────────────────────────────────────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Acceptance Criteria

- [ ] `npm run dev` (in `frontend/`) starts Vite dev server
- [ ] Frontend connects to FastAPI backend and loads metadata
- [ ] Dark theme renders with Inter font, no browser defaults visible
- [ ] Form dropdowns populated from `/api/v1/metadata`
- [ ] Submitting valid preferences shows ≥ 1 recommendation card within ~5 seconds
- [ ] Cards display: rank badge (gold/silver/bronze), name, star rating, cuisine pills, location, cost badge, AI explanation
- [ ] Loading state shows animated spinner with rotating messages
- [ ] Empty state shows friendly message with clickable suggestion pills
- [ ] Fallback results display with "📊 Ranked by data" indicator
- [ ] Hover effects work on cards (lift + glow) and button (scale + glow)
- [ ] No raw JSON or error stack traces visible to the user
- [ ] Layout is responsive and looks good at 1440px, 768px, and 375px
- [ ] API errors show user-friendly error state with retry button

**Estimated effort:** 6–8 hours

**Depends on:** Phase 5A

---

## Phase 6: Testing, Error Handling & Documentation

**Goal:** Harden the application with comprehensive tests, resilient error handling, security checks, and final documentation for demo/deployment.

**Architecture refs:** §13, §14, §16

### Tasks

- [ ] **6.1** Complete test coverage for critical paths
  - Run `pytest tests/ -v` — all green
  - Target: preprocessor, filters, prompt builder, groq (mocked), orchestrator, API routes

- [ ] **6.2** Harden error handling per architecture §13
  - Dataset download failure → retry + cache fallback message
  - Unknown location → suggest closest matches via API response
  - Groq timeout / 429 → retry then fallback (backend)
  - Invalid Groq JSON → retry with stricter prompt then fallback
  - API unreachable → React shows error state with retry

- [ ] **6.3** Security checklist per architecture §14
  - Confirm `.env` is gitignored; no API keys in source
  - Cap `additional_preferences` length in both frontend and backend
  - Sanitize free-text before prompt injection (strip control chars; system prompt instructs model to ignore overrides)
  - CORS configured for specific origins only (not `*` in production)

- [ ] **6.4** Performance sanity check per architecture §15
  - Filter stage < 50 ms on full dataset
  - Groq call typically < 3 s
  - API startup with cache < 5 s
  - Frontend bundle size < 200 KB (Vite optimised)

- [ ] **6.5** Update `README.md`
  - Project description, architecture overview link
  - Prerequisites: Python 3.11+, Node.js 18+
  - Backend: install, env setup, `uvicorn` run command
  - Frontend: `npm install`, `npm run dev`
  - Example user flow screenshot or description
  - Troubleshooting (Groq key, dataset download, CORS, empty results)

- [ ] **6.6** Update `context.md` checklist — mark all items complete

- [ ] **6.7** Demo script
  - Prepare 2–3 preset preference combos for live demo
  - Document expected output characteristics
  - Script to launch both backend and frontend with one command

### Deliverables

| Artifact | Description |
|----------|-------------|
| Full test suite | `tests/` — all passing |
| Hardened error paths | Across orchestrator, groq_service, API, React |
| README | Setup and usage guide (backend + frontend) |
| Demo presets | Documented in README or `DOCS/demo-scenarios.md` |

### Acceptance Criteria

- [ ] `pytest tests/ -v` — 100% pass rate
- [ ] App recovers gracefully when Groq API key is invalid (shows fallback or clear error)
- [ ] No secrets committed to repository
- [ ] README enables a new developer to run the full stack in < 15 minutes
- [ ] All context.md core requirements checked off

**Estimated effort:** 3–4 hours

**Depends on:** Phase 5B

---

## Master Checklist

Track overall progress across all phases:

### Data & Models
- [x] Phase 0 — Project scaffold and config
- [ ] Phase 1 — Dataset loaded, preprocessed, cached, repository ready

### Business Logic
- [ ] Phase 2 — User preferences validated; filter service returns TOP_K candidates
- [x] Phase 3 — Prompt builder + Groq service + fallback ranker working
- [x] Phase 4 — Orchestrator runs full pipeline end-to-end

### API Layer
- [ ] Phase 5A — FastAPI REST API serving recommendations and metadata

### User-Facing
- [ ] Phase 5B — React + Vite premium frontend with all UI states

### Quality & Ship
- [ ] Phase 6 — Tests pass; errors handled; README complete

---

## Timeline Estimate

| Phase | Focus | Effort | Cumulative |
|-------|-------|--------|------------|
| 0 | Foundation | 1–2 h | ~2 h |
| 1 | Data layer | 4–6 h | ~8 h |
| 2 | Filtering | 3–4 h | ~12 h |
| 3 | Groq engine | 5–7 h | ~19 h |
| 4 | Orchestrator | 3–4 h | ~23 h |
| 5A | **FastAPI REST API** | **3–4 h** | **~27 h** |
| 5B | **React + Vite Premium UI** | **6–8 h** | **~35 h** |
| 6 | Test & docs | 3–4 h | ~39 h |

**MVP (Phases 0–6):** approximately **28–39 hours** for a solo developer.

For a hackathon / build-hours sprint, prioritize Phases 0–4 + 5A first to get the API working, then 5B for the premium UI, then Phase 6 for polish.

---

## Suggested Build Order (Sprint Mode)

If time is limited, use this compressed sequence:

| Day / Session | Phases | Outcome |
|---------------|--------|---------|
| Session 1 | 0 + 1 | Data loading works; repository queryable |
| Session 2 | 2 + 3 | Filters work; Groq returns ranked JSON |
| Session 3 | 4 + 5A | API end-to-end; curl returns recommendations |
| Session 4 | 5B | React frontend with premium design |
| Session 5 | 6 | Tests, README, demo prep |

---

## Risk Register

| Risk | Impact | Mitigation | Phase |
|------|--------|------------|-------|
| Hugging Face dataset schema differs from docs | Preprocessing breaks | Inspect raw columns on first load; adapt field mapping | 1 |
| Groq rate limits during demo | Empty or slow responses | Cache a sample Groq response; use fallback ranker; use `llama-3.1-8b-instant` | 3, 6 |
| Zero filter matches for common locations | Poor demo UX | Verify location normalization; relax fuzzy threshold; demo preset locations | 1, 2, 5B |
| Groq returns invalid JSON | Pipeline crash | Pydantic validation + fallback ranker | 3 |
| Large dataset slow on first load | Long startup | Parquet cache; show loading screen in React | 1, 5B |
| CORS misconfiguration | Frontend can't reach API | Configure specific origins; test cross-origin in dev | 5A, 5B |
| React bundle too large | Slow page load | Vanilla CSS only, no heavy libs; Vite tree-shaking | 5B |

---

## Definition of Done (MVP)

The project is **complete** when all of the following are true:

1. FastAPI backend starts and `/health` returns 200 with dataset loaded
2. React frontend loads, displays metadata from API, and renders the preference form
3. User can select location/budget/cuisine/rating and submit preferences
4. System filters the Zomato dataset and sends ≤ 25 candidates to Groq
5. Groq returns top 5 ranked restaurants with personalized explanations
6. React UI displays glassmorphism cards with name, cuisine, rating, cost, and explanation
7. Groq failure degrades to fallback rankings without crashing; UI shows "Ranked by data"
8. Loading, empty, and error states render with polished animations
9. `pytest tests/ -v` passes
10. README documents full-stack setup and usage
11. All items in [context.md](context.md) Core Requirements Checklist are satisfied

---

## Related Documents

| Document | Purpose |
|----------|---------|
| [context.md](context.md) | Problem statement and requirements |
| [architecture.md](architecture.md) | System design, components, Groq integration |
| [DOCS/problemstatement.txt](DOCS/problemstatement.txt) | Original problem statement |

