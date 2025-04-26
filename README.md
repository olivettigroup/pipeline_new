# Pipeline-2

## Overview

**Pipeline-2** is a modular system for automated literature search, download, and parsing, primarily focused on scientific papers in materials science and sustainability.  
It supports asynchronous operation, publisher-specific access methods, structured parsing, and organized database storage.

The system is designed to handle large-scale ingestion and structuring of research papers for downstream analysis, machine learning, and knowledge graph building.

---

## Repository Structure

```plaintext
/scripts/           # Python modules: search.py, download.py, parser.py
/wiki/              # GitHub Wiki contains full documentation
/data/scratch/      # Downloaded full-text articles (local storage during runs)
/docs/ (optional)   # Additional notes or local copies of documentation
```

---

## Main Scripts

| Script | Purpose |
| :--- | :--- |
| `search.py` | Searches external APIs (Crossref, Dimensions, Lens) based on user keywords and stores new DOIs into the scratch database. |
| `download.py` | Downloads full-text articles based on DOIs, using publisher APIs or manual sources. |
| `parser.py` | Parses downloaded files into structured sections and paragraphs, then inserts them into MongoDB. |

---

## How to Use

### 1. Setup

- Install required dependencies (Python 3.10+ recommended).
- Ensure MongoDB server is running and accessible.
- Recommended to use the provided Conda environment: `vineeth_10.1`.

```bash
conda activate vineeth_10.1
cd /home/jupyter/vineeth/pipeline-2
```

### 2. Running the Pipeline

Manually:

```bash
# Search for papers
python scripts/search.py --keywords "solid state battery" "energy storage" --given_name "battery_search"

# Download papers
python scripts/download.py

# Parse downloaded papers
python scripts/parser.py
```

Or use a batch script to run all stages (see examples in the wiki).

---

## Documentation

📚 Full usage instructions, module guides, and best practices are available in the [Wiki](../../wiki).

Start here: [Overview](../../wiki/Overview)

---

## Acknowledgements

This project was developed to support data-driven materials discovery and automated scientific knowledge extraction.  
Special thanks to contributors and maintainers for expanding the pipeline's functionality.

---
