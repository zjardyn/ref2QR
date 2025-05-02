import uuid
import html
from flask import Blueprint, request, render_template, url_for, abort, redirect, flash, send_file
from utils.parsers import parse_bibtex_bytes, parse_rdf_bytes, parse_ris_bytes, parse_endnote_xml_bytes
from utils.cleaning import clean_and_structure_entry
from utils.qr_generator import generate_qr_data_url
import database
from config import ALLOWED_EXTENSIONS
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta

main_bp = Blueprint('main', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main_bp.route('/', methods=['GET', 'POST'])
def index():
    error = None
    qr_image_url = None
    if request.method == 'POST':
        gdoc_url = request.form.get('gdoc_url', '').strip()
        if gdoc_url:
            if 'docs.google.com' not in gdoc_url:
                error = 'Please provide a valid Google Docs URL'
                return render_template('index.html', error=error)
            ref_id = str(uuid.uuid4())
            gdoc_entry = [{
                'type': 'gdoc',
                'url': gdoc_url,
                'title': 'Google Document'
            }]
            database.save_reference_list(ref_id, gdoc_entry, expires_days=30)
            ref_list_url = url_for('main.show_references', ref_id=ref_id, _external=True)
            print(f"Reference List URL: {ref_list_url}")
            qr_image_url = generate_qr_data_url(ref_list_url)
            return render_template('index.html', error=error, qr_image_url=qr_image_url)
        if 'file' not in request.files:
            error = 'No file part'
            return render_template('index.html', error=error)
        file = request.files['file']
        if file.filename == '':
            error = 'No selected file or Google Docs URL provided'
            return render_template('index.html', error=error)
        ALLOWED_EXTENSIONS = {'bib', 'rdf', 'ris', 'xml'}
        def allowed_file(filename):
            return '.' in filename and \
                   filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
        if file and allowed_file(file.filename):
            try:
                file_content_bytes = file.read()
                file_extension = file.filename.rsplit('.', 1)[1].lower()
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
                parsed_entries = parser(file_content_bytes)
                if file_extension == 'rdf' and not parsed_entries:
                    error = 'Failed to parse RDF file or no entries found.'
                    return render_template('index.html', error=error)
                if not parsed_entries:
                    error = 'No valid entries found in the file.'
                    return render_template('index.html', error=error)
                ref_id = str(uuid.uuid4())
                database.save_reference_list(ref_id, parsed_entries, expires_days=30)
                ref_list_url = url_for('main.show_references', ref_id=ref_id, _external=True)
                print(f"Reference List URL: {ref_list_url}")
                qr_image_url = generate_qr_data_url(ref_list_url)
            except Exception as e:
                if "bibtexparser" in str(e).lower() or type(e).__module__.startswith('bibtexparser'):
                     error = f"Error parsing BibTeX file: {e}" 
                else:
                    error = f"An unexpected error occurred: {e}"
        else:
            allowed_ext_str = ", ".join(f".{ext}" for ext in sorted(list(ALLOWED_EXTENSIONS)))
            error = f'Invalid file type or missing file. Please upload a {allowed_ext_str} file.'
    return render_template('index.html', error=error, qr_image_url=qr_image_url)

@main_bp.route('/refs/<ref_id>')
def show_references(ref_id):
    entries = database.get_reference_list(ref_id)
    if not entries:
        abort(404, description="Reference list not found or expired.")
    if len(entries) == 1 and entries[0].get('type') == 'gdoc':
        gdoc_url = entries[0].get('url')
        gdoc_title = entries[0].get('title', 'Google Document')
        html_redirect = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Redirecting to Google Document</title>
    <meta http-equiv=\"refresh\" content=\"3; URL={html.escape(gdoc_url)}\" />
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
    <div class=\"redirect-message\">
        Redirecting you to: <strong>{html.escape(gdoc_title)}</strong>
    </div>
    <p>If you are not redirected automatically, click the link below:</p>
    <a class=\"manual-link\" href=\"{html.escape(gdoc_url)}\" target=\"_blank\">Open Google Document</a>
</body>
</html>"""
        return html_redirect
    html_report = """<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Reference List</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 20px auto;
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
            margin-top: 5px;
        }
        .publication-info {
             margin-top: 5px;
             font-style: italic;
             color: #555;
        }
        .doi a {
            color: #3498db;
            text-decoration: none;
        }
        .doi a:hover {
            text-decoration: underline;
        }
        .doi, .date {
            margin-top: 5px;
        }
        .date {
            color: #7f8c8d;
            font-size: 0.9em;
        }
        .no-doi {
            color: #e74c3c;
            font-style: italic;
            margin-top: 5px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <h1>Reference List</h1>
    <div id=\"references\">
"""
    for entry in entries:
        cleaned_data = clean_and_structure_entry(entry)
        journal_val = cleaned_data.get('journal')
        volume_val = cleaned_data.get('volume')
        issue_val = cleaned_data.get('issue')
        pages_val = cleaned_data.get('pages')
        doi = cleaned_data.get('doi')
        authors_esc = html.escape(cleaned_data.get('authors_formatted', 'N/A'))
        title_esc = html.escape(cleaned_data.get('title', 'N/A'))
        date_published_esc = html.escape(cleaned_data.get('date_published', 'N/A'))
        journal_esc = html.escape(journal_val if journal_val is not None else '')
        volume_esc = html.escape(volume_val if volume_val is not None else '')
        issue_esc = html.escape(issue_val if issue_val is not None else '')
        pages_esc = html.escape(pages_val if pages_val is not None else '')
        pub_info_parts = []
        if journal_esc:
            pub_info_parts.append(journal_esc)
            if volume_esc:
                vol_issue = volume_esc
                if issue_esc:
                    vol_issue += f"({issue_esc})"
                pub_info_parts.append(vol_issue)
            if pages_esc:
                 pub_info_parts.append(f"pp. {pages_esc}")
        pub_info_str = ", ".join(pub_info_parts)
        html_report += "<div class=\"reference\">\n"
        html_report += f"    <div class=\"authors\">{authors_esc} ({cleaned_data.get('year', '')})</div>\n"
        html_report += f"    <div class=\"title\">{title_esc}</div>\n"
        if pub_info_str:
            html_report += f"    <div class=\"publication-info\">{pub_info_str}</div>\n"
        if doi:
            doi_esc = html.escape(doi)
            html_report += f"    <div class=\"doi\">DOI: <a href=\"{doi_esc}\" target=\"_blank\">{doi_esc}</a></div>\n"
        else:
            html_report += "    <div class=\"no-doi\">No DOI available</div>\n"
        html_report += "</div>\n"
    html_report += """
    </div>
    <div style=\"margin-top: 30px; text-align: center;\">
        <a href=\"/\" class=\"btn btn-primary\">Back to Home</a>
    </div>
</body>
</html>"""
    return html_report

@main_bp.route('/references/<ref_id>')
def view_references(ref_id):
    entries = database.get_reference_list(ref_id)
    if entries is None:
        flash('Reference list not found or has expired')
        return redirect(url_for('main.index'))
    return render_template('references.html', entries=entries)

@main_bp.route('/download/<ref_id>')
def download_references(ref_id):
    entries = database.get_reference_list(ref_id)
    if entries is None:
        flash('Reference list not found or has expired')
        return redirect(url_for('main.index'))
        
    # Create a temporary file with the references
    temp_file = f'temp_{ref_id}.txt'
    with open(temp_file, 'w') as f:
        for entry in entries:
            f.write(f"{entry}\n\n")
            
    return send_file(temp_file, as_attachment=True, download_name=f'references_{ref_id}.txt') 