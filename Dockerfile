# Stage 1: Build Stage for Python Application
FROM python:3.12-slim AS builder

# Set the working directory
WORKDIR /app

# Install build dependencies and upgrade pip in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && pip install --upgrade pip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the necessary files for installation
COPY requirements.txt setup.py pyproject.toml ./
COPY src/ ./src/
COPY readme.md .
COPY start_muscpy.py .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir .

# Stage 2: Runtime Stage with FFmpeg
FROM python:3.12-slim

# Install FFmpeg in a single layer and clean up
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy only the necessary files from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app/start_muscpy.py .
COPY --from=builder /app/src ./src
COPY --from=builder /app/readme.md .

# Command to run the script
CMD ["python3", "start_muscpy.py"]

