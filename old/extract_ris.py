#!/usr/bin/env python3

import csv
import os
import re
import pandas as pd
from datetime import datetime

def extract_bibliographic_data(ris_file):
    """Extract complete bibliographic information from a RIS file."""
    
    # List to store bibliographic entries
    entries = []
    
    # RIS tags we're interested in
    TITLE_TAGS = ['TI', 'T1']        # Primary title tags
    JOURNAL_TAGS = ['T2', 'JO', 'JF', 'J2']  # Journal/secondary title tags
    AUTHOR_TAGS = ['AU', 'A1']       # Author tags
    DATE_TAGS = ['DA', 'PY', 'Y1']   # Date tags
    DOI_TAG = 'DO'                   # DOI tag
    
    # Open and read the RIS file
    with open(ris_file, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    # Parse the RIS file
    current_entry = {}
    authors = []
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Check if line starts a new entry
        if line.startswith('TY  - '):
            # If we have an entry in progress, save it
            if current_entry and ('title' in current_entry or 'journal' in current_entry):
                if authors:
                    current_entry['authors'] = authors
                entries.append(current_entry)
            
            # Start a new entry
            current_entry = {}
            authors = []
        
        # Check if line ends an entry
        elif line.startswith('ER  - '):
            # Save the current entry if it has a title or journal
            if current_entry and ('title' in current_entry or 'journal' in current_entry):
                # If we have a journal but no title, use journal as title
                if 'journal' in current_entry and 'title' not in current_entry:
                    current_entry['title'] = current_entry['journal']
                
                if authors:
                    current_entry['authors'] = authors
                entries.append(current_entry)
            
            # Reset for next entry
            current_entry = {}
            authors = []
        
        # Process regular fields
        elif line[0:2].strip() and line[2:6] == '  - ':
            tag = line[0:2].strip()
            value = line[6:].strip()
            
            # Primary Title (article title)
            if tag in TITLE_TAGS and value:
                current_entry['title'] = value
            
            # Journal Title
            elif tag in JOURNAL_TAGS and value:
                current_entry['journal'] = value
            
            # Author
            elif tag in AUTHOR_TAGS and value:
                # Add author to the list
                authors.append(value)
            
            # DOI
            elif tag == DOI_TAG and value:
                if not value.startswith('https://doi.org/'):
                    current_entry['doi'] = f"https://doi.org/{value}"
                else:
                    current_entry['doi'] = value
            
            # Date published
            elif tag in DATE_TAGS and value:
                # Clean up the date format
                # RIS date can be in various formats like YYYY/MM/DD/ or YYYY//
                date_value = value.rstrip('/')
                
                # If it's a complex date with slashes, simplify it
                if '/' in date_value:
                    parts = date_value.split('/')
                    # Keep most significant parts (year and possibly month)
                    if len(parts) >= 2 and parts[0].strip():
                        # If there's a year and month
                        if parts[0].strip() and parts[1].strip():
                            date_value = f"{parts[0]}-{parts[1]}"
                        else:
                            # Just use year if month is empty
                            date_value = parts[0]
                
                current_entry['date_published'] = date_value
                
                # Extract year for reference formatting
                year_match = re.search(r'(\d{4})', value)
                if year_match:
                    current_entry['year'] = year_match.group(1)
                else:
                    current_entry['year'] = value
    
    # In case the file doesn't end with ER tag, process the last entry
    if current_entry and ('title' in current_entry or 'journal' in current_entry):
        # If we have a journal but no title, use journal as title
        if 'journal' in current_entry and 'title' not in current_entry:
            current_entry['title'] = current_entry['journal']
        
        if authors:
            current_entry['authors'] = authors
        entries.append(current_entry)
    
    # Filter out entries that don't have a title
    filtered_entries = [entry for entry in entries if 'title' in entry]
    
    return filtered_entries

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
    
    # Journal
    if 'journal' in entry:
        reference += f"{entry['journal']}. "
    
    # DOI
    if 'doi' in entry:
        reference += f"{entry['doi']}"
    
    return reference

if __name__ == "__main__":
    # Files to process
    ris_files = ["BIOL645.ris"]
    
    # List to store all references
    all_entries = []
    
    # Process each file
    for ris_file in ris_files:
        if os.path.exists(ris_file):
            entries = extract_bibliographic_data(ris_file)
            all_entries.extend(entries)
            print(f"Extracted {len(entries)} entries from {ris_file}")
        else:
            print(f"File {ris_file} not found.")
    
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
        output_file = "ris_references.csv"
        df.to_csv(output_file, index=False)
        print(f"Saved {len(df)} references to {output_file}")
    else:
        print("No entries found to generate references.") 