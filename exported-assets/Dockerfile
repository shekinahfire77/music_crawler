# Dockerfile for Render deployment (optional)
# Use Python 3.9 slim image for efficiency
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create output directory
RUN mkdir -p /tmp/output

# Run as non-root user for security
RUN useradd --create-home --shell /bin/bash crawler
RUN chown -R crawler:crawler /app /tmp/output
USER crawler

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import redis, psycopg2; print('Health check passed')" || exit 1

# Default command
CMD ["python", "app.py"]