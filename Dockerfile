FROM python:3.11-slim

WORKDIR /app

# System dependencies — Tesseract OCR is required for PDF/image extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" && \
    pip install --no-cache-dir streamlit

# Copy source
COPY src/ ./src/
COPY web/ ./web/
COPY examples/ ./examples/

# Run as non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "web/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
