# Dockerfile
FROM python:3.12-slim
 
# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    DEBIAN_FRONTEND=noninteractive
 
WORKDIR /app
 
# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        gcc \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
&& rm -rf /var/lib/apt/lists/*
 
# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
 
# Copy requirements first (cache optimization)
COPY --chown=appuser:appuser requirements.txt .
 
# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt
 
# Copy app code
COPY --chown=appuser:appuser . .
 
# Create data dir
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data
 
# Expose port
EXPOSE 8501
 
# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1
 
# Switch to non-root user
USER appuser
 
# Run Streamlit
CMD ["streamlit", "run", "research_assistant.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--browser.gatherUsageStats=false"]