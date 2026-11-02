FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY tadabbur ./tadabbur
RUN pip install --no-cache-dir .
COPY config ./config
COPY web ./web
COPY scripts ./scripts
# Build the corpus at image build time (sources are fetched, not committed).
RUN bash scripts/fetch_sources.sh && python -m tadabbur.build_data && rm -rf data-src
ENV TADABBUR_DATA_DIR=/app/data TADABBUR_CACHE_DIR=/app/.cache/llm
EXPOSE 8000
CMD ["uvicorn", "tadabbur.api:app", "--host", "0.0.0.0", "--port", "8000"]
