import os
import sys
import time
import requests
from pymongo import MongoClient, ASCENDING

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "pictograms")
LANGUAGE = os.getenv("ARASAAC_LANGUAGE", "de")
ARASAAC_BASE = "https://api.arasaac.org/v1"
COLLECTION = "pictograms"


def fetch_all_pictograms(language: str) -> list[dict]:
    """Fetch every pictogram record from the ARASAAC API for the given language."""
    url = f"{ARASAAC_BASE}/pictograms/all/{language}"
    print(f"Fetching pictograms from {url} ...")
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    data = response.json()
    print(f"Received {len(data)} pictograms from ARASAAC API.")
    return data


def build_search_terms(pictogram: dict) -> list[str]:
    """
    Extract all searchable text from a pictogram and return as lowercased list.
    Includes keyword texts, plurals, tags, and categories.
    """
    terms: set[str] = set()

    for kw in pictogram.get("keywords", []):
        keyword = kw.get("keyword", "")
        if keyword:
            terms.add(keyword.strip().lower())
        plural = kw.get("plural", "")
        if plural:
            terms.add(plural.strip().lower())

    for tag in pictogram.get("tags", []):
        if tag:
            terms.add(tag.strip().lower())

    for cat in pictogram.get("categories", []):
        if cat:
            terms.add(cat.strip().lower())

    return sorted(terms)


def load_into_mongodb(pictograms: list[dict]):
    """Insert pictograms into MongoDB, enriching each with searchTerms."""
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[COLLECTION]

    existing = collection.count_documents({})
    if existing > 0:
        print(f"Collection already contains {existing} documents. Skipping load.")
        print("Drop the collection manually if you want to reload.")
        client.close()
        return

    docs = []
    for p in pictograms:
        p["searchTerms"] = build_search_terms(p)
        docs.append(p)

    print(f"Inserting {len(docs)} pictograms into MongoDB ...")
    batch_size = 1000
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        collection.insert_many(batch)
        print(f"  Inserted {min(i + batch_size, len(docs))} / {len(docs)}")

    # Create indexes for efficient lookup
    collection.create_index([("_id", ASCENDING)])
    collection.create_index([("searchTerms", ASCENDING)])
    collection.create_index([("keywords.keyword", ASCENDING)])
    print("Indexes created.")

    client.close()
    print("Data loading complete.")


def main():
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            pictograms = fetch_all_pictograms(LANGUAGE)
            load_into_mongodb(pictograms)
            return
        except requests.RequestException as e:
            print(f"Attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                wait = attempt * 10
                print(f"Retrying in {wait}s ...")
                time.sleep(wait)
            else:
                print("All retries exhausted. Exiting.")
                sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
