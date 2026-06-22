# Project Context: AI-Powered Restaurant Recommendation System

> Source: [DOCS/problemstatement.txt](DOCS/problemstatement.txt)

## Overview

Build an **AI-powered restaurant recommendation service** inspired by **Zomato**. The system intelligently suggests restaurants based on user preferences by combining **structured data** with a **Large Language Model (LLM)**.

---

## Objective

Design and implement an application that:

1. Takes user preferences (location, budget, cuisine, ratings, etc.)
2. Uses a real-world dataset of restaurants
3. Leverages an LLM to generate personalized, human-like recommendations
4. Displays clear and useful results to the user

---

## Dataset

| Property | Value |
|----------|-------|
| **Source** | Hugging Face |
| **URL** | https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation |
| **Key fields** | Restaurant name, location, cuisine, cost, rating, and related metadata |

---

## System Workflow

### 1. Data Ingestion

- Load and preprocess the Zomato dataset from Hugging Face
- Extract relevant fields: restaurant name, location, cuisine, cost, rating, etc.

### 2. User Input

Collect user preferences:

| Preference | Examples / Options |
|------------|-------------------|
| **Location** | Indiranagar, Whitefield, Church Street, etc. |
| **Budget** | Low, medium, high |
| **Cuisine** | Italian, Chinese, etc. |
| **Minimum rating** | Numeric threshold |
| **Additional preferences** | Family-friendly, quick service, etc. |

### 3. Integration Layer

- Filter and prepare relevant restaurant data based on user input
- Pass structured results into an LLM prompt
- Design a prompt that helps the LLM reason and rank options

### 4. Recommendation Engine

Use the LLM to:

- **Rank** restaurants
- **Explain** why each recommendation fits the user's preferences
- **Optionally summarize** the overall set of choices

### 5. Output Display

Present top recommendations in a user-friendly format:

| Field | Description |
|-------|-------------|
| Restaurant Name | Name of the recommended restaurant |
| Cuisine | Type of cuisine offered |
| Rating | Restaurant rating |
| Estimated Cost | Approximate cost for the user |
| AI-generated explanation | Why this restaurant was recommended |

---

## Architecture Summary

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│   Dataset   │────▶│ Data Ingest  │────▶│ Integration     │────▶│ Recommendation│
│ (HuggingFace)│     │ & Preprocess │     │ Layer (Filter + │     │ Engine (LLM) │
└─────────────┘     └──────────────┘     │  Prompt Design) │     └──────┬───────┘
                                         └────────▲────────┘            │
                                                  │                     ▼
                                         ┌────────┴────────┐     ┌──────────────┐
                                         │   User Input   │     │ Output Display│
                                         │  (Preferences) │     │ (Top Picks)   │
                                         └────────────────┘     └──────────────┘
```

---

## Core Requirements Checklist

- [ ] Load Zomato dataset from Hugging Face
- [ ] Preprocess and extract restaurant fields
- [ ] Accept user preferences (location, budget, cuisine, rating, extras)
- [ ] Filter dataset based on user input
- [ ] Build LLM prompt with structured restaurant data
- [ ] LLM ranks restaurants and generates explanations
- [ ] Display results: name, cuisine, rating, cost, AI explanation

---

## Key Design Considerations

- **Hybrid approach**: Structured filtering narrows candidates; LLM adds ranking and natural-language reasoning
- **Prompt engineering**: The integration layer must format filtered data clearly so the LLM can compare and justify choices
- **User experience**: Output should be readable and actionable, not raw JSON or model dumps
