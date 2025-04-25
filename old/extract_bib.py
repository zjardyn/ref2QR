#!/usr/bin/env python3

import bibtexparser
from bibtexparser.bparser import BibTexParser
import csv
import os
import re
import pandas as pd
from datetime import datetime

def extract_bibliographic_data(bib_file):
    """Extract complete bibliographic information from a BibTeX file."""
    
    # Create a parser that ignores non-standard entry types
    parser = BibTexParser(common_strings=True)
    parser.customization = lambda record: record  # No customization - keep everything
    
    # Parse the BibTeX file
    with open(bib_file, 'r', encoding='utf-8') as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file, parser=parser)
    
    # List to store bibliographic entries
    entries = []
    
    # Process each entry in the BibTeX file
    for entry in bib_database.entries:
        bib_entry = {}
        
        # Extract DOI
        if 'doi' in entry:
            doi = entry['doi'].strip()
            if not doi.startswith('https://doi.org/'):
                bib_entry['doi'] = f"https://doi.org/{doi}"
            else:
                bib_entry['doi'] = doi
        
        # Extract title
        if 'title' in entry:
            # Clean up title - remove braces and special formatting
            title = entry['title']
            title = re.sub(r'[{}]', '', title)
            title = re.sub(r'\\[a-zA-Z]+', '', title)
            bib_entry['title'] = title
        
        # Extract authors
        if 'author' in entry:
            # BibTeX authors are typically in the format "Last, First and Last, First"
            author_text = entry['author']
            # Split by 'and' and clean up
            authors = [author.strip() for author in author_text.split(' and ')]
            # Format as "Last, First"
            author_list = []
            for author in authors:
                if ',' in author:  # Already in Last, First format
                    author_list.append(author)
                else:  # In First Last format
                    parts = author.split()
                    if len(parts) > 1:
                        last_name = parts[-1]
                        first_names = ' '.join(parts[:-1])
                        author_list.append(f"{last_name}, {first_names}")
                    else:
                        author_list.append(author)
            
            bib_entry['authors'] = author_list
        
        # Extract date published
        date_published = None
        # Try different date fields
        for date_field in ['date', 'year', 'month', 'urldate']:
            if date_field in entry:
                date_published = entry[date_field]
                break
        
        if date_published:
            bib_entry['date_published'] = date_published
            
            # Extract year for reference formatting
            year_match = re.search(r'(\d{4})', date_published)
            if year_match:
                bib_entry['year'] = year_match.group(1)
            else:
                bib_entry['year'] = date_published
        
        # Get journal/publication info
        if 'journaltitle' in entry:
            bib_entry['journal'] = entry['journaltitle']
        elif 'journal' in entry:
            bib_entry['journal'] = entry['journal']
        
        # Get volume
        if 'volume' in entry:
            bib_entry['volume'] = entry['volume']
        
        # Get issue/number
        if 'number' in entry:
            bib_entry['issue'] = entry['number']
        
        # Get pages
        if 'pages' in entry:
            bib_entry['pages'] = entry['pages']
        
        # Get abstract
        if 'abstract' in entry:
            bib_entry['abstract'] = entry['abstract']
        
        # Add entry if it has at least a title
        if 'title' in bib_entry:
            entries.append(bib_entry)
    
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
    
    return reference

if __name__ == "__main__":
    # Files to process
    bib_files = ["BIOL645.bib"]
    
    # List to store all references
    all_entries = []
    
    # Process each file
    for bib_file in bib_files:
        if os.path.exists(bib_file):
            entries = extract_bibliographic_data(bib_file)
            all_entries.extend(entries)
            print(f"Extracted {len(entries)} entries from {bib_file}")
        else:
            print(f"File {bib_file} not found.")
    
    # Generate references
    if all_entries:
        # Create DataFrame with requested columns
        df_data = []
        for entry in all_entries:
            # Format authors for CSV
            if 'authors' in entry and entry['authors']:
                if len(entry['authors']) == 1:
                    authors_str = entry['authors'][0]
                else:
                    authors_str = f"{entry['authors'][0]} et al."
            else:
                authors_str = ""
            
            row = {
                'authors': authors_str,
                'title': entry.get('title', ''),
                'doi': entry.get('doi', ''),
                'date_published': entry.get('date_published', '')
            }
            df_data.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(df_data)
        
        # Save DataFrame to CSV
        output_file = "bib_references.csv"
        df.to_csv(output_file, index=False)
        print(f"Saved {len(df)} references to {output_file}")
    else:
        print("No entries found to generate references.") 