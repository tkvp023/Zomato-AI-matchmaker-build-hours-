# Edge Cases & Corner Scenarios

> AI-Powered Restaurant Recommendation System (Zomato Use Case)  
> Companion to [context.md](context.md), [architecture.md](architecture.md), [implementation-plan.md](implementation-plan.md)

This document catalogs **edge cases, corner scenarios, and failure modes** across the full pipeline. Each entry includes the scenario, expected system behavior, and recommended handling.

---

## Table of Contents

1. [Dataset & Data Ingestion](#1-dataset--data-ingestion)
2. [Preprocessing & Normalization](#2-preprocessing--normalization)
3. [Repository & Startup](#3-repository--startup)
4. [User Input & Validation](#4-user-input--validation)
5. [Filtering Service](#5-filtering-service)
6. [Prompt Builder](#6-prompt-builder)
7. [Groq / LLM Engine](#7-groq--llm-engine)
8. [Orchestrator & Pipeline](#8-orchestrator--pipeline)
9. [Output Formatting & Display](#9-output-formatting--display)
10. [Streamlit UI](#10-streamlit-ui)
11. [REST API (Optional)](#11-rest-api-optional)
12. [Security & Abuse](#12-security--abuse)
13. [Concurrency & Performance](#13-concurrency--performance)
14. [Configuration & Environment](#14-configuration--environment)
15. [Cross-Cutting Scenarios](#15-cross-cutting-scenarios)

---

## Severity Legend

| Level | Meaning |
|-------|---------|
| 🔴 **Critical** | Can crash the app, leak data, or return dangerously wrong results |
| 🟠 **High** | Broken UX or incorrect recommendations; must handle before demo |
| 🟡 **Medium** | Degraded experience; should handle gracefully |
| 🟢 **Low** | Rare or cosmetic; nice to handle |

---

## 1. Dataset & Data Ingestion

### 1.1 Hugging Face download failures

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| D-01 | Network timeout during first download | 🟠 | Retry 3× with exponential backoff; show clear error if all fail |
| D-02 | Hugging Face service down (503) | 🟠 | Retry; if local cache exists, load cache and warn user |
| D-03 | Dataset removed or renamed on Hugging Face | 🔴 | Fail startup with message: dataset unavailable; document fallback CSV path |
| D-04 | Partial download (corrupt cache file) | 🟠 | Detect corrupt Parquet/pickle on load; delete cache and re-download |
| D-05 | Disk full while writing cache | 🟠 | Log error; run in-memory without cache; warn on next startup |
| D-06 | User has no internet on first run | 🔴 | Cannot proceed without dataset; show setup instructions |
| D-07 | Hugging Face rate limiting | 🟡 | Backoff and retry; suggest manual download |
| D-08 | Dataset requires authentication / gated access | 🟠 | Fail with message to set `HF_TOKEN` if needed |

### 1.2 Raw dataset structure surprises

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| D-09 | Column names differ from documentation | 🟠 | Field mapping config with aliases; log unmapped columns |
| D-10 | Empty dataset (0 rows) | 🔴 | Fail startup; "No restaurant data available" |
| D-11 | Dataset split has multiple configs (train/test) | 🟡 | Explicitly select split (e.g. `train` or first available) |
| D-12 | Duplicate rows in source data | 🟡 | Deduplicate by name + location; log duplicate count |
| D-13 | Dataset updated upstream (schema change) | 🟠 | Version cache by hash; invalidate stale cache on schema mismatch |
| D-14 | Non-UTF-8 characters in restaurant names | 🟡 | Decode with `errors="replace"`; preserve original in `raw` field |
| D-15 | Extremely large dataset (memory pressure) | 🟡 | Use chunked loading; filter columns early; consider SQLite for scale |

---

## 2. Preprocessing & Normalization

### 2.1 Missing or invalid field values

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| P-01 | Missing `name` | 🟠 | Drop row; increment dropped-row counter |
| P-02 | Missing `location` | 🟠 | Drop row |
| P-03 | Missing `rating` | 🟠 | Drop row (or impute median with flag — prefer drop for MVP) |
| P-04 | Missing `cuisine` | 🟡 | Set cuisine to `"Unknown"`; still include if other fields valid |
| P-05 | Missing `cost` / unparseable cost string | 🟡 | Set `cost_for_two = None`; assign `budget_tier` from cuisine/location median or `"unknown"` |
| P-06 | Rating as string `"4.5/5"` or `"New"` | 🟠 | Parse numeric portion; treat `"New"` / `"-"` as null → drop or default |
| P-07 | Rating out of range (e.g. 8.0 or -1) | 🟡 | Clamp to 0–5 or drop if clearly invalid |
| P-08 | Rating is 0.0 for all restaurants in an area | 🟡 | Filter still works; UI shows 0 stars |
| P-09 | Empty string vs `null` vs `"N/A"` | 🟡 | Treat all as missing consistently |

### 2.2 Location normalization edge cases

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| P-10 | Same area, different spellings ("Indira Nagar" vs "Indiranagar") | 🟠 | Alias map + fuzzy merge to canonical form |
| P-11 | Location contains city + locality ("Bangalore, Indiranagar") | 🟡 | Extract locality portion or store both `city` and `location` |
| P-12 | Location is only city name ("Bangalore") | 🟠 | Match all restaurants in city; may return very large set before TOP_K cap |
| P-13 | Location with special characters or extra whitespace | 🟡 | Strip, normalize unicode, collapse whitespace |
| P-14 | Location string is numeric or gibberish | 🟡 | Keep as-is; likely no filter matches later |
| P-15 | Case sensitivity ("whitefield" vs "Whitefield") | 🟠 | Case-insensitive normalization |
| P-16 | Multiple locations in one field ("Indiranagar / Koramangala") | 🟡 | Split or match if user query matches any segment |

### 2.3 Cuisine normalization edge cases

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| P-17 | Multi-cuisine string ("Italian, Pizza, Continental") | 🟠 | Keep full string; token match on any segment |
| P-18 | Cuisine with typos in dataset ("Chines" vs "Chinese") | 🟡 | Fuzzy vocabulary; optional cuisine alias map |
| P-19 | Very generic cuisine ("Miscellaneous", "Fast Food") | 🟡 | Allow filter; LLM may produce vague explanations |
| P-20 | Cuisine field is a list vs string in raw data | 🟡 | Coerce to comma-separated string |
| P-21 | Same cuisine, different casing ("north indian" vs "North Indian") | 🟠 | Title-case normalization |

### 2.4 Cost & budget tier edge cases

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| P-22 | Cost as range ("₹300–₹500 for two") | 🟡 | Parse midpoint or lower bound |
| P-23 | Cost in USD or other currency | 🟡 | Log warning; skip or convert if detectable |
| P-24 | Cost is `"₹"` or empty | 🟡 | `cost_for_two = None`; exclude from budget filter or use `"unknown"` tier |
| P-25 | All restaurants have null cost | 🟠 | Budget filter matches nothing; skip budget filter with warning |
| P-26 | Cost distribution skewed (all "medium") | 🟡 | Recompute quantile thresholds; log warning |
| P-27 | User budget "low" but area only has expensive restaurants | 🟠 | Zero candidates after budget filter → empty state with suggestion |
| P-28 | Restaurant cost exactly on tier boundary (₹300) | 🟡 | Document inclusive/exclusive rules; apply consistently |

---

## 3. Repository & Startup

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| R-01 | Cache exists but was built with old code version | 🟡 | Version stamp in cache metadata; rebuild if mismatch |
| R-02 | Concurrent app instances writing same cache file | 🟡 | File lock or write-to-temp-then-rename |
| R-03 | Repository initialized before preprocessing completes | 🔴 | Block serving until ready; show loading state |
| R-04 | `get_locations()` returns 1000+ entries | 🟡 | Streamlit selectbox may be slow; add search/autocomplete |
| R-05 | Single location with only 1 restaurant | 🟢 | Valid; return 1 candidate to LLM |
| R-06 | Repository queried before initialization | 🔴 | Raise clear error or return empty with log |
| R-07 | Memory insufficient to hold full dataset | 🟠 | Fail startup with actionable message |

---

## 4. User Input & Validation

### 4.1 Required fields

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| U-01 | Location not provided (empty string) | 🟠 | Validation error: "Location is required" |
| U-02 | Budget not selected | 🟠 | Validation error: "Budget is required" |
| U-03 | Both location and budget missing | 🟠 | Return all validation errors at once |

### 4.2 Location input edge cases

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| U-04 | Location not in dataset vocabulary | 🟠 | Fuzzy suggest top 3 closest; reject if score below threshold |
| U-05 | User types location manually (API) instead of dropdown | 🟡 | Same fuzzy validation as UI |
| U-06 | Location with leading/trailing spaces | 🟡 | Trim before validation |
| U-07 | Location match ambiguous (two areas score 85%) | 🟡 | Pick highest score; optionally show "Did you mean?" |
| U-08 | User selects valid location with zero restaurants after other filters | 🟠 | Empty result — not a validation error |
| U-09 | Unicode location names | 🟡 | Normalize before match |

### 4.3 Optional fields

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| U-10 | Cuisine = "Any" / null / empty | 🟢 | Skip cuisine filter |
| U-11 | Cuisine not in vocabulary | 🟡 | Fuzzy match or warn; skip filter if no match |
| U-12 | `min_rating` = 0 (default) | 🟢 | No rating filter effectively |
| U-13 | `min_rating` = 5.0 | 🟡 | Very restrictive; may yield zero or few results |
| U-14 | `min_rating` negative or > 5 (API bypass) | 🟡 | Clamp to [0, 5] |
| U-15 | `min_rating` as string `"4.5"` (API) | 🟡 | Coerce to float or return 422 |
| U-16 | `additional_preferences` empty string | 🟢 | Treat as null; skip keyword logic |
| U-17 | `additional_preferences` exceeds 500 chars | 🟡 | Truncate with warning or reject with 422 |
| U-18 | `additional_preferences` only whitespace | 🟢 | Treat as null |
| U-19 | `additional_preferences` in non-English | 🟡 | Pass to Groq as-is; model may still reason |
| U-20 | Conflicting preferences ("cheap" + budget high) | 🟡 | Hard filters use budget enum; LLM resolves free-text tension |

### 4.4 Budget enum edge cases

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| U-21 | Invalid budget value ("premium", "LOW", 1) | 🟠 | Reject with 422; list valid values |
| U-22 | Budget case mismatch ("Medium" vs "medium") | 🟡 | Normalize to lowercase enum |

---

## 5. Filtering Service

### 5.1 Zero and low candidate scenarios

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| F-01 | Zero restaurants match all filters | 🟠 | Return empty list; UI suggests relaxing rating/cuisine/budget |
| F-02 | Exactly 1 candidate | 🟡 | Skip LLM or still call Groq for explanation of single option |
| F-03 | Fewer candidates than `TOP_N` (e.g. 2 candidates, want 5) | 🟠 | Return all available; Groq explains 2; no padding with fake entries |
| F-04 | Exactly `TOP_K` candidates | 🟢 | Normal path |
| F-05 | More candidates than `TOP_K` (e.g. 200 match) | 🟠 | Pre-sort by rating desc; cap at TOP_K; log truncated count |
| F-06 | All candidates have identical rating | 🟡 | LLM or fallback uses cuisine/cost/tags to differentiate |

### 5.2 Individual filter edge cases

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| F-07 | Location substring false positive ("Street" matches many areas) | 🟡 | Prefer whole-word or fuzzy threshold tuning |
| F-08 | Cuisine "Indian" matches "North Indian", "South Indian" | 🟢 | Expected substring behavior |
| F-09 | User cuisine "Pizza" but dataset has "Italian, Pizza" | 🟢 | Token match succeeds |
| F-10 | Budget filter excludes all due to null `budget_tier` | 🟠 | Exclude null-tier from budget filter or bucket separately |
| F-11 | Keyword filter too aggressive (no matches) | 🟡 | Treat keywords as soft signal for LLM, not hard filter (per architecture) |
| F-12 | Keyword filter on empty tags field | 🟢 | No keyword boost; candidates still pass |
| F-13 | User asks for "vegan" — not in dataset tags | 🟡 | No keyword match; LLM may still mention limitation in explanation |
| F-14 | Filter order matters: location first reduces set dramatically | 🟢 | Document order; log counts per stage |

### 5.3 Data quality during filtering

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| F-15 | Duplicate restaurants after filter (same name, different rows) | 🟡 | Deduplicate by name before sending to Groq |
| F-16 | Restaurant name contains comma or JSON-special chars | 🟡 | Proper JSON escaping in prompt |
| F-17 | Restaurant name very long (200+ chars) | 🟡 | Truncate in prompt if needed |
| F-18 | Two restaurants with identical name in same location | 🟠 | Include distinguishing fields (rating, cost) in prompt; use `id` internally |

---

## 6. Prompt Builder

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| PR-01 | Prompt exceeds model context window | 🟠 | Reduce TOP_K; truncate candidate fields; switch to `mixtral-8x7b-32768` |
| PR-02 | Candidate list empty passed to prompt builder | 🔴 | Guard clause; never call Groq with empty list |
| PR-03 | Special characters in restaurant names break JSON | 🟠 | Use `json.dumps` for serialization |
| PR-04 | User `additional_preferences` contains prompt injection | 🔴 | Sanitize; system prompt instructs model to ignore overrides |
| PR-05 | Very long additional_preferences (500 chars) | 🟡 | Included but bounded; monitor token count |
| PR-06 | TOP_N larger than candidate count | 🟡 | Prompt says "rank all N available" not "exactly TOP_N" |
| PR-07 | All candidates look identical to model | 🟡 | Explanations may be generic; acceptable degradation |
| PR-08 | Prompt template variable missing (bug) | 🔴 | Unit test catches; fail before Groq call |

---

## 7. Groq / LLM Engine

### 7.1 API & connectivity failures

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| G-01 | Missing `GROQ_API_KEY` | 🔴 | Fail at startup or first call with clear message |
| G-02 | Invalid / expired API key (401) | 🟠 | User-friendly error; activate fallback ranker |
| G-03 | Groq service outage (503) | 🟠 | Retry once; fallback ranker |
| G-04 | Request timeout (> 30s) | 🟠 | Retry once; fallback ranker |
| G-05 | Rate limit exceeded (429) | 🟠 | Exponential backoff (max 2 retries); fallback or switch to `llama-3.1-8b-instant` |
| G-06 | Network disconnect mid-request | 🟠 | Catch exception; fallback ranker |
| G-07 | Model deprecated or renamed | 🟠 | Fail with config error; document alternate model in README |
| G-08 | Model specified in env does not exist | 🟠 | Clear error at startup |

### 7.2 Response parsing & content edge cases

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| G-09 | Groq returns empty response | 🟠 | Fallback ranker |
| G-10 | Response is valid text but not JSON | 🟠 | Retry with stricter prompt; then fallback |
| G-11 | JSON missing required fields | 🟠 | Partial parse + fallback for missing slots |
| G-12 | JSON wrapped in markdown code fences | 🟡 | Strip ```json ... ``` before parse |
| G-13 | Groq returns fewer than TOP_N recommendations | 🟡 | Merge with fallback for remaining slots or show partial |
| G-14 | Groq returns more than TOP_N recommendations | 🟡 | Take first TOP_N by rank |
| G-15 | Duplicate ranks (two items rank 1) | 🟡 | Re-number sequentially |
| G-16 | Missing or duplicate rank numbers | 🟡 | Sort by rank; fill gaps |
| G-17 | Groq hallucinates restaurant not in candidate list | 🔴 | Reject hallucinated entries; backfill from fallback |
| G-18 | Groq returns correct name with wrong spelling | 🟠 | Fuzzy match name back to candidate list |
| G-19 | Explanation is empty string | 🟡 | Use template explanation from fallback |
| G-20 | Explanation is extremely long (1000+ words) | 🟡 | Truncate in UI with "Read more" optional |
| G-21 | Explanation contains harmful / offensive content | 🟡 | Rare; optional content filter; log for review |
| G-22 | Summary field missing (optional) | 🟢 | Omit summary banner |
| G-23 | Groq returns `"restaurant_name": null` | 🟡 | Skip entry; backfill from fallback |
| G-24 | `response_format json_object` not supported by model | 🟡 | Parse free-text JSON; rely on prompt instructions |
| G-25 | Temperature too high → inconsistent rankings across runs | 🟢 | Document; use 0.2–0.4 for stability |
| G-26 | Same request twice → different rankings | 🟢 | Expected with LLM; acceptable for MVP |

### 7.3 Fallback ranker edge cases

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| G-27 | Fallback triggered during demo | 🟡 | UI badge: "AI unavailable — showing rule-based picks" |
| G-28 | All fallback scores tied | 🟡 | Secondary sort by name alphabetically |
| G-29 | Fallback runs but candidates empty | 🔴 | Return empty response (should not reach this state) |
| G-30 | User cannot distinguish fallback vs Groq results | 🟡 | Optional transparency flag in response metadata |

---

## 8. Orchestrator & Pipeline

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| O-01 | Validation fails mid-pipeline | 🟠 | Short-circuit; return validation errors; no Groq call |
| O-02 | Filter returns empty → Groq still called (bug) | 🔴 | Guard: never call Groq on empty candidates |
| O-03 | Exception in one service crashes entire request | 🟠 | Catch per stage; partial error messages |
| O-04 | Double submit (user clicks twice quickly) | 🟡 | Disable button during loading; debounce |
| O-05 | Request with all optional fields omitted | 🟢 | Valid; wide filter results |
| O-06 | Request with every filter maximally restrictive | 🟠 | Likely empty; graceful empty state |
| O-07 | Merge step: Groq name doesn't match any candidate | 🟠 | Fuzzy match threshold; drop if no match |
| O-08 | Candidate updated between filter and merge (unlikely in sync app) | 🟢 | N/A for in-memory MVP |
| O-09 | Logging exposes API key in error stack trace | 🔴 | Redact secrets in logs |
| O-10 | Pipeline succeeds but all explanations are generic templates | 🟡 | Acceptable fallback path; log Groq failure reason |

---

## 9. Output Formatting & Display

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| OUt-01 | `cost_for_two` is null in candidate | 🟡 | Display "Price not available" |
| OUt-02 | Rating is null (shouldn't happen post-preprocess) | 🟡 | Hide stars or show "N/A" |
| OUt-03 | Cuisine string very long ("Italian, Chinese, ...") | 🟡 | Truncate in card with tooltip for full list |
| OUt-04 | Restaurant name contains HTML/script tags | 🟠 | Escape on render (XSS prevention in web UI) |
| OUt-05 | Explanation contains markdown | 🟡 | Render safely or strip markdown |
| OUt-06 | Unicode / emoji in restaurant name | 🟢 | Render correctly with UTF-8 |
| OUt-07 | Zero recommendations in response object | 🟠 | Empty state UI, not blank page |
| OUt-08 | `total_candidates_considered` is 0 vs null | 🟡 | Show 0 explicitly |
| OUt-09 | Estimated cost formatting for null | 🟡 | Consistent fallback string |

---

## 10. Streamlit UI

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| UI-01 | App rerun during Groq call | 🟡 | Spinner resets; use session state to preserve in-flight request or cancel |
| UI-02 | User changes form without resubmitting | 🟢 | Show stale results with optional "Results may be outdated" |
| UI-03 | Location dropdown with 500+ items | 🟡 | Use searchable select (`st.selectbox` limit) or text input + autocomplete |
| UI-04 | Browser back button after submit | 🟢 | Streamlit rerun behavior; results may clear |
| UI-05 | Mobile narrow viewport | 🟡 | Cards stack vertically; text wraps |
| UI-06 | Very long explanation overflows card | 🟡 | CSS scroll or truncate |
| UI-07 | Streamlit cache stale after dataset update | 🟡 | `@st.cache_resource` clear button or version key in cache |
| UI-08 | Multiple users on same Streamlit instance | 🟡 | Shared in-memory state; session isolated but dataset shared (OK for MVP) |
| UI-09 | User submits with default slider values only | 🟢 | Valid minimal query |
| UI-10 | Page refresh during loading | 🟡 | Request may complete server-side; UI shows initial state |
| UI-11 | Dark mode / light mode | 🟢 | Streamlit default; optional theme |
| UI-12 | Accessibility: screen reader on form | 🟢 | Use labels on all inputs |

---

## 11. REST API (Optional)

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| A-01 | Malformed JSON body | 🟠 | 400 Bad Request |
| A-02 | Wrong Content-Type | 🟡 | 415 or attempt parse |
| A-03 | Extra unknown fields in request | 🟢 | Ignore (Pydantic `extra="ignore"`) |
| A-04 | `top_n` = 0 or negative | 🟡 | Validate; default to 5 or return 422 |
| A-05 | `top_n` = 100 (excessive) | 🟡 | Cap at max (e.g. 10) |
| A-06 | Request before dataset loaded | 🟠 | 503 Service Unavailable |
| A-07 | Concurrent API requests | 🟡 | Thread-safe repository reads |
| A-08 | Very large request body | 🟡 | Limit body size at reverse proxy |
| A-09 | CORS issues from frontend | 🟡 | Configure CORS on FastAPI |
| A-10 | Idempotency: same POST twice | 🟢 | Two independent responses (may differ slightly) |

---

## 12. Security & Abuse

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| S-01 | Prompt injection in additional_preferences | 🔴 | Sanitize; system prompt hardening; never execute user text |
| S-02 | `.env` committed to git | 🔴 | `.gitignore`; pre-commit hook optional |
| S-03 | API key logged in debug mode | 🔴 | Redact in all log formatters |
| S-04 | User enumerates all restaurants via metadata endpoint | 🟡 | Acceptable for MVP; rate limit in production |
| S-05 | Automated scraping / DDoS on recommendation endpoint | 🟡 | Rate limiting per IP |
| S-06 | XSS via restaurant name in HTML frontend | 🟠 | Escape all user-facing and dataset-sourced strings |
| S-07 | SQL injection (if SQLite added later) | 🟠 | Parameterized queries only |
| S-08 | User sends binary data in text fields | 🟡 | Reject non-text or strip non-printable chars |
| S-09 | Groq prompt includes full dataset (bug) | 🔴 | Assert candidate count ≤ TOP_K before every call |

---

## 13. Concurrency & Performance

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| PF-01 | First startup slow (download + preprocess) | 🟡 | Loading screen; cache on disk |
| PF-02 | Filter on 10K+ rows slow | 🟡 | Vectorize with pandas; target < 50 ms |
| PF-03 | Multiple simultaneous Groq calls | 🟡 | May hit rate limits; queue or serialize |
| PF-04 | Groq latency spike (5s+) | 🟡 | Timeout + fallback; spinner in UI |
| PF-05 | Memory leak on repeated Streamlit reruns | 🟡 | Use `@st.cache_resource` correctly |
| PF-06 | Parquet cache read fails mid-startup | 🟠 | Fall back to full re-download |
| PF-07 | TOP_K too high → token limit error | 🟠 | Catch Groq error; reduce TOP_K and retry |

---

## 14. Configuration & Environment

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| C-01 | `.env` file missing | 🟠 | Fail on Groq call; optional warn at startup |
| C-02 | Invalid integer for `TOP_K_CANDIDATES` | 🟡 | Pydantic validation error at startup |
| C-03 | `TOP_K` > `TOP_N` but TOP_K < 1 | 🟡 | Reject config at startup |
| C-04 | Wrong working directory when running app | 🟡 | Use paths relative to project root or absolute from config |
| C-05 | Windows vs Linux path separators for cache | 🟡 | Use `pathlib.Path` |
| C-06 | Environment variable override in production | 🟢 | pydantic-settings precedence documented |

---

## 15. Cross-Cutting Scenarios

### 15.1 End-to-end user journeys

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| X-01 | **Happy path:** Indiranagar + medium + Italian + 4.0 rating | 🟢 | 5 cards with explanations |
| X-02 | **Impossible combo:** Whitefield + low budget + 5.0 rating + niche cuisine | 🟠 | Empty state with helpful suggestions |
| X-03 | **Groq down during demo** | 🟠 | Fallback rankings still show useful results |
| X-04 | **First-time user, no idea what locations exist** | 🟡 | Dropdown shows all options; README lists examples |
| X-05 | **User trusts AI explanation blindly** | 🟢 | Optional disclaimer: "Recommendations based on dataset + AI" |
| X-06 | **Stale dataset** (restaurant closed in real life) | 🟡 | Inherent limitation; document data freshness |
| X-07 | **Bias in data** (certain areas overrepresented) | 🟡 | LLM may favor popular areas; document limitation |

### 15.2 Testing & development edge cases

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| X-08 | Tests run without `GROQ_API_KEY` | 🟢 | Mock Groq; no live calls in CI |
| X-09 | Tests run without network | 🟢 | Use fixture data / cached Parquet |
| X-10 | Developer deletes cache manually | 🟢 | Re-download on next run |
| X-11 | pytest collects integration test that hits live Groq | 🟡 | Mark `@pytest.mark.integration`; skip in CI |

### 15.3 Data ↔ LLM consistency

| ID | Scenario | Severity | Expected behavior |
|----|----------|----------|-------------------|
| X-12 | LLM says "great for families" but no family tag in data | 🟡 | Soft inference; acceptable if reasonable |
| X-13 | LLM cites wrong rating in explanation | 🟠 | Display rating from dataset, not from LLM text |
| X-14 | LLM recommends based on budget user didn't select | 🟡 | Prompt should anchor to stated prefs |
| X-15 | Filter passes restaurant LLM excludes entirely | 🟡 | OK if fewer than TOP_N returned; don't invent replacements |

---

## Priority Matrix for Implementation

Handle these **before demo / MVP ship**:

| Priority | IDs | Category |
|----------|-----|----------|
| P0 Must fix | G-17, G-01, G-02, O-02, PR-02, PR-04, S-01, S-09, D-10 | Hallucination guards, empty pipeline, secrets, prompt injection |
| P1 Should fix | F-01, F-03, F-05, G-05, G-09–G-11, G-27, U-04, P-01–P-03, O-07 | Empty states, Groq failures, fallback UX, validation |
| P2 Nice to fix | F-15, G-12, G-18, UI-03, P-10, D-12 | Dedup, JSON fences, fuzzy name match, large dropdowns |
| P3 Later | X-06, A-05, UI-11, PF-03 | Stale data disclaimer, API caps, scale |

---

## Test Case Mapping

Suggested pytest cases derived from this document:

```
tests/test_edge_cases_data.py      → P-01, P-06, P-22, D-12
tests/test_edge_cases_filter.py    → F-01, F-03, F-05, F-10, F-15
tests/test_edge_cases_groq.py      → G-09, G-11, G-12, G-17, G-18
tests/test_edge_cases_validation.py → U-01, U-04, U-14, U-17, U-21
tests/test_edge_cases_orchestrator.py → O-02, O-07, F-01 + mocked Groq
```

---

## Related Documents

| Document | Purpose |
|----------|---------|
| [architecture.md](architecture.md) | Error handling §13, security §14, Groq §8 |
| [implementation-plan.md](implementation-plan.md) | Phase 6 hardening tasks |
| [context.md](context.md) | Core requirements |

---

## Document Maintenance

When adding new features, update this file with:

1. New edge case ID in the appropriate section  
2. Severity rating  
3. Expected behavior  
4. Entry in Priority Matrix if P0/P1  

**Last reviewed:** aligned with architecture v1 (Groq provider, Streamlit MVP).
