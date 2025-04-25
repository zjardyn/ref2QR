#!/usr/bin/env python3

import xml.etree.ElementTree as ET
import csv
import re
import os
import pandas as pd
from datetime import datetime

def extract_bibliographic_data(rdf_file):
    """Extract complete bibliographic information from an RDF file."""
    # Register namespaces for RDF parsing
    namespaces = {
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'dc': 'http://purl.org/dc/elements/1.1/',
        'bib': 'http://purl.org/net/biblio#',
        'z': 'http://www.zotero.org/namespaces/export#',
        'foaf': 'http://xmlns.com/foaf/0.1/',
        'prism': 'http://prismstandard.org/namespaces/1.2/basic/',
        'dcterms': 'http://purl.org/dc/terms/'
    }
    
    # Parse the RDF file
    tree = ET.parse(rdf_file)
    root = tree.getroot()
    
    # First, extract all journals with their DOIs
    journals = {}
    for journal in root.findall('.//bib:Journal', namespaces):
        journal_id = journal.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')
        if not journal_id:
            continue
            
        journal_info = {'id': journal_id}
        
        # Get journal DOI
        for identifier in journal.findall('./dc:identifier', namespaces):
            if identifier.text and 'DOI' in identifier.text:
                doi_text = identifier.text.strip()
                # Format as URL
                if doi_text.startswith('DOI '):
                    doi_number = doi_text.replace('DOI ', '')
                    journal_info['doi'] = f"https://doi.org/{doi_number}"
                else:
                    journal_info['doi'] = doi_text
        
        # Store journal info
        journals[journal_id] = journal_info
    
    # List to store bibliographic entries
    entries = []
    
    # Find all article and book section entries
    article_types = ['.//bib:Article', './/bib:BookSection']
    
    for article_type in article_types:
        for article in root.findall(article_type, namespaces):
            entry = {}
            
            # Get article URL or ID from the about attribute
            about_attr = article.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')
            if about_attr:
                if 'doi.org' in about_attr:
                    entry['doi'] = about_attr
                elif 'pubmed' in about_attr:
                    entry['pubmed'] = about_attr
                elif 'sciencedirect.com' in about_attr or 'nature.com' in about_attr:
                    entry['url'] = about_attr
            
            # Check if article is linked to a journal
            journal_ref = article.find('./dcterms:isPartOf', namespaces)
            if journal_ref is not None:
                journal_id = journal_ref.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource')
                if journal_id in journals and 'doi' in journals[journal_id]:
                    entry['doi'] = journals[journal_id]['doi']
            
            # Also check for DOI in dc:identifier elements
            for identifier in article.findall('.//dc:identifier', namespaces):
                if identifier.text and 'DOI' in identifier.text:
                    doi_text = identifier.text.strip()
                    # Format as URL if it's just the DOI number
                    if doi_text.startswith('DOI '):
                        doi_number = doi_text.replace('DOI ', '')
                        entry['doi'] = f"https://doi.org/{doi_number}"
                    else:
                        entry['doi'] = doi_text
            
            # Get title
            title_elem = article.find('./dc:title', namespaces)
            if title_elem is not None and title_elem.text:
                entry['title'] = title_elem.text
            
            # Get authors
            authors = []
            for author_elem in article.findall('./bib:authors/rdf:Seq/rdf:li/foaf:Person', namespaces):
                surname = author_elem.find('./foaf:surname', namespaces)
                given_name = author_elem.find('./foaf:givenName', namespaces)
                if surname is not None and given_name is not None:
                    authors.append(f"{surname.text}, {given_name.text}")
                elif surname is not None:
                    authors.append(surname.text)
            entry['authors'] = authors
            
            # Get date/year - store both full date and year
            date_elem = article.find('./dc:date', namespaces)
            if date_elem is not None and date_elem.text:
                # Store the full date
                entry['date_published'] = date_elem.text.strip()
                
                # Also extract year for reference formatting
                year_match = re.search(r'(\d{4})', date_elem.text)
                if year_match:
                    entry['year'] = year_match.group(1)
                else:
                    entry['year'] = date_elem.text
            
            # Get journal/publication info
            journal_elem = article.find('./dcterms:isPartOf/bib:Journal', namespaces)
            if journal_elem is not None:
                # Journal title
                journal_title = journal_elem.find('./dc:title', namespaces)
                if journal_title is not None and journal_title.text:
                    entry['journal'] = journal_title.text
                
                # Volume
                volume = journal_elem.find('./prism:volume', namespaces)
                if volume is not None and volume.text:
                    entry['volume'] = volume.text
                
                # Issue/number
                issue = journal_elem.find('./prism:number', namespaces)
                if issue is not None and issue.text:
                    entry['issue'] = issue.text
            
            # Get pages
            pages_elem = article.find('./bib:pages', namespaces)
            if pages_elem is not None and pages_elem.text:
                entry['pages'] = pages_elem.text
            
            # Get abstract
            abstract_elem = article.find('./dcterms:abstract', namespaces)
            if abstract_elem is not None and abstract_elem.text:
                entry['abstract'] = abstract_elem.text
            
            # Add entry if it has at least a title
            if 'title' in entry:
                entries.append(entry)
    
    return entries

def format_apa_reference(entry):
    """Format a bibliographic entry in APA style."""
    reference = ""
    
    # Authors - only include first author + et al. for multiple authors
    if 'authors' in entry and entry['authors']:
        if len(entry['authors']) == 1:
            reference += f"{entry['authors'][0]}. "
        else:
            reference += f"{entry['authors'][0]} et al. "
    
    # Year
    if 'year' in entry:
        reference += f"({entry['year']}). "
    
    # Title
    if 'title' in entry:
        reference += f"{entry['title']}. "
    
    # Journal, volume, issue, pages
    if 'journal' in entry:
        reference += f"{entry['journal']}"
        
        if 'volume' in entry:
            reference += f", {entry['volume']}"
            
            if 'issue' in entry:
                reference += f"({entry['issue']})"
                
        if 'pages' in entry:
            reference += f", {entry['pages']}"
            
        reference += ". "
    
    # DOI
    if 'doi' in entry:
        reference += f"{entry['doi']}"
    elif 'pubmed' in entry:
        reference += f"{entry['pubmed']}"
    
    return reference

if __name__ == "__main__":
    # Files to process
    rdf_files = ["BIOL645.rdf"]
    
    # List to store all references
    all_entries = []
    
    # Process each file
    for rdf_file in rdf_files:
        if os.path.exists(rdf_file):
            entries = extract_bibliographic_data(rdf_file)
            all_entries.extend(entries)
        else:
            print(f"File {rdf_file} not found.")
    
    # Generate references
    if all_entries:
        # Create DataFrame with requested columns
        df_data = []
        for entry in all_entries:
            authors_str = entry['authors'][0] if entry.get('authors') and len(entry['authors']) > 0 else ""
            if 'authors' in entry and len(entry['authors']) > 1:
                authors_str += " et al."
            
            row = {
                'authors': authors_str,
                'title': entry.get('title', ''),
                'doi': entry.get('doi', entry.get('pubmed', '')),
                'date_published': entry.get('date_published', '')
            }
            df_data.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(df_data)
        
        # Save DataFrame to CSV
        df.to_csv("rdf_references.csv", index=False)
        print(f"Saved {len(df)} references to rdf_references.csv")
    else:
        print("No entries found to generate references.") 