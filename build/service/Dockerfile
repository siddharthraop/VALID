FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY guardrails/g1_g2.py .
COPY guardrails/g4_generate.py .
COPY guardrails/g5_citation.py .
COPY guardrails/main.py .

ENV PORT=8080
EXPOSE 8080

CMD exec python3 -m uvicorn main:app --host 0.0.0.0 --port ${PORT}
