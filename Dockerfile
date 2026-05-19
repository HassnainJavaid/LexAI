# Production-ready Dockerfile for LexAI Backend & Frontend
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV JWT_SECRET="production-secure-random-jwt-secret-key-32-chars"
ENV GROQ_MODEL="llama-3.3-70b-versatile"

WORKDIR /app

# Install system dependencies needed for ReportLab / SQLite / ChromaDB
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p uploaded_docs chroma_db server_logs && chmod 777 uploaded_docs chroma_db server_logs

EXPOSE 8000

# Run uvicorn server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
