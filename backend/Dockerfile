FROM python:3.12-slim

WORKDIR /app

# System deps for compiling some Python wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download spaCy models (large, but cached in image)
RUN python -m spacy download de_core_news_lg && \
    python -m spacy download en_core_web_lg

# Pre-download NLTK data (WordNet for synset matching)
RUN python -c "import nltk; nltk.download('wordnet', quiet=True); nltk.download('omw-1.4', quiet=True)"

COPY . .

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
