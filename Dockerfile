# ============================
# Stage 1: Build GEHistoricalImagery (self-contained linux-x64)
# ============================
FROM mcr.microsoft.com/dotnet/sdk:8.0-jammy AS gehi-build

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
 && rm -rf /var/lib/apt/lists/*

# Clone and publish a single-file, self-contained binary
RUN git clone https://github.com/Mbucari/GEHistoricalImagery.git /src
RUN dotnet publish /src/src/GEHistoricalImagery/GEHistoricalImagery.csproj \
      -c Release -r linux-x64 --self-contained true \
      -p:PublishSingleFile=true \
      -o /out

# ============================
# Stage 2: Python API runtime
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

# Install GEHistoricalImagery from build stage
COPY --from=gehi-build /out/GEHistoricalImagery /usr/local/bin/GEHistoricalImagery
RUN chmod +x /usr/local/bin/GEHistoricalImagery \
 && /usr/local/bin/GEHistoricalImagery --version || true

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
