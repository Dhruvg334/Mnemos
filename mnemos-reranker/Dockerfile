FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2
ENV HOST=0.0.0.0
ENV PORT=7860

EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
