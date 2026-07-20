import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

MODEL_NAME = os.getenv("MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "7860"))


class RerankRequest(BaseModel):
    query: str
    documents: list[str]


class RerankResponse(BaseModel):
    scores: list[float]


model: CrossEncoder | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    logger.info("Loading cross-encoder model: %s", MODEL_NAME)
    model = CrossEncoder(MODEL_NAME)
    logger.info("Model loaded")
    yield
    model = None


app = FastAPI(
    title="Mnemos Reranker",
    description="Cross-encoder reranker for Mnemos evidence reranking",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME, "loaded": model is not None}


@app.post("/", response_model=RerankResponse)
async def rerank(request: RerankRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    pairs = [(request.query, doc) for doc in request.documents]
    scores = model.predict(pairs, show_progress_bar=False)
    scores_list = scores.tolist() if hasattr(scores, "tolist") else list(scores)
    return RerankResponse(scores=scores_list)


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
