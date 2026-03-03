# Chen's Engineer Toolbox - Full Stack (Frontend + Backend)
# For deployment to ai-builders.space
# Serves Streamlit UI on PORT, FastAPI backend on 8000 (internal)

FROM python:3.11-slim

WORKDIR /app

# Install Tesseract OCR for inspection report parser (image-based PDFs)
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies (pywin32 is Windows-only, skipped on Linux)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY .streamlit/ ./.streamlit/

# Streamlit talks to backend via localhost (backend on 8001 to avoid PORT conflict)
ENV BACKEND_URL=http://127.0.0.1:8001

# Expose port (PORT set at runtime by Koyeb)
EXPOSE 8000

# Run backend on 8001 (internal) + Streamlit on PORT (exposed to internet)
# Platform routes external traffic to PORT - visitors see Streamlit UI
# Fix WebSocket loading behind reverse proxy (enableWebsocketCompression=false)
ENV STREAMLIT_SERVER_ENABLEWEBSOCKETCOMPRESSION=false
ENV STREAMLIT_SERVER_ENABLECORS=false
CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port 8001 & streamlit run frontend/Home.py --server.port ${PORT:-8000} --server.address 0.0.0.0 --server.headless true --server.enableWebsocketCompression false --server.enableCORS false"
