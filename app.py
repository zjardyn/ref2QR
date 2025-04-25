import io
import base64
import uuid
import re
import html
import xml.etree.ElementTree as ET
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import homogenize_latex_encoding, convert_to_unicode
import rispy
from flask import Flask, request, render_template, url_for, abort
import qrcode
import database
import datetime
import json
import os
from PIL import Image

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # Limit upload size to 16MB
app.config['MAINTENANCE_KEY'] = 'change_this_key_for_production'

# Initialize database with our app
database.init_app(app)

# Add 'rdf' to allowed extensions
ALLOWED_EXTENSIONS = {'bib', 'rdf', 'ris', 'xml'}

# Helper function to apply multiple customizations
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

    # --- Title --- 
    raw_title = entry.get('title', 'N/A')
    # Remove braces and common LaTeX commands (like \textit, \textbf)
    # Note: convert_to_unicode customization handles accents like {"u}
    title_no_braces = re.sub(r'[{\}]', '', raw_title)
    cleaned_data['title'] = re.sub(r'\[a-zA-Z]+', '', title_no_braces).strip()
    
    # --- Authors --- 
    raw_authors = entry.get('author', '')
    if raw_authors:
        authors = [a.strip() for a in raw_authors.split(' and ')]
        author_list = []
        for author in authors:
            # Remove braces from author names
            author_clean = re.sub(r'[{\}]', '', author)
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
        cleaned_data['authors_formatted'] = '; '.join(author_list)
    else:
        cleaned_data['authors_formatted'] = 'N/A'

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
    cleaned_data['year'] = year_match.group(1) if year_match else date_published_str

    # --- Journal / Publication Info --- 
    # Prefer journaltitle if available
    journal_val = entry.get('journaltitle') or entry.get('journal')
    if journal_val:
         cleaned_data['journal'] = re.sub(r'[{\}]', '', journal_val).strip()
    else:
         cleaned_data['journal'] = None

    # Add other fields if needed (volume, issue, pages) - keep simple for now
    cleaned_data['volume'] = entry.get('volume')
    cleaned_data['issue'] = entry.get('number') # BibTeX often uses 'number' for issue
    cleaned_data['pages'] = entry.get('pages')

    return cleaned_data

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Parsing helper functions
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

# Helper to generate a QR code (with logo) as a Base64 data URL
def generate_qr_data_url(data_url: str) -> str:
    """Generate a Base64-encoded PNG data URL for a QR code with logo overlay."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert('RGBA')
    try:
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logo.png')
        logo = Image.open(logo_path).convert('RGBA')

        width, height = img.size
        logo_size = int(width * 0.25)
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
        pos = ((width - logo_size) // 2, (height - logo_size) // 2)
        mask = logo.split()[3] if len(logo.split()) == 4 else None
        img.paste(logo, pos, mask)
    except Exception as e:
        app.logger.error(f"Error adding logo to QR code: {e}")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{img_str}"

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    qr_image_url = None

    if request.method == 'POST':
        # Check if the user provided a Google Docs URL
        gdoc_url = request.form.get('gdoc_url', '').strip()
        
        if gdoc_url:
            # Validate that it's a Google Docs URL
            if 'docs.google.com' not in gdoc_url:
                error = 'Please provide a valid Google Docs URL'
                return render_template('index.html', error=error)
                
            # Generate unique ID and store the URL in the database
            ref_id = str(uuid.uuid4())
            
            # Create a special "gdoc" entry with just the URL
            gdoc_entry = [{
                'type': 'gdoc',
                'url': gdoc_url,
                'title': 'Google Document'
            }]
            
            # Save to database with 30-day expiration
            database.save_reference_list(ref_id, gdoc_entry, expires_days=30)
            
            # Generate URL for the reference list
            ref_list_url = url_for('show_references', ref_id=ref_id, _external=True)
            print(f"Google Doc Reference URL: {ref_list_url}")
            
            qr_image_url = generate_qr_data_url(ref_list_url)
            return render_template('index.html', error=error, qr_image_url=qr_image_url)
                
        # Check if the post request has the file part
        if 'file' not in request.files:
            error = 'No file part'
            return render_template('index.html', error=error)
        
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            error = 'No selected file or Google Docs URL provided'
            return render_template('index.html', error=error)

        if file and allowed_file(file.filename):
            try:
                file_content_bytes = file.read()
                file_extension = file.filename.rsplit('.', 1)[1].lower()

                # Dispatch parsing based on file extension
                parser_map = {
                    'bib': parse_bibtex_bytes,
                    'rdf': parse_rdf_bytes,
                    'ris': parse_ris_bytes,
                    'xml': parse_endnote_xml_bytes
                }
                parser = parser_map.get(file_extension)
                if not parser:
                    allowed_ext_str = ", ".join(f".{ext}" for ext in sorted(ALLOWED_EXTENSIONS))
                    error = f'Invalid file type. Please upload a {allowed_ext_str} file.'
                    return render_template('index.html', error=error)
                # Parse entries, catching specific failures for RDF
                parsed_entries = parser(file_content_bytes)
                if file_extension == 'rdf' and not parsed_entries:
                    error = 'Failed to parse RDF file or no entries found.'
                    return render_template('index.html', error=error)

                # --- Common Processing Logic --- 
                if not parsed_entries:
                    # This catches empty bib files too
                    error = 'No valid entries found in the file.'
                    return render_template('index.html', error=error)

                # Generate unique ID and store data
                ref_id = str(uuid.uuid4())
                
                # Save references to database (with optional 30-day expiration)
                database.save_reference_list(ref_id, parsed_entries, expires_days=30)
                
                # Generate URL for the reference list
                # Use _external=True to get the absolute URL needed for the QR code
                ref_list_url = url_for('show_references', ref_id=ref_id, _external=True)
                print(f"Reference List URL: {ref_list_url}") # Print the full URL

                qr_image_url = generate_qr_data_url(ref_list_url)

            # Catch potential parsing errors more broadly
            except Exception as e:
                # Check if the error likely comes from bibtexparser
                if "bibtexparser" in str(e).lower() or type(e).__module__.startswith('bibtexparser'):
                     error = f"Error parsing BibTeX file: {e}" 
                else:
                    # Catch other unexpected errors
                    error = f"An unexpected error occurred: {e}"
        else:
            # Get allowed extensions for the error message
            allowed_ext_str = ", ".join(f".{ext}" for ext in sorted(list(ALLOWED_EXTENSIONS)))
            error = f'Invalid file type or missing file. Please upload a {allowed_ext_str} file.'

    return render_template('index.html', error=error, qr_image_url=qr_image_url)

@app.route('/refs/<ref_id>')
def show_references(ref_id):
    entries = database.get_reference_list(ref_id)
    if not entries:
        abort(404, description="Reference list not found or expired.")

    # Check if this is a Google Docs entry
    if len(entries) == 1 and entries[0].get('type') == 'gdoc':
        gdoc_url = entries[0].get('url')
        gdoc_title = entries[0].get('title', 'Google Document')
        
        # Create a simple HTML page with a redirect to the Google Doc
        html_redirect = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Redirecting to Google Document</title>
    <meta http-equiv="refresh" content="3; URL={html.escape(gdoc_url)}" />
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 600px;
            margin: 100px auto;
            padding: 20px;
            text-align: center;
            color: #333;
        }}
        h1 {{
            color: #2c3e50;
        }}
        .redirect-message {{
            margin: 30px 0;
            font-size: 18px;
        }}
        .manual-link {{
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background-color: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 5px;
        }}
        .manual-link:hover {{
            background-color: #2980b9;
        }}
    </style>
</head>
<body>
    <h1>Google Document Reference</h1>
    <div class="redirect-message">
        Redirecting you to: <strong>{html.escape(gdoc_title)}</strong>
    </div>
    <p>If you are not redirected automatically, click the link below:</p>
    <a class="manual-link" href="{html.escape(gdoc_url)}" target="_blank">Open Google Document</a>
</body>
</html>"""
        return html_redirect

    # --- Start HTML Generation (inspired by generate_report.py) --- 
    html_report = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reference List</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 20px auto; /* Added top/bottom margin */
            padding: 20px;
            color: #333;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        .reference {
            margin-bottom: 20px;
            padding: 15px;
            border-radius: 5px;
            background-color: #f9f9f9;
            border-left: 4px solid #3498db;
        }
        .authors {
            font-weight: bold;
        }
        .title {
            /* font-style: italic;  Removed italic style for title */
            margin-top: 5px; /* Added margin */
        }
        .publication-info {
             margin-top: 5px; /* Added margin */
             font-style: italic; /* Apply italic to journal/booktitle */
             color: #555; /* Slightly darker color */
        }
        .doi a {
            color: #3498db;
            text-decoration: none;
        }
        .doi a:hover {
            text-decoration: underline;
        }
        .doi, .date {
            margin-top: 5px; /* Added margin */
        }
        .date {
            color: #7f8c8d;
            font-size: 0.9em; /* Slightly smaller date */
        }
        .no-doi {
            color: #e74c3c;
            font-style: italic;
             margin-top: 5px; /* Added margin */
            font-size: 0.9em; /* Slightly smaller */
        }
    </style>
</head>
<body>
    <h1>Reference List</h1>
    <div id="references">
"""

    # Process and add each entry
    for entry in entries:
        # Clean and structure the data using the helper function
        cleaned_data = clean_and_structure_entry(entry)
        
        # Get potentially None values
        journal_val = cleaned_data.get('journal')
        volume_val = cleaned_data.get('volume')
        issue_val = cleaned_data.get('issue')
        pages_val = cleaned_data.get('pages')
        doi = cleaned_data.get('doi') # Keep URL raw for href

        # Escape data for HTML safety, handling None
        authors_esc = html.escape(cleaned_data.get('authors_formatted', 'N/A'))
        title_esc = html.escape(cleaned_data.get('title', 'N/A'))
        date_published_esc = html.escape(cleaned_data.get('date_published', 'N/A'))
        journal_esc = html.escape(journal_val if journal_val is not None else '')
        volume_esc = html.escape(volume_val if volume_val is not None else '')
        issue_esc = html.escape(issue_val if issue_val is not None else '')
        pages_esc = html.escape(pages_val if pages_val is not None else '')

        # Build publication string (Journal, Vol(Issue), Pages)
        pub_info_parts = []
        if journal_esc:
            pub_info_parts.append(journal_esc)
            if volume_esc:
                vol_issue = volume_esc
                if issue_esc:
                    vol_issue += f"({issue_esc})"
                pub_info_parts.append(vol_issue)
            if pages_esc:
                 pub_info_parts.append(f"pp. {pages_esc}") # Add pp. prefix
        pub_info_str = ", ".join(pub_info_parts)

        # Create HTML for this reference
        html_report += "<div class=\"reference\">\n"
        html_report += f"    <div class=\"authors\">{authors_esc} ({cleaned_data.get('year', '')})</div>\n" # Add year next to authors
        html_report += f"    <div class=\"title\">{title_esc}</div>\n"
        
        # Add publication info if available
        if pub_info_str:
            html_report += f"    <div class=\"publication-info\">{pub_info_str}</div>\n"

        # Add DOI link or message
        if doi:
            doi_esc = html.escape(doi)
            html_report += f"    <div class=\"doi\">DOI: <a href=\"{doi_esc}\" target=\"_blank\">{doi_esc}</a></div>\n"
        else:
            html_report += "    <div class=\"no-doi\">No DOI available</div>\n"
        
        # Optionally add date published if different from year (or always show?)
        # html_report += f"    <div class=\"date\">Date Info: {date_published_esc}</div>\n"
        html_report += "</div>\n"

    # Add the footer
    html_report += """
    </div>
</body>
</html>"""

    return html_report

# --- RDF Parsing Helper --- 

def parse_rdf_file(rdf_content_string):
    """Parses RDF/XML content and extracts bibliographic data.
    Args:
        rdf_content_string (str): The RDF file content as a string.
    Returns:
        list: A list of dictionaries, each representing a reference entry,
              mapped to keys compatible with the BibTeX processing path 
              (e.g., 'title', 'author', 'doi', 'year', 'journal', 'volume', 'number', 'pages').
              Returns an empty list if parsing fails or no entries are found.
    """
    entries = []
    try:
        namespaces = {
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'dc': 'http://purl.org/dc/elements/1.1/',
            'bib': 'http://purl.org/net/biblio#',
            'foaf': 'http://xmlns.com/foaf/0.1/',
            'prism': 'http://prismstandard.org/namespaces/1.2/basic/',
            'dcterms': 'http://purl.org/dc/terms/'
        }
        
        root = ET.fromstring(rdf_content_string)
        
        # --- Pass 1: Extract Journal DOIs --- 
        journal_dois = {}
        for journal in root.findall('.//bib:Journal', namespaces):
            journal_id = journal.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')
            if not journal_id:
                continue
            for identifier in journal.findall('./dc:identifier', namespaces):
                 identifier_text = identifier.text if identifier is not None else None
                 if identifier_text:
                      match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', identifier_text, re.IGNORECASE)
                      if match:
                          journal_dois[journal_id] = match.group(1)
                          break # Found DOI for this journal
                          
        # --- Pass 2: Process Items (Articles, Books, etc.) --- 
        item_types = ['.//bib:Article', './/bib:BookSection', './/bib:Book', './/bib:Report']
        
        for item_type in item_types:
            for item in root.findall(item_type, namespaces):
                entry = {}

                # --- Title --- 
                title_elem = item.find('./dc:title', namespaces)
                if title_elem is not None and title_elem.text:
                    entry['title'] = title_elem.text
                else:
                    continue # Skip entries without a title

                # --- Authors --- 
                authors_list = []
                # Look for authors within bib:authors sequence
                for author_elem in item.findall('./bib:authors/rdf:Seq/rdf:li/foaf:Person', namespaces):
                    surname = author_elem.find('./foaf:surname', namespaces)
                    given_name = author_elem.find('./foaf:givenName', namespaces)
                    if surname is not None and surname.text:
                        name = surname.text
                        if given_name is not None and given_name.text:
                            name = f"{surname.text}, {given_name.text}"
                        authors_list.append(name)
                # Also check dc:creator for simpler cases
                if not authors_list:
                     creator_elem = item.find('./dc:creator', namespaces)
                     if creator_elem is not None and creator_elem.text:
                         authors_list = [a.strip() for a in creator_elem.text.split(';')]
                entry['author'] = ' and '.join(authors_list) if authors_list else None

                # --- DOI --- 
                doi = None
                # Attempt 1: Check associated journal DOI (from Pass 1)
                part_of = item.find('./dcterms:isPartOf', namespaces)
                if part_of is not None:
                    journal_id_ref = part_of.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource')
                    if journal_id_ref in journal_dois:
                        doi = journal_dois[journal_id_ref]
                
                # Attempt 2: If no journal DOI, check dc:identifier in item
                if not doi:
                    for identifier in item.findall('.//dc:identifier', namespaces):
                        identifier_text = identifier.text if identifier is not None else None
                        if identifier_text:
                            identifier_text = identifier_text.strip()
                            if identifier_text:
                                match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', identifier_text, re.IGNORECASE)
                                if match:
                                    doi = match.group(1)
                                    break # Found DOI
                
                # Attempt 3: If still no DOI, check rdf:about attribute
                if not doi:
                    about_attr = item.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')
                    if about_attr:
                        match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', about_attr, re.IGNORECASE)
                        if match:
                             doi = match.group(1)
                             
                entry['doi'] = doi

                # --- Date / Year --- 
                date_elem = item.find('./dc:date', namespaces)
                if date_elem is not None and date_elem.text:
                    entry['date_published'] = date_elem.text.strip()
                    year_match = re.search(r'(\d{4})', date_elem.text)
                    entry['year'] = year_match.group(1) if year_match else date_elem.text
                else:
                     entry['date_published'] = None
                     entry['year'] = None

                # --- Journal / Publication Info --- 
                journal_title = None
                volume = None
                issue = None
                part_of_journal = item.find('./dcterms:isPartOf', namespaces) # Reuse variable name for clarity
                if part_of_journal is not None:
                    journal_elem = part_of_journal.find('./bib:Journal', namespaces) 
                    if journal_elem is None:
                        journal_elem = part_of_journal.find('./bib:Book', namespaces)
                    if journal_elem is not None:
                        title_elem = journal_elem.find('./dc:title', namespaces)
                        if title_elem is not None and title_elem.text:
                            journal_title = title_elem.text
                        vol_elem = journal_elem.find('./prism:volume', namespaces)
                        if vol_elem is not None and vol_elem.text:
                             volume = vol_elem.text
                        issue_elem = journal_elem.find('./prism:number', namespaces)
                        if issue_elem is not None and issue_elem.text:
                            issue = issue_elem.text
                entry['journal'] = journal_title
                entry['volume'] = volume
                entry['number'] = issue

                # --- Pages --- 
                pages_elem = item.find('./bib:pages', namespaces)
                if pages_elem is not None and pages_elem.text:
                    entry['pages'] = pages_elem.text
                else:
                    entry['pages'] = None

                entries.append(entry)
                
    except ET.ParseError as e:
        print(f"Error parsing RDF file: {e}") 
        return [] 
    except Exception as e:
        print(f"Unexpected error during RDF processing: {e}")
        return []
        
    return entries

@app.route('/maintenance/cleanup', methods=['GET'])
def cleanup_expired_references():
    """Clean up expired reference lists. This route can be called by a scheduled task (e.g., cron job)."""
    if request.args.get('key') != app.config.get('MAINTENANCE_KEY'):
        abort(403, description="Invalid maintenance key")
        
    # Delete expired references and count how many were removed
    count = database.delete_expired_references()
    
    return f"Cleaned up {count} expired reference lists", 200

@app.route('/admin/stats', methods=['GET'])
def database_stats():
    """View database statistics. Secured with the same maintenance key."""
    if request.args.get('key') != app.config.get('MAINTENANCE_KEY'):
        abort(403, description="Invalid maintenance key")
    
    # Get statistics about reference lists
    from database import ReferenceList, db
    
    # Count all reference lists
    total_count = ReferenceList.query.count()
    
    # Count active reference lists (not expired)
    now = datetime.datetime.utcnow()
    active_count = ReferenceList.query.filter(
        db.or_(
            ReferenceList.expires_at.is_(None),
            ReferenceList.expires_at > now
        )
    ).count()
    
    # Count expired reference lists
    expired_count = ReferenceList.query.filter(
        ReferenceList.expires_at.isnot(None),
        ReferenceList.expires_at <= now
    ).count()
    
    # Get newest 5 reference lists
    newest = ReferenceList.query.order_by(
        ReferenceList.created_at.desc()
    ).limit(5).all()
    
    newest_info = []
    for ref in newest:
        entries = json.loads(ref.entries)
        newest_info.append({
            'id': ref.id,
            'created_at': ref.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'expires_at': ref.expires_at.strftime('%Y-%m-%d %H:%M:%S') if ref.expires_at else 'Never',
            'entries_count': len(entries)
        })
    
    # Format as HTML for easy viewing
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Database Statistics</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto; }}
            h1, h2 {{ color: #2c3e50; }}
            .stats {{ margin-bottom: 30px; }}
            .stat-item {{ font-size: 18px; margin-bottom: 10px; }}
            .ref-list {{ border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; border-radius: 5px; }}
            .ref-list:hover {{ background-color: #f9f9f9; }}
        </style>
    </head>
    <body>
        <h1>Database Statistics</h1>
        
        <div class="stats">
            <div class="stat-item"><strong>Total Reference Lists:</strong> {total_count}</div>
            <div class="stat-item"><strong>Active Reference Lists:</strong> {active_count}</div>
            <div class="stat-item"><strong>Expired Reference Lists:</strong> {expired_count}</div>
        </div>
        
        <h2>Newest Reference Lists</h2>
        <div id="newest">
    """
    
    for ref in newest_info:
        html += f"""
            <div class="ref-list">
                <div><strong>ID:</strong> {ref['id']}</div>
                <div><strong>Created:</strong> {ref['created_at']}</div>
                <div><strong>Expires:</strong> {ref['expires_at']}</div>
                <div><strong>Entries:</strong> {ref['entries_count']}</div>
                <div><a href="{url_for('show_references', ref_id=ref['id'])}" target="_blank">View References</a></div>
            </div>
        """
    
    html += """
        </div>
        
        <div style="margin-top: 30px;">
            <a href="/maintenance/cleanup?key={}" style="color: #e74c3c; text-decoration: none; font-weight: bold; margin-right: 20px;">
                Clean Up Expired References
            </a>
            
            <a href="/admin/delete-all?key={}" style="color: #e74c3c; text-decoration: none; font-weight: bold; border: 1px solid #e74c3c; padding: 5px 10px; border-radius: 4px;">
                DELETE ALL REFERENCES
            </a>
        </div>
    </body>
    </html>
    """.format(request.args.get('key', ''), request.args.get('key', ''))
    
    return html

@app.route('/admin/delete-all', methods=['GET'])
def confirm_delete_all():
    """Show confirmation page for deleting all references"""
    if request.args.get('key') != app.config.get('MAINTENANCE_KEY'):
        abort(403, description="Invalid maintenance key")
    
    # Get count of references for confirmation
    from database import ReferenceList
    total_count = ReferenceList.query.count()
    
    # Generate confirmation HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Delete All References</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto; }}
            h1 {{ color: #2c3e50; }}
            .warning {{ color: #e74c3c; font-weight: bold; }}
            .count {{ font-size: 24px; margin: 20px 0; }}
            .button-container {{ margin: 30px 0; }}
            .delete-button {{ background-color: #e74c3c; color: white; padding: 10px 20px; 
                            border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }}
            .cancel-button {{ background-color: #7f8c8d; color: white; padding: 10px 20px; 
                           border: none; border-radius: 5px; cursor: pointer; margin-left: 10px; font-size: 16px; }}
        </style>
    </head>
    <body>
        <h1>Delete All References</h1>
        
        <p class="warning">WARNING: This action cannot be undone!</p>
        
        <div class="count">
            You are about to delete <strong>{total_count}</strong> reference lists from the database.
        </div>
        
        <div class="button-container">
            <form method="POST" action="/admin/delete-all/confirm?key={request.args.get('key')}">
                <button type="submit" class="delete-button">Yes, Delete ALL References</button>
                <a href="/admin/stats?key={request.args.get('key')}" class="cancel-button">Cancel</a>
            </form>
        </div>
    </body>
    </html>
    """
    
    return html

@app.route('/admin/delete-all/confirm', methods=['POST'])
def delete_all_references():
    """Handle deletion of all references"""
    if request.args.get('key') != app.config.get('MAINTENANCE_KEY'):
        abort(403, description="Invalid maintenance key")
    
    # Delete all references
    count = database.delete_all_references()
    
    # Show success message
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>References Deleted</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto; }}
            h1 {{ color: #2c3e50; }}
            .success {{ color: #27ae60; font-weight: bold; font-size: 18px; }}
            .back-button {{ background-color: #3498db; color: white; padding: 10px 20px; 
                         border: none; border-radius: 5px; cursor: pointer; text-decoration: none; 
                         display: inline-block; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <h1>References Deleted</h1>
        
        <p class="success">Successfully deleted {count} reference lists from the database.</p>
        
        <a href="/admin/stats?key={request.args.get('key')}" class="back-button">Back to Statistics</a>
    </body>
    </html>
    """
    
    return html

if __name__ == '__main__':
    # Important: Use host='0.0.0.0' to make the server accessible
    # externally if running inside a container or VM.
    # For local development, '127.0.0.1' (the default) is usually fine.
    
    app.run(debug=True, host='0.0.0.0') 