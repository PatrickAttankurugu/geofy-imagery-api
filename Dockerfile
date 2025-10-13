# ============================
# Python API runtime
# ============================
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# System deps (GDAL + build tools for wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    wget \
    unzip \
    curl \
    libgdal-dev \
    gdal-bin \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Download pre-built GEHistoricalImagery binary from v0.2.0.1 release
# This is a working Linux x64 binary that doesn't require building from source
RUN wget https://github.com/Mbucari/GEHistoricalImagery/releases/download/v0.2.0.1/GEHistoricalImagery-linux-x64.tar.gz \
 && tar -xzf GEHistoricalImagery-linux-x64.tar.gz -C /usr/local/bin \
 && chmod +x /usr/local/bin/GEHistoricalImagery \
 && rm GEHistoricalImagery-linux-x64.tar.gz \
 && /usr/local/bin/GEHistoricalImagery --version || echo "GEHistoricalImagery installed"

# Copy requirements first (better layer caching)
COPY requirements.txt .

# Install Python deps
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create runtime directories
RUN mkdir -p storage/temp storage/logs storage/cache

# Expose API port
EXPOSE 8006

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8006/api/health || exit 1

# Run the application
CMD ["python", "run.py"]