import os
import time
import requests
from typing import List
from datetime import datetime
import time
from tqdm import tqdm
from pymongo import MongoClient

# Elsevier Downloader Class

class ElsevierDownloader:
    def __init__(self, output_folder, api_key):
        self.output_folder = output_folder
        self.api_key = api_key

        # Create output folder if it doesn't exist
        os.makedirs(self.output_folder, exist_ok=True)

    @staticmethod
    def sanitize_doi(doi):
        return ''.join(c for c in doi if c.isalnum())

    def download_paper(self, doi):
        try:
            api_key = self.api_key 
            url = f"https://api.elsevier.com/content/article/doi/{doi}?&apiKey={api_key}"
            response = requests.get(url, timeout=100, stream=True)
            response.raise_for_status()

            file_path = os.path.join(self.output_folder, f"{self.sanitize_doi(doi)}.html")
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(response.text)
        except Exception as e:
            print(f"Error downloading DOI {doi}: {e}")
        time.sleep(1.0)  # Avoid overwhelming the API

# Springer Downloader Class

class SpringerDownloader:
    def __init__(self, output_folder):
        self.output_folder = output_folder

        # Create output folder if it doesn't exist
        os.makedirs(self.output_folder, exist_ok=True)

    @staticmethod
    def sanitize_doi(doi):
        return ''.join(c for c in doi if c.isalnum())

    def download_paper(self, doi):
        try:
            url = f"http://link.springer.com/{doi}.html"
            headers = {
                "Accept": "text/html",
                "User-agent": "Mozilla/5.0"
            }
            response = requests.get(url, headers=headers, timeout=100, stream=True)
            response.raise_for_status()

            # Save the file
            file_path = os.path.join(self.output_folder, f"{self.sanitize_doi(doi)}.html")
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(response.text)

        except Exception as e:
            print(f"Error downloading DOI {doi}: {e}")
        finally:
            time.sleep(1.0)  # Avoid overwhelming the server

# Wiley Downloader Class

class WileyDownloader:
    def __init__(self, output_folder, client_token):
        self.output_folder = output_folder
        self.client_token = client_token

        # Create output folder if it doesn't exist
        os.makedirs(self.output_folder, exist_ok=True)

    @staticmethod
    def sanitize_doi(doi):
        return ''.join(c for c in doi if c.isalnum())

    def download_paper(self, doi):
        try:
            sanitized_doi = doi.replace("/", "%2F")
            url = f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{sanitized_doi}"
            headers = {"Wiley-TDM-Client-Token": self.client_token}
            extension = ".pdf"

            response = requests.get(url, headers=headers, timeout=100, stream=True)
            response.raise_for_status()

            # Save the file
            file_path = os.path.join(self.output_folder, f"{self.sanitize_doi(doi)}{extension}")
            with open(file_path, "wb") as file:
                file.write(response.content)

        except Exception as e:
            print(f"Error downloading DOI {doi}: {e}")
        finally:
            time.sleep(1.0)  # Avoid overwhelming the server

class DOIIntegrator:
    def __init__(self, output_folder: str, api_keys: dict):
        self.output_folder = output_folder
        self.api_keys = api_keys

        # Ensure output directory exists
        os.makedirs(self.output_folder, exist_ok=True)

        # Instantiate downloaders
        self.downloaders = {
            "Elsevier": ElsevierDownloader(self.output_folder, self.api_keys.get("Elsevier")),
            "Springer": SpringerDownloader(self.output_folder),
            "Wiley": WileyDownloader(self.output_folder, self.api_keys.get("Wiley"))
        }

    def download_from_record(self, record):
        doi = record.get("doi")
        publisher = record.get("publisher")
        safe_doi = record.get("safe_doi")

        if not doi or not publisher or not safe_doi:
            raise ValueError("Missing required fields in record.")

        # Construct file path using safe_doi and publisher
        if 'Elsevier' in publisher or 'Springer' in publisher:
            file_path = os.path.join(self.output_folder, f"{safe_doi}.html")
        elif 'Wiley' in publisher:
            file_path = os.path.join(self.output_folder, f"{safe_doi}.pdf")
        else:
            raise ValueError(f"Unknown publisher for DOI: {doi}")

        downloader = None
        if 'Elsevier' in publisher:
            downloader = self.downloaders.get("Elsevier")
        elif 'Springer' in publisher:
            downloader = self.downloaders.get("Springer")
        elif 'Wiley' in publisher:
            downloader = self.downloaders.get("Wiley")

        if not downloader:
            raise ValueError(f"No downloader configured for publisher: {publisher}")

        # Perform the download
        downloader.download_paper(doi)

        return file_path

if __name__ == "__main__":

    client = MongoClient()
    scratch = client['scratch']['records']
    errors = client['scratch']['errors']
    failed_records = list(scratch.find({'download_succeeded': False}))
    
    output_folder = '/data/scratch'
    api_keys = {"Elsevier": 'elsevier_key', "Wiley": "wiley_key"}
    integrator = DOIIntegrator(output_folder, api_keys)
    
    for record in tqdm(failed_records, total=len(failed_records)):
        doi = record.get('doi')
        safe_doi = record.get('safe_doi')
        publisher = record.get('publisher')
    
        try:
            file_path = integrator.download_from_record(record)
    
            # Set universal success flags
            record['download_attempted'] = True
            record['download_succeeded'] = True
            record['download_date'] = datetime.utcnow()
            record['have_any'] = True
    
            # Determine content type by extension
            if file_path.endswith(".html"):
                record['have_html'] = True
                record['have_pdf'] = False
                record['html_path'] = file_path
                record['pdf_path'] = None
            elif file_path.endswith(".pdf"):
                record['have_pdf'] = True
                record['have_html'] = False
                record['pdf_path'] = file_path
                record['html_path'] = None
            else:
                raise ValueError("Unknown file format downloaded.")
    
            # Update the scratch record using DOI as key
            scratch.replace_one({'doi': record['doi']}, record)
    
        except Exception as e:
             record['download_attempted'] = True
             record['download_succeeded'] = False
             record['download_error'] = str(e)
             record['download_date'] = datetime.utcnow()
             record.pop('_id', None)
             errors.insert_one(record)
             scratch.delete_one({'doi': record['doi']})
             #print(f"[ERROR] Failed: {doi} — {e}")
        
        time.sleep(1.0)
