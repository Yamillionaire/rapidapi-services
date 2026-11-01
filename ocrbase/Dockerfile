# OCRBase - print-first OCR service (Tesseract 5, Docker runtime).
#
# Build context assumption: the REPO ROOT (~/workspace/rapidapi-competitors/),
# NOT this ocrbase/ directory, so that shared/ is available alongside the
# service. Build with:
#   docker build -f ocrbase/Dockerfile -t ocrbase .
# OCRBase itself is stdlib-only and does not import shared/ at runtime;
# shared/ is copied for fleet parity / future scaffold use.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-spa \
        tesseract-ocr-fra \
        tesseract-ocr-deu \
        tesseract-ocr-por \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY shared/ ./shared/
COPY ocrbase/ ./ocrbase/

ENV PORT=8118 \
    OMP_THREAD_LIMIT=1

EXPOSE 8118

CMD ["python", "ocrbase/app.py"]
