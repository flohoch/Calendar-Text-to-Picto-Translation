"""
Loads ARASAAC pictograms into MongoDB, one collection per language.
Collections: pictograms_de, pictograms_en

Each collection has its own copy of every pictogram with language-specific
keywords. The backend selects the right collection based on the request
language.
"""
import os
import sys
import time

import requests
from pymongo import ASCENDING, MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "pictograms")
LANGUAGES = [lang.strip() for lang in os.getenv("ARASAAC_LANGUAGES", "de,en").split(",")]
ARASAAC_BASE = "https://api.arasaac.org/v1"


def fetch_all(language: str) -> list[dict]:
    url = f"{ARASAAC_BASE}/pictograms/all/{language}"
    print(f"[{language}] Fetching {url} ...")
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    data = r.json()
    print(f"[{language}] Received {len(data)} pictograms.")
    return data


def build_search_terms(p: dict) -> list[str]:
    terms: set[str] = set()
    for kw in p.get("keywords", []):
        if kw.get("keyword"):
            terms.add(kw["keyword"].strip().lower())
        if kw.get("plural"):
            terms.add(kw["plural"].strip().lower())
    for tag in p.get("tags", []):
        if tag:
            terms.add(tag.strip().lower())
    for cat in p.get("categories", []):
        if cat:
            terms.add(cat.strip().lower())
    return sorted(terms)


def load_language(language: str, db) -> None:
    coll_name = f"pictograms_{language}"
    coll = db[coll_name]

    if coll.count_documents({}) > 0:
        print(f"[{language}] Collection '{coll_name}' already populated. Skipping.")
        return

    pictograms = fetch_all(language)
    docs = []
    for p in pictograms:
        p["searchTerms"] = build_search_terms(p)
        docs.append(p)

    print(f"[{language}] Inserting {len(docs)} pictograms into {coll_name} ...")
    batch = 1000
    for i in range(0, len(docs), batch):
        coll.insert_many(docs[i : i + batch])
        print(f"  [{language}] {min(i + batch, len(docs))}/{len(docs)}")

    coll.create_index([("_id", ASCENDING)])
    coll.create_index([("searchTerms", ASCENDING)])
    coll.create_index([("keywords.keyword", ASCENDING)])
    print(f"[{language}] Indexes created.")


def main():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]

    for language in LANGUAGES:
        retries = 5
        for attempt in range(1, retries + 1):
            try:
                load_language(language, db)
                break
            except requests.RequestException as e:
                print(f"[{language}] Attempt {attempt}/{retries} failed: {e}")
                if attempt < retries:
                    wait = attempt * 10
                    print(f"  Retrying in {wait}s ...")
                    time.sleep(wait)
                else:
                    print(f"[{language}] Giving up.")
                    sys.exit(1)
            except Exception as e:
                print(f"[{language}] Unexpected error: {e}")
                sys.exit(1)

    client.close()
    print("Data loading complete for all languages.")


if __name__ == "__main__":
    main()
