# Use Railway's Python base image
FROM python:3.11-slim

# Install ffmpeg and dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install Python dependencies + always update yt-dlp
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade yt-dlp

# Run bot
CMD ["python", "main.py"]
