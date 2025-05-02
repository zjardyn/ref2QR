import re
from bibtexparser.customization import homogenize_latex_encoding, convert_to_unicode

def apply_bibtex_customizations(record):
    """Applies standard BibTeX cleaning customizations."""
    record = homogenize_latex_encoding(record)
    record = convert_to_unicode(record)
    # Add other customizations here if needed in the future
    return record

def clean_and_structure_entry(entry):
    """Cleans and structures a single BibTeX entry dictionary.
    Inspired by logic in extract_bib.py
    Args:
        entry (dict): A dictionary representing a single entry from bibtexparser.
    Returns:
        dict: A dictionary with cleaned and structured fields.
    """
    # print(f"\n[Cleaning] Processing entry: {entry}")
    cleaned_data = {}

    # --- DOI --- 
    # Handle potential None value before stripping
    doi_val = entry.get('doi') 
    raw_doi = doi_val.strip() if doi_val is not None else ''
    if raw_doi:
        if not raw_doi.startswith('http'): # Simple check for existing protocol
            cleaned_data['doi'] = f"https://doi.org/{raw_doi}"
        else:
            cleaned_data['doi'] = raw_doi
    else:
        cleaned_data['doi'] = None
    # print(f"[Cleaning] DOI: {cleaned_data['doi']}")

    # --- Title --- 
    raw_title = entry.get('title', 'N/A')
    # Remove braces and common LaTeX commands (like \textit, \textbf)
    # Note: convert_to_unicode customization handles accents like {"u}
    title_no_braces = re.sub(r'[{}]', '', raw_title)
    cleaned_data['title'] = re.sub(r'\[a-zA-Z]+', '', title_no_braces).strip()
    # print(f"[Cleaning] Title: {cleaned_data['title']}")
    
    # --- Authors --- 
    raw_authors = entry.get('author', '')
    if raw_authors:
        authors = [a.strip() for a in raw_authors.split(' and ')]
        author_list = []
        for author in authors:
            # Remove braces from author names
            author_clean = re.sub(r'[{}]', '', author)
            if ',' in author_clean: # Already in Last, First format (hopefully)
                author_list.append(author_clean)
            else: # Attempt to convert First Last to Last, First
                parts = author_clean.split()
                if len(parts) > 1:
                    last_name = parts[-1]
                    first_names = ' '.join(parts[:-1])
                    author_list.append(f"{last_name}, {first_names}")
                else:
                    author_list.append(author_clean) # Keep as is if single name
        cleaned_data['authors_formatted'] = '; '.join(author_list)  # Changed from authors_formatted to author
    else:
        cleaned_data['authors_formatted'] = 'N/A'  # Changed from N/A to None to match other fields
    # print(f"[Cleaning] Author: {cleaned_data['authors_formatted']}")

    # --- Date Published / Year --- 
    date_published_str = '' # Default to empty string
    # Check fields in order, use the first non-None string found
    for field in ['year', 'date', 'month']:
        val = entry.get(field)
        if val is not None and isinstance(val, str):
            date_published_str = val
            break # Found a valid string, stop checking
    if not date_published_str: # If still empty after checking fields
        date_published_str = 'N/A'
         
    cleaned_data['date_published'] = date_published_str
    # Extract year for display if possible (now date_published_str is guaranteed to be a string)
    year_match = re.search(r'(\d{4})', date_published_str)
    cleaned_data['year'] = year_match.group(1) if year_match else date_published_str  # Changed to None if no year found
    # print(f"[Cleaning] Year: {cleaned_data['year']}")

    # --- Journal / Publication Info --- 
    # Prefer journaltitle if available
    journal_val = entry.get('journaltitle') or entry.get('journal')
    if journal_val:
         cleaned_data['journal'] = re.sub(r'[{}]', '', journal_val).strip()
    else:
         cleaned_data['journal'] = None
    # print(f"[Cleaning] Journal: {cleaned_data['journal']}")

    # Add other fields if needed (volume, issue, pages) - keep simple for now
    cleaned_data['volume'] = entry.get('volume')
    cleaned_data['issue'] = entry.get('number')  # Changed from issue to number to match template
    cleaned_data['pages'] = entry.get('pages')
    # print(f"[Cleaning] Volume: {cleaned_data['volume']}, Issue: {cleaned_data['issue']}, Pages: {cleaned_data['pages']}")

    # print(f"[Cleaning] Final cleaned entry: {cleaned_data}")
    return cleaned_data 