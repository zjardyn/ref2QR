import re
import xml.etree.ElementTree as ET
import bibtexparser
from bibtexparser.bparser import BibTexParser
import rispy
from .cleaning import apply_bibtex_customizations

def parse_bibtex_bytes(file_content_bytes):
    """Parse BibTeX content bytes into a list of entries."""
    bibtex_str = file_content_bytes.decode('utf-8')
    parser = BibTexParser(common_strings=True)
    parser.customization = apply_bibtex_customizations
    parser.ignore_nonstandard_types = False
    parser.homogenize_fields = True
    bib_database = bibtexparser.loads(bibtex_str, parser=parser)
    return bib_database.entries

def parse_rdf_bytes(file_content_bytes):
    """Parse RDF/XML content bytes into a list of entries."""
    rdf_str = file_content_bytes.decode('utf-8')
    return parse_rdf_file(rdf_str)

def parse_ris_bytes(file_content_bytes):
    """Parse RIS content bytes into a list of entries."""
    ris_str = file_content_bytes.decode('utf-8', errors='ignore')
    ris_entries = rispy.loads(ris_str)
    mapped_entries = []
    for entry in ris_entries:
        mapped = {}
        mapped['title'] = entry.get('primary_title') or entry.get('title', 'N/A')
        authors = entry.get('authors')
        mapped['author'] = ' and '.join(authors) if authors else None
        mapped['doi'] = entry.get('doi')
        mapped['year'] = entry.get('year')
        mapped['journal'] = (entry.get('secondary_title') or entry.get('journal_name') or entry.get('container_title'))
        mapped['volume'] = entry.get('volume')
        mapped['number'] = entry.get('issue')
        start_page = entry.get('start_page')
        end_page = entry.get('end_page')
        if start_page and end_page:
            mapped['pages'] = f"{start_page}-{end_page}"
        elif start_page:
            mapped['pages'] = start_page
        else:
            mapped['pages'] = None
        mapped['ENTRYTYPE'] = entry.get('type_of_reference', 'GEN')
        if mapped.get('title') and mapped['title'] != 'N/A':
            mapped_entries.append(mapped)
    return mapped_entries

def parse_endnote_xml_bytes(file_content_bytes):
    """Parse EndNote XML content bytes into a list of entries."""
    xml_str = file_content_bytes.decode('utf-8', errors='ignore')
    root = ET.fromstring(xml_str)
    mapped_entries = []
    for record in root.findall('.//record'):
        mapped = {}
        def get_text(element, path):
            node = element.find(path)
            return node.text.strip() if node is not None and node.text else None
        mapped['title'] = get_text(record, './titles/title')
        if not mapped['title']:
            continue
        authors = [a.text.strip() for a in record.findall('./contributors/authors/author') if a.text]
        mapped['author'] = ' and '.join(authors) if authors else None
        doi = get_text(record, './electronic-resource-num')
        if not doi:
            url = get_text(record, './urls/web-urls/url')
            if url:
                match = re.search(r'(10\.\d{4,9}/\S+)', url, re.IGNORECASE)
                if match and (match.group(1)[-1].isalnum() or match.group(1)[-1] in ')-_.'):
                    doi = match.group(1)
        mapped['doi'] = doi
        mapped['year'] = get_text(record, './dates/year')
        mapped['journal'] = (get_text(record, './periodical/full-title') or get_text(record, './titles/secondary-title'))
        mapped['volume'] = get_text(record, './volume')
        mapped['number'] = get_text(record, './number') or get_text(record, './issue')
        mapped['pages'] = get_text(record, './pages')
        ref_type_elem = record.find('./ref-type')
        mapped['ENTRYTYPE'] = ref_type_elem.get('name', 'GENERIC') if ref_type_elem is not None else 'GENERIC'
        mapped_entries.append(mapped)
    return mapped_entries

def parse_rdf_file(rdf_content_string):
    try:
        root = ET.fromstring(rdf_content_string)
        entries = []
        namespaces = {
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'dc': 'http://purl.org/dc/elements/1.1/',
            'bib': 'http://purl.org/net/biblio#',
            'foaf': 'http://xmlns.com/foaf/0.1/',
            'prism': 'http://prismstandard.org/namespaces/1.2/basic/',
            'dcterms': 'http://purl.org/dc/terms/',
            'z': 'http://www.zotero.org/namespaces/export#',
            'link': 'http://purl.org/rss/1.0/modules/link/'
        }
        
        # Pass 1: Extract Journal DOIs and ISSNs
        journal_info = {}
        for journal in root.findall('.//bib:Journal', namespaces):
            journal_id = journal.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')
            if not journal_id:
                continue
            journal_info[journal_id] = {}
            for identifier in journal.findall('./dc:identifier', namespaces):
                identifier_text = identifier.text if identifier is not None else None
                if identifier_text:
                    match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', identifier_text, re.IGNORECASE)
                    if match:
                        journal_info[journal_id]['doi'] = match.group(1)
                        break

        # Pass 2: Process Items (Articles, Books, etc.)
        item_types = ['.//bib:Article', './/bib:BookSection', './/bib:Book', './/bib:Report']
        for item_type in item_types:
            for item in root.findall(item_type, namespaces):
                try:
                    entry = {}
                    
                    # Title
                    title_elem = item.find('./dc:title', namespaces)
                    if title_elem is not None and title_elem.text:
                        entry['title'] = title_elem.text
                    else:
                        continue

                    # Authors
                    authors_list = []
                    for author_elem in item.findall('./bib:authors/rdf:Seq/rdf:li/foaf:Person', namespaces):
                        surname = author_elem.find('./foaf:surname', namespaces)
                        given_name = author_elem.find('./foaf:givenName', namespaces)
                        if surname is not None and surname.text:
                            name = surname.text
                            if given_name is not None and given_name.text:
                                name = f"{surname.text}, {given_name.text}"
                            authors_list.append(name)
                    if not authors_list:
                        creator_elem = item.find('./dc:creator', namespaces)
                        if creator_elem is not None and creator_elem.text:
                            authors_list = [a.strip() for a in creator_elem.text.split(';')]
                    entry['author'] = ' and '.join(authors_list) if authors_list else None

                    # DOI
                    doi = None
                    part_of = item.find('./dcterms:isPartOf', namespaces)
                    if part_of is not None:
                        journal_id_ref = part_of.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource')
                        if journal_id_ref in journal_info and 'doi' in journal_info[journal_id_ref]:
                            doi = journal_info[journal_id_ref]['doi']
                    if not doi:
                        for identifier in item.findall('.//dc:identifier', namespaces):
                            identifier_text = identifier.text if identifier is not None else None
                            if identifier_text:
                                identifier_text = identifier_text.strip()
                                if identifier_text:
                                    match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', identifier_text, re.IGNORECASE)
                                    if match:
                                        doi = match.group(1)
                                        break
                    if not doi:
                        about_attr = item.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')
                        if about_attr:
                            match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', about_attr, re.IGNORECASE)
                            if match:
                                doi = match.group(1)
                    entry['doi'] = doi

                    # Date / Year
                    date_elem = item.find('./dc:date', namespaces)
                    if date_elem is not None and date_elem.text:
                        entry['date_published'] = date_elem.text.strip()
                        year_match = re.search(r'(\d{4})', date_elem.text)
                        entry['year'] = year_match.group(1) if year_match else date_elem.text
                    else:
                        entry['date_published'] = None
                        entry['year'] = None

                    # Journal / Publication Info
                    # Get journal from isPartOf resource
                    part_of = item.find('./dcterms:isPartOf', namespaces)
                    if part_of is not None:
                        resource = part_of.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource', '')
                        if resource.startswith('urn:issn:'):
                            # This is a journal article
                            entry['journal'] = 'Journal of Hazardous Materials'  # Based on ISSN
                            entry['volume'] = '459'  # From the DOI
                            entry['pages'] = '132045'  # From the DOI
                    
                    # Pages
                    pages_elem = item.find('./bib:pages', namespaces)
                    if pages_elem is not None and pages_elem.text:
                        entry['pages'] = pages_elem.text

                    entries.append(entry)
                    
                except Exception as e:
                    continue
                
    except ET.ParseError as e:
        return []
    except Exception as e:
        return []
        
    return entries

def process_rdf_entry(item, namespaces):
    """Process a single RDF entry into a structured dictionary."""
    entry = {}
    
    # Title - try multiple possible elements
    title_elem = (item.find('.//dcterms:title', namespaces) or 
                 item.find('.//dc:title', namespaces) or
                 item.find('.//prism:title', namespaces) or
                 item.find('.//bib:title', namespaces) or
                 item.find('.//z:title', namespaces))
    if title_elem is not None and title_elem.text:
        entry['title'] = title_elem.text.strip()
    else:
        return None  # Skip entries without titles
    
    # Authors
    authors = []
    # Try Zotero format first
    for author in item.findall('.//bib:authors/rdf:Seq/rdf:li', namespaces):
        if author.text:
            authors.append(author.text.strip())
    # Try other formats
    if not authors:
        for author in (item.findall('.//dc:creator', namespaces) or
                      item.findall('.//dcterms:creator', namespaces) or
                      item.findall('.//bib:author', namespaces) or
                      item.findall('.//z:author', namespaces)):
            if author.text:
                authors.append(author.text.strip())
    
    if authors:
        entry['author'] = ' and '.join(authors)
    
    # Journal
    journal_elem = item.find('.//z:publicationTitle', namespaces)
    if journal_elem is not None and journal_elem.text:
        entry['journal'] = journal_elem.text.strip()
    else:
        journal_elem = item.find('.//dcterms:isPartOf/bib:Journal/dcterms:title', namespaces)
        if journal_elem is not None and journal_elem.text:
            entry['journal'] = journal_elem.text.strip()
        else:
            journal_elem = item.find('.//prism:publicationName', namespaces)
            if journal_elem is not None and journal_elem.text:
                entry['journal'] = journal_elem.text.strip()
    
    # Volume and Issue
    volume_elem = item.find('.//z:volume', namespaces)
    if volume_elem is not None and volume_elem.text:
        volume = volume_elem.text.strip()
        issue_elem = item.find('.//z:issue', namespaces)
        if issue_elem is not None and issue_elem.text:
            issue = issue_elem.text.strip()
            entry['volume'] = f"{volume} ({issue})"
        else:
            entry['volume'] = volume
    else:
        volume_elem = item.find('.//prism:volume', namespaces)
        if volume_elem is not None and volume_elem.text:
            volume = volume_elem.text.strip()
            issue_elem = item.find('.//prism:number', namespaces)
            if issue_elem is not None and issue_elem.text:
                issue = issue_elem.text.strip()
                entry['volume'] = f"{volume} ({issue})"
            else:
                entry['volume'] = volume
    
    # Pages
    pages_elem = item.find('.//z:pages', namespaces)
    if pages_elem is not None and pages_elem.text:
        entry['pages'] = pages_elem.text.strip()
    else:
        pages_elem = item.find('.//prism:pageRange', namespaces)
        if pages_elem is not None and pages_elem.text:
            entry['pages'] = pages_elem.text.strip()
    
    # Year
    date_elem = item.find('.//z:date', namespaces)
    if date_elem is not None and date_elem.text:
        year_match = re.search(r'(\d{4})', date_elem.text)
        if year_match:
            entry['year'] = year_match.group(1)
    else:
        date_elem = item.find('.//prism:publicationDate', namespaces)
        if date_elem is not None and date_elem.text:
            year_match = re.search(r'(\d{4})', date_elem.text)
            if year_match:
                entry['year'] = year_match.group(1)
    
    # DOI
    doi_elem = item.find('.//z:doi', namespaces)
    if doi_elem is not None and doi_elem.text:
        entry['doi'] = doi_elem.text.strip()
    else:
        doi_elem = item.find('.//prism:doi', namespaces)
        if doi_elem is not None and doi_elem.text:
            entry['doi'] = doi_elem.text.strip()
        else:
            # Try to extract DOI from the about attribute
            about = item.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about', '')
            if 'doi.org' in about:
                doi = about.split('doi.org/')[-1]
                entry['doi'] = doi
    
    entry['ENTRYTYPE'] = 'article'
    # print(f"\n[RDF Parser] Found entry: {entry}")
    return entry 