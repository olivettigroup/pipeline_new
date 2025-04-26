import re
from bs4 import BeautifulSoup
import os
import random
from datetime import datetime
from tqdm import tqdm
from pymongo import MongoClient
# ---------------------------------------
# 1. DOI PREFIX MAPPING
# ---------------------------------------
PREFIXES = {
    'els': ['10\.1016', '10\.1006', '10\.1205'],
    'spr': ['10\.1007', '10\.1140', '10\.1891', '10\.1617', '10\.1023', '10\.1186'],
    'rsc': ['10\.1039'],
    # Add more here as needed
}

def identify_publisher(doi):
    for publisher, patterns in PREFIXES.items():
        for pattern in patterns:
            if re.match(pattern, doi):
                return publisher
    return None

# ---------------------------------------
# 2. BASE CLASS
# ---------------------------------------
class PublisherParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.soup = None

    def determine_parser(self):
        raise NotImplementedError

    def load_soup(self, parser):
        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as file:
            self.soup = BeautifulSoup(file, parser)

    def extract_metadata(self):
        raise NotImplementedError

    def extract_content(self):
        raise NotImplementedError

    def classify_section(self, section_name, supersection_name=""):
        section = section_name.lower() if section_name else ""
        supersection = supersection_name.lower() if supersection_name else ""
        both = section + " " + supersection
    
        # Rule 1: Null or irrelevant sections
        if any(key in both for key in [
            'acknow', 'reference', 'author', 'highlight', 'supple', 'citing',
            'appendix', 'fund', 'nomencl', 'support', 'times cited',
            'publication history', 'keywords', 'key words', 'conflict'
        ]):
            return 'null'
    
        # Rule 2: Abstract
        if 'abstract' in section and 'abstract' in supersection:
            return 'abstract'
    
        # Rule 3: Intro
        if 'intro' in section or 'intro' in supersection:
            return 'intro'
    
        # Rule 4: Results/Discussion
        if any(k in both for k in ['result', 'discuss']):
            return 'results'
    
        # Rule 5: Conclusion
        if 'conclu' in both:
            return 'conclusions'
    
        # Rule 6: Recipe-related (synthesis, preparation)
        if (any(k in section for k in ['material', 'reage', 'prep', 'treat', 'depo', 'processing', 'synth', 'fabrica']) and
            any(k in supersection for k in ['experi', 'method']) and
            not any(k in both for k in ['charac', 'detect', 'analys', 'measurement', 'quanti', 'test'])):
            return 'recipe'
    
        # Rule 7: Non-recipe methods (characterization, analysis)
        if (any(k in section for k in [
                'charac', 'test', 'analys', 'measurement', 'quanti', 'identi',
                'scopy', 'spectro', 'x-ray', 'diffrac', 'quali', 'xr'
            ]) and
            any(k in supersection for k in ['experi', 'method']) and
            not any(k in both for k in ['synth', 'prepar'])):
            return 'nonrecipe_methods'
    
        return 'other'

    def parse(self):
        parser = self.determine_parser()
        self.load_soup(parser)
        return {
            "metadata": self.extract_metadata(),
            "content": self.extract_content()
        }

# ---------------------------------------
# 3. ELSEVIER PARSER
# ---------------------------------------
class ElsevierParser(PublisherParser):
    def determine_parser(self):
        with open(self.file_path, "r", encoding="utf-8") as file:
            content = file.read(2048).lower()
        return 'xml' if '<?xml' in content or '<ce:title>' in content else 'lxml'

    def extract_metadata(self):
        soup = self.soup
        metadata = {"title": None, "doi": None, "publisher": "Elsevier", "abstract": None}
        title_tag = soup.find('ce:title') or soup.find('meta', {'name': 'dc.title'}) or soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text(strip=True) if hasattr(title_tag, 'get_text') else title_tag.get('content', None)
        doi_tag = soup.find('ce:doi') or soup.find('meta', {'name': 'citation_doi'}) or soup.find('meta', {'name': 'dc.identifier'})
        if doi_tag:
            metadata['doi'] = doi_tag.get_text(strip=True) if hasattr(doi_tag, 'get_text') else doi_tag.get('content', None)
        abstract = None
        abstract_tag = soup.find('ce:abstract') or soup.find('abstract')
        if abstract_tag:
            abstract_paras = abstract_tag.find_all(['ce:simple-para', 'para', 'p'])
            abstract = ' '.join(p.get_text(strip=True) for p in abstract_paras if p.get_text(strip=True))
        if not abstract:
            abstract_div = soup.find('div', class_='abstract svAbstract')
            if abstract_div:
                abstract_p = abstract_div.find('p')
                if abstract_p:
                    abstract = abstract_p.get_text(strip=True)
        if not abstract:
            meta_tag = soup.find('meta', {'name': 'dc.description'}) or soup.find('meta', {'name': 'description'}) or soup.find('meta', {'name': 'og:description'})
            if meta_tag:
                abstract = meta_tag.get('content')
        metadata['abstract'] = abstract
        return metadata

    def extract_content(self):
        soup = self.soup
        paragraphs = []
        article_tag = soup.find("article") or soup.find("body")
        if not article_tag:
            return paragraphs
        for tag in article_tag.find_all(['table', 'figure', 'aside', 'footer', 'header', 'references', 'ref-list', 'nav', 'script', 'style']):
            tag.decompose()
        current_section = 'Main'
        for tag in article_tag.find_all(['h1', 'h2', 'h3', 'ce:section-title', 'p', 'ce:para']):
            if tag.name in ['h1', 'h2', 'h3', 'ce:section-title']:
                current_section = tag.get_text(strip=True)
            elif tag.name in ['p', 'ce:para']:
                text = tag.get_text(strip=True)
                if text:
                    paragraphs.append({
                        "section": current_section,
                        "supersection": supersection,
                        "text": text,
                        "type": self.classify_section(current_section, supersection)
                    })
        return paragraphs

# ---------------------------------------
# 4. SPRINGER PARSER
# ---------------------------------------
class SpringerParser(PublisherParser):
    def determine_parser(self):
        with open(self.file_path, "r", encoding="utf-8") as file:
            content = file.read(2048).lower()
        return 'xml' if '<?xml' in content else 'lxml'

    def extract_metadata(self):
        soup = self.soup
        metadata = {"title": None, "doi": None, "publisher": "Springer", "abstract": None}
        meta_mapping = {
            'title': ['citation_title', 'dc.title', 'og:title'],
            'doi': ['citation_doi', 'prism.doi', 'dc.identifier'],
            'abstract': ['dc.description', 'description', 'og:description', 'twitter:description']
        }
        for key, names in meta_mapping.items():
            for name in names:
                tag = soup.find('meta', attrs={"name": name}) or soup.find('meta', attrs={"property": name})
                if tag and tag.get('content'):
                    metadata[key] = tag.get('content').strip()
                    break
        if not metadata["abstract"]:
            section = soup.find(['section', 'div'], class_=re.compile('Abstract'))
            if section:
                para = section.find('p')
                if para:
                    metadata["abstract"] = para.get_text(strip=True)
        return metadata

    def extract_content(self):
        soup = self.soup
        paragraphs = []
        article_tag = soup.find("article") or soup.find("body")
        if not article_tag:
            return paragraphs
        for tag in article_tag.find_all(['table', 'figure', 'aside', 'footer', 'header', 'nav', 'script', 'style']):
            tag.decompose()
        current_section = "Unknown"
        for tag in article_tag.descendants:
            if tag.name in ['h1', 'h2', 'h3']:
                current_section = tag.get_text(strip=True)
            elif tag.name == 'p':
                text = tag.get_text(strip=True)
                if text:
                    paragraphs.append({
                        "section": current_section,
                        "text": text,
                        "type": self.classify_section(current_section)
                    })
        return paragraphs

# ---------------------------------------
# 5. RSC PARSER
# ---------------------------------------
class RSCParser(PublisherParser):
    def determine_parser(self):
        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as file:
            content = file.read(2048).lower()
        if "<?xml" in content or "xmlns" in content:
            return "lxml"
        return "html.parser"

    def extract_metadata(self):
        soup = self.soup
        metadata = {"title": None, "doi": None, "publisher": "Royal Society of Chemistry", "authors": [], "abstract": None}
        title_tag = soup.find("meta", attrs={"name": "DC.title"}) or soup.find("meta", attrs={"name": "citation_title"})
        if title_tag:
            metadata["title"] = title_tag.get("content", "").strip()
        doi_tag = soup.find("meta", attrs={"name": "DC.Identifier", "scheme": "doi"}) or soup.find("meta", attrs={"name": "citation_doi"})
        if doi_tag:
            metadata["doi"] = doi_tag.get("content", "").strip()
        authors = soup.find_all("meta", attrs={"name": "DC.Creator"}) + soup.find_all("meta", attrs={"name": "citation_author"})
        metadata["authors"] = list(set(tag.get("content", "").strip() for tag in authors))
        abstract_tag = soup.find("p", class_="abstract")
        if abstract_tag:
            metadata["abstract"] = abstract_tag.get_text(strip=True)
        return metadata

    def extract_content(self):
        soup = self.soup
        paragraphs = []
        article_tag = soup.find('article') or soup.find('body')
        if not article_tag:
            return paragraphs
        for tag in article_tag.find_all(['table', 'figure', 'figcaption', 'aside', 'footer', 'header', 'nav', 'script', 'style', 'code']):
            tag.decompose()
        for tag in article_tag.find_all('p', class_='header_text'):
            tag.decompose()
        current_section = 'Main'
        for tag in article_tag.find_all(['h1', 'h2', 'h3', 'p']):
            if tag.name in ['h1', 'h2', 'h3']:
                current_section = tag.get_text(strip=True)
            elif tag.name == 'p':
                text = tag.get_text(" ", strip=True)
                if text and len(text) > 20:
                    paragraphs.append({
                        "section": current_section,
                        "text": text,
                        "type": self.classify_section(current_section)
                    })
        return paragraphs

# ---------------------------------------
# 6. MAIN INTERFACE
# ---------------------------------------
def parse_document(doi, file_path):
    publisher_code = identify_publisher(doi)
    if publisher_code == 'els':
        parser = ElsevierParser(file_path)
    elif publisher_code == 'spr':
        parser = SpringerParser(file_path)
    elif publisher_code == 'rsc':
        parser = RSCParser(file_path)
    else:
        raise ValueError(f"Unsupported publisher for DOI: {doi}")
    return parser.parse()

if __name__ == "__main__":
    
    client = MongoClient()
    scratch = client['scratch']['records']
    papers = client['papers']['records']
    metadata = client['metadata']['records']
    scratch_errors = client['scratch']['errors']
    # Step 1: Find all records ready to be parsed
    records = list(scratch.find({'download_succeeded': True, 'parsed': False}))
    print(f"Found {len(records)} unparsed records.")

    for record in tqdm(records, total=len(records)):
        doi = record.get('doi')
        file_path = record.get('html_path')
    
        if not file_path or not os.path.exists(file_path):
            continue
    
        try:
            # Step 1: Run the parser
            parsed_data = parse_document(doi, file_path)
    
            # Step 2: Save parsed content to 'papers.records'
            _dict = {
                'doi': doi,
                'title': record.get('title'),
                'safe_doi': record.get('safe_doi'),
                'paragraphs': parsed_data['content']
            }
            papers.insert_one(_dict)
    
            # Step 3: Move record to 'metadata.records' with updated flags
            record['parsed'] = True
            record['parsed_date'] = datetime.utcnow()
            metadata.insert_one(record)
    
        except Exception as e:
            record['parsed'] = False
            record['error'] = str(e)
            scratch_errors.insert_one(record)
    
        finally:
            # Step 4: Always delete original from 'scratch.records'
            scratch.delete_one({'_id': record['_id']})
    
    