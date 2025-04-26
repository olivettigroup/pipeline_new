import os
import time
import requests
import argparse
from typing import List
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from tqdm import tqdm
import dimcli

# ---------------------------
# Helper: Crossref metadata fetcher
# ---------------------------

def get_crossref_metadata(doi):
    url = f"https://api.crossref.org/works/{doi}"
    response = requests.get(url)
    
    if response.status_code != 200:
        return None

    metadata = response.json()['message']

    def sanitize_doi(doi):
        return ''.join(c for c in doi if c.isalnum())
    
    def get_first(lst):
        return lst[0] if lst and len(lst) > 0 else None

    def get_date_year(date_parts):
        try:
            return date_parts[0][0]
        except Exception:
            return None

    doi = metadata.get("DOI", None)
    safe_doi = sanitize_doi(doi)

    title = get_first(metadata.get("title"))
    journal = get_first(metadata.get("container-title"))
    issn = get_first(metadata.get("ISSN"))

    return {
        'doi': doi,
        'safe_doi': safe_doi,
        'title': title,
        'prefix': metadata.get("prefix", None),
        'issue': metadata.get("issue", None),
        'journal': journal,
        'volume': metadata.get("volume", None),
        'publisher': metadata.get("publisher", None),
        'issn': issn,
        'page': metadata.get("page", None),
        'year': get_date_year(metadata.get("published", {}).get("date-parts", [[None]])),
        'num_references': metadata.get("reference-count", 0),
        'times_cited': metadata.get("is-referenced-by-count", 0),
        'References': metadata.get("reference-count", 0),
        'have_pdf': False,
        'have_any': False,
        'have_html': False,
        'pdf_path': f'/data/scratch/{safe_doi}.pdf',
        'html_path': f'/data/scratch/{safe_doi}.html',
        'download_succeeded': False,
        'download_attempted': False,
        'parsed': False,
        'priority': 1
    }

# ---------------------------
# Extractors
# ---------------------------

class DimensionsExtractor:
    def __init__(self):
        try:
            BASE_URL = "https://app.dimensions.ai"
            api_key = "YOUR_API_KEY_HERE"
            dimcli.login(key=api_key, endpoint=BASE_URL)
            self.dsl = dimcli.Dsl()
            self.active = True
        except Exception as e:
            print(f"Dimensions login failed: {e}")
            self.active = False

    def extract(self, keyword, size=1000):
        if not self.active:
            return []

        all_records = []
        for skip_val in range(0, size, 1000):
            query = f"""search publications where year >= 2019 for "{keyword}" return publications[doi] limit 1000 skip {skip_val}"""
            response = self.dsl.query(query)
            all_records.extend([rec.get("doi") for rec in response.get("publications", []) if rec.get("doi")])

            if len(all_records) >= size:
                break

        return all_records[:size]

class LensExtractor:
    def __init__(self):
        self.token = "token"
        self.url = "https://api.lens.org/scholarly/search"

    def extract(self, keyword, size=100):
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        }

        all_records = []
        request_body = {
            "query": keyword,
            "size": min(size, 1000),  # Lens limits max size per request
            "scroll": "1m"
        }

        response = requests.post(self.url, json=request_body, headers=headers)

        if response.status_code != 200:
            print(f"Lens API Error: {response.status_code}")
            return []

        json_response = response.json()
        all_records.extend(json_response.get('data', []))
        scroll_id = json_response.get('scroll_id')

        while scroll_id and len(all_records) < size:
            scroll_request_body = {"scroll_id": scroll_id}
            response = requests.post(self.url, json=scroll_request_body, headers=headers)

            if response.status_code == 429:
                retry_after = int(response.headers.get('x-rate-limit-retry-after-seconds', 8))
                print(f"Rate limited. Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            elif response.status_code != 200:
                print(f"Scroll error: {response.status_code}")
                break

            json_response = response.json()
            all_records.extend(json_response.get('data', []))
            scroll_id = json_response.get('scroll_id')
            time.sleep(1)

        all_dois = [rec["doi"] for rec in all_records if "doi" in rec]
        return all_dois[:size]

class CrossrefExtractor:
    def __init__(self, uri="mongodb://localhost:27017", db_name="crossref", coll_name="records"):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.collection = self.db[coll_name]

    def extract(self, keyword, size=1000):
        query = {
            "title": {"$exists": True},
            "title": {"$elemMatch": {"$regex": keyword, "$options": "i"}}
        }

        cursor = self.collection.find(query, no_cursor_timeout=True).limit(size)

        doi_list = []
        for doc in cursor:
            if "DOI" in doc:
                doi_list.append(doc["DOI"])

        return doi_list

    def close(self):
        self.client.close()

# ---------------------------
# Aggregator
# ---------------------------

class DoiAggregator:
    def __init__(self):
        self.lens_extractor = LensExtractor()
        self.crossref_extractor = CrossrefExtractor()
        self.dim_extractor = DimensionsExtractor()

        self.client = MongoClient('mongodb://localhost:27017')
        self.metadata_coll = self.client['metadata']['records']
        self.scratch_coll = self.client['scratch']['records']

    def aggregate_dois(self, keywords: List[str], size_per_source=500) -> List[str]:
        dims_dois = []
        lens_dois = []
        crossref_dois = []

        for kw in keywords:
            if self.dim_extractor.active:
                dims_dois.extend(self.dim_extractor.extract(kw, size=size_per_source))
            lens_dois.extend(self.lens_extractor.extract(kw, size=size_per_source))
            crossref_dois.extend(self.crossref_extractor.extract(kw, size=size_per_source))

        all_dois = set(dims_dois).union(set(lens_dois)).union(set(crossref_dois))

        final_dois = []
        duplicate_count = 0

        for doi in tqdm(all_dois, desc="Checking and inserting DOIs"):
            exists = self.metadata_coll.find_one({'doi': doi, 'download': True})
            if exists:
                continue

            crossref_meta = get_crossref_metadata(doi)
            if crossref_meta:
                try:
                    self.scratch_coll.insert_one(crossref_meta)
                    final_dois.append(doi)
                except DuplicateKeyError:
                    duplicate_count += 1
                except Exception as e:
                    print(f"Error inserting DOI {doi}: {e}")

        print(f"Completed aggregation. {duplicate_count} duplicate DOIs were skipped.")
        
        return final_dois

# ---------------------------
# Main Entry Point
# ---------------------------

def main():
    parser = argparse.ArgumentParser(description="DOI Aggregator from multiple sources")
    parser.add_argument('--keywords', nargs='+', required=True, help="List of keywords to search for")
    parser.add_argument('--size', type=int, default=300, help="Number of DOIs to fetch per source per keyword")

    args = parser.parse_args()

    aggregator = DoiAggregator()
    aggregator.aggregate_dois(
        keywords=args.keywords,
        size_per_source=args.size
    )

if __name__ == "__main__":
    main()
