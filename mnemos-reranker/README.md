---
title: Mnemos Reranker
emoji: 🧠
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
---

# Mnemos Reranker

Cross-encoder reranker for the Mnemos evidence reranking pipeline.

Uses `cross-encoder/ms-marco-MiniLM-L-6-v2` by default (configurable via `MODEL_NAME` env var).

## API

### `POST /`
**Request:**
```json
{
  "query": "What is the failure rate?",
  "documents": ["Doc 1 text...", "Doc 2 text..."]
}
```
**Response:**
```json
{
  "scores": [0.98, 0.12]
}
```

### `GET /health`
Returns model status.

## Configure in Mnemos `.env`
```
CROSS_ENCODER_URL=https://pingpong9999-mnemos-reranker.hf.space
ENABLE_RERANKING=true
```
