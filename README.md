# pipeline_new

## Overview

**pipeline_new** is a modular system for automated literature search, download, and parsing, primarily focused on scientific papers in materials science and sustainability.  
It supports asynchronous operation, publisher-specific access methods, structured parsing, and organized database storage.

The system is designed to handle large-scale ingestion and structuring of research papers for downstream analysis, machine learning, and knowledge graph building.

---

## Repository Structure

```plaintext
/scripts/           # Python modules: search.py, download.py, parse.py (for external users)
/wiki/              # GitHub Wiki contains full documentation
/data/scratch/      # Downloaded full-text articles (local storage during runs)
/docs/ (optional)   # Additional notes or local copies of documentation
```

---

## Main Scripts

| Script | Purpose |
| :--- | :--- |
| `search.py` | Searches external APIs (Crossref, Dimensions, Lens) based on user-provided keywords. Requires command-line arguments for keywords, size, and given_name. |
| `download.py` | Downloads full-text articles based on DOIs, using publisher APIs or manual sources. |
| `parse.py` | Parses downloaded files into structured sections and paragraphs, then inserts them into MongoDB. |

---

## Setup Instructions

Depending on your access, please follow one of the two paths:

---

### Option A: Olivetti Lab Members (Spatula Server Users)

1. **Directory:**  
   Scripts are located directly under `/home/jupyter/Pipeline`.

2. **Environment:**  
   Activate the existing environment:

   ```bash
   conda activate pipeline_env
   ```

3. **Running the Pipeline:**

   ```bash
   cd /home/jupyter/Pipeline

   # 1. Search for papers (specify keywords, size, and given_name)
   python search.py --keywords "plastic" "ozone" "machine learning" --size 300 --given_name "plastic_ozone_search"

   # 2. Download papers
   python download.py

   # 3. Parse downloaded papers
   python parse.py
   ```

4. **No need to clone the repository or install dependencies.**

---

### Option B: External Users (New Users / Outside Lab)

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/YourUsername/pipeline_new.git
   cd pipeline_new
   ```

2. **Create the Conda Environment:**

   ```bash
   conda env create -f environment.yaml
   ```

3. **Activate the Environment:**

   ```bash
   conda activate pipeline_env
   ```

4. **Install Additional Pip Packages:**

   ```bash
   pip install dimcli==1.4
   ```

5. **Running the Pipeline:**

   ```bash
   cd scripts

   # 1. Search for papers (specify keywords, size, and given_name)
   python search.py --keywords "plastic" "ozone" "machine learning" --size 300 --given_name "plastic_ozone_search"

   # 2. Download papers
   python download.py

   # 3. Parse downloaded papers
   python parse.py
   ```

---

## Notes on Usage

- `search.py` **requires** the following arguments:
  - `--keywords`: One or more search terms.
  - `--size`: Number of DOIs to retrieve per source.
  - `--given_name`: Label to identify this search batch.

- Example:

  ```bash
  python search.py --keywords "solid state battery" "energy storage" --size 300 --given_name "battery_search"
  ```

- Always ensure the MongoDB server is running and accessible before starting the pipeline.

- All downloads happen under the `/data/scratch/` directory.

---

## Documentation

📚 Full usage instructions, pipeline flow, module guides, and best practices are available in the [Wiki](../../wiki).

Start here: [Overview](../../wiki/Overview)

---

## Author

- Vineeth Venugopal  
- [vinven7@gmail.com](mailto:vinven7@gmail.com)

---

## Acknowledgements

This project was developed to support data-driven materials discovery and automated scientific knowledge extraction.  
Special thanks to all contributors and maintainers for expanding and improving the pipeline's functionality.

---
