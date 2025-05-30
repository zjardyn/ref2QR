import uuid
import html
from flask import Blueprint, request, render_template, url_for, abort, redirect, flash, send_file, session, current_app
from utils.parsers import parse_bibtex_bytes, parse_rdf_bytes, parse_ris_bytes, parse_endnote_xml_bytes
from utils.cleaning import clean_and_structure_entry
from utils.qr_generator import generate_qr_data_url
import database
import random
from extensions import twilio_client, mail
from flask_mail import Message
from config import Config
from database import save_verified_email
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
import re

main_bp = Blueprint('main', __name__)

# Define fields that are essential for storage and HTML generation
ALLOWED_FIELDS_FOR_STORAGE = {
    # Core identifiers and types
    'ID',               # BibTeX key or internal ID from parser
    'ENTRYTYPE',        # From BibTeX, e.g., 'article', 'book'
    'type',             # Can be from parser (like ENTRYTYPE) OR app-specific ('gdoc', 'file')

    # For title
    'title',

    # For authors/editors
    'author', 'authors', # Raw author string/list
    'editor', 'editors', # Raw editor string/list

    # For date/year information
    'year',
    'month',
    'day',
    'date',             # If a full date string is provided by parser

    # For publication venue (journal/book)
    'journal', 'journaltitle',
    'booktitle',
    'series',           # e.g., for reports or book series
    'publisher',        # For books/proceedings

    # For volume, issue, pages
    'volume',
    'number',           # Often used for issue number
    'issue',
    'pages',
    'articleno',        # Article number, can substitute for pages in some journal styles

    # For DOI and URL
    'doi',
    'url',              # Generic URL, or specific for GDoc

    # App-specific fields added in routes/main.py or needed for app logic
    'filename',         # For pending file logic (app-specific)
    'email',            # Added by the app for user tracking (app-specific)
    # 'note' is intentionally omitted to save space, unless critical parsing info is there
}

def _filter_entry_for_storage(entry_dict):
    """Filters an entry dictionary to keep only allowed fields for storage."""
    if not isinstance(entry_dict, dict): # Ensure it's a dictionary
        return entry_dict # Or handle error appropriately
    return {k: v for k, v in entry_dict.items() if k in ALLOWED_FIELDS_FOR_STORAGE}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def is_valid_google_doc_url(url):
    """Validate if a URL is a valid Google Docs URL.
    
    Args:
        url (str): The URL to validate
        
    Returns:
        bool: True if the URL is a valid Google Docs URL, False otherwise
    """
    # Basic pattern for Google Docs URLs
    pattern = r'^https://docs\.google\.com/document/d/[a-zA-Z0-9_-]+(/edit)?(/.*)?$'
    return bool(re.match(pattern, url))

@main_bp.route('/', methods=['GET', 'POST'])
def index():
    MAX_QR_CODES_PER_SESSION = 15
    generated_qr_codes = session.get('generated_qr_codes', 0)
    pending_id   = session.get('pending_file_id')
    pending_name = session.get('pending_filename')
    pending_gdoc_url_from_session = session.get('pending_gdoc_url')

    # 1) Limit check
    if generated_qr_codes >= MAX_QR_CODES_PER_SESSION:
        flash(f"You've reached the max of {MAX_QR_CODES_PER_SESSION} QR codes this session.", 'warning')
        session.clear()
        return redirect(url_for('main.index'))

    error = None
    qr_image_url = None
    gdoc_url_to_populate = None # For pre-filling the GDoc URL field

    # Check for and handle pending GDoc URL from session if user is verified
    if pending_gdoc_url_from_session and (session.get('email_verified') or session.get('phone_verified')):
        session.pop('_flashes', None) # Clear previous flashes
        if not is_valid_google_doc_url(pending_gdoc_url_from_session):
            flash('A previously submitted Google Docs URL was invalid and has been cleared.', 'error')
        else:
            gdoc_url_to_populate = pending_gdoc_url_from_session
        session.pop('pending_gdoc_url', None)

    if request.method == 'POST':
        # 2) "Finish pending" button (for files)
        if request.form.get('pending_file_id'):
            file_id = request.form['pending_file_id']
            pending_filename = session.get('pending_filename') # Get the original filename

            if not file_id or not pending_filename:
                session.pop('_flashes', None) # Clear before flashing new error
                flash("Error processing pending file. Please try uploading again.", 'error')
                session.pop('pending_file_id', None)
                session.pop('pending_filename', None)
                return redirect(url_for('main.index'))

            upload_folder = current_app.config['UPLOAD_FOLDER']
            temp_path = os.path.join(upload_folder, file_id)

            if not os.path.exists(temp_path):
                session.pop('_flashes', None) # Clear before flashing new error
                flash("Pending file not found. It might have expired or been removed. Please try uploading again.", 'error')
                session.pop('pending_file_id', None)
                session.pop('pending_filename', None)
                return redirect(url_for('main.index'))

            try:
                with open(temp_path, 'rb') as f:
                    file_content = f.read()

                parsed_entries = []
                filename_lower = pending_filename.lower()

                if filename_lower.endswith('.bib'):
                    parsed_entries = parse_bibtex_bytes(file_content)
                elif filename_lower.endswith('.rdf'):
                    parsed_entries = parse_rdf_bytes(file_content)
                elif filename_lower.endswith('.ris'):
                    parsed_entries = parse_ris_bytes(file_content)
                elif filename_lower.endswith('.xml'): # Assuming EndNote XML
                    parsed_entries = parse_endnote_xml_bytes(file_content)
                else:
                    error = "Unsupported file type for pending file."
                    flash(error)
                    session.pop('pending_file_id', None)
                    session.pop('pending_filename', None)
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    return render_template('index.html', error=error, qr_image_url=None, gdoc_url_to_populate=gdoc_url_to_populate, pending_filename=pending_name, pending_file_id=pending_id)

                if len(parsed_entries) > 30:
                    error = f"File contains {len(parsed_entries)} references. Maximum allowed is 30 references per file."
                    flash(error, 'error')
                    session.pop('pending_file_id', None)
                    session.pop('pending_filename', None)
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    return render_template('index.html', error=error, qr_image_url=None, gdoc_url_to_populate=gdoc_url_to_populate, pending_filename=pending_name, pending_file_id=pending_id)

                session_email = session.get('email')
                processed_entries_for_storage = []
                for entry_item in parsed_entries:
                    if session_email and isinstance(entry_item, dict):
                        entry_item['email'] = session_email
                    processed_entries_for_storage.append(_filter_entry_for_storage(entry_item))
                
                database.save_reference_list(file_id, processed_entries_for_storage, expires_days=30)

            except Exception as e:
                current_app.logger.error(f"Error processing pending file {file_id}: {e}")
                session.pop('_flashes', None) # Clear before flashing new error
                flash(f"An error occurred while processing your pending file: {str(e)[:100]}", 'error') # Truncate long errors for flash
                session.pop('pending_file_id', None)
                session.pop('pending_filename', None)
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return redirect(url_for('main.index'))

            ref_list_url = url_for('main.show_references', ref_id=file_id, _external=True)
            qr_image_url = generate_qr_data_url(ref_list_url)
            session['generated_qr_codes'] = generated_qr_codes + 1
            session.pop('pending_file_id', None)
            session.pop('pending_filename', None)
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            session.pop('_flashes', None) # Clear other flashes
            flash(f'QR code generated for your file: {pending_filename}', 'success') # Use original pending_filename here
            return render_template('index.html', error=None, qr_image_url=qr_image_url, gdoc_url_to_populate=gdoc_url_to_populate, pending_filename=None, pending_file_id=None)

        # 3) Not yet verified → stage file or GDoc URL
        elif not session.get('email_verified') and not session.get('phone_verified'):
            file = request.files.get('file')
            gdoc_url_unverified = request.form.get('gdoc_url', '').strip()

            if file and file.filename and allowed_file(file.filename):
                file_id = str(uuid.uuid4())
                filename = secure_filename(file.filename)
                temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_id)
                file.save(temp_path)
                session['pending_file_id']  = file_id
                session['pending_filename'] = filename
                flash('File saved. Please verify your email or phone to generate the QR code.', 'info')
                return redirect(url_for('main.verify'))
            elif gdoc_url_unverified and is_valid_google_doc_url(gdoc_url_unverified):
                session['pending_gdoc_url'] = gdoc_url_unverified
                flash('Google Doc URL saved. Please verify your email or phone to generate the QR code.', 'info')
                return redirect(url_for('main.verify'))
            elif gdoc_url_unverified: # Invalid GDoc URL submitted by unverified user
                error = "Invalid Google Docs URL. Please ensure it starts with 'https://docs.google.com/document/d/' and check for typos."
                session.pop('_flashes', None) # Clear any existing flashed messages
                return render_template(
                    'index.html',
                    error=error, 
                    qr_image_url=None,
                    pending_filename=pending_name, 
                    pending_file_id=pending_id,
                    gdoc_url_to_populate=None # Don't repopulate with the invalid URL
                )
            
            # If neither file nor GDoc URL was provided by unverified user
            flash('Please provide a file or a Google Doc URL, then verify your email or phone to continue.', 'warning')
            return redirect(url_for('main.verify'))

        # 4) Verified user: Process new GDoc submission or new file upload
        else:
            gdoc_url_submission = request.form.get('gdoc_url', '').strip()

            if gdoc_url_submission:
                if not is_valid_google_doc_url(gdoc_url_submission):
                    error = 'Please provide a valid Google Docs URL (e.g., https://docs.google.com/document/d/1234567890/edit)'
                    # Fall through to render template with error and gdoc_url_to_populate (which might be the invalid one or a previously valid one)
                else:
                    ref_id = str(uuid.uuid4())
                    session_email = session.get('email')
                    gdoc_db_entry_raw = [{'type': 'gdoc', 'url': gdoc_url_submission, 'title': 'Google Document', 'email': session_email}]
                    filtered_gdoc_entry = [_filter_entry_for_storage(entry) for entry in gdoc_db_entry_raw]
                    database.save_reference_list(ref_id, filtered_gdoc_entry, expires_days=30)
                    ref_list_url = url_for('main.show_references', ref_id=ref_id, _external=True)
                    qr_image_url = generate_qr_data_url(ref_list_url)
                    session['generated_qr_codes'] = generated_qr_codes + 1
                    return render_template('index.html', error=None, qr_image_url=qr_image_url, pending_filename=pending_name, pending_file_id=pending_id, gdoc_url_to_populate=None)

            elif 'file' in request.files:
                file = request.files['file']
                if file.filename == '':
                    if not gdoc_url_submission: # Only error if GDoc wasn't also provided
                        error = 'No selected file or Google Docs URL provided'
                elif file and allowed_file(file.filename):
                    try:
                        ref_id = str(uuid.uuid4())
                        session_email = session.get('email')
                        file_content = file.read()
                        file.seek(0)
                        parsed_entries = []
                        filename_lower = file.filename.lower()

                        if filename_lower.endswith('.bib'): parsed_entries = parse_bibtex_bytes(file_content)
                        elif filename_lower.endswith('.rdf'): parsed_entries = parse_rdf_bytes(file_content)
                        elif filename_lower.endswith('.ris'): parsed_entries = parse_ris_bytes(file_content)
                        elif filename_lower.endswith('.xml'): parsed_entries = parse_endnote_xml_bytes(file_content)
                        else: error = "Unsupported file type for parsing." # Should be caught by allowed_file

                        if not error and len(parsed_entries) > 30:
                            error = f"File contains {len(parsed_entries)} references. Maximum allowed is 30."
                        
                        if not error:
                            processed_entries_for_storage = []
                            for entry_item in parsed_entries:
                                if session_email and isinstance(entry_item, dict): entry_item['email'] = session_email
                                processed_entries_for_storage.append(_filter_entry_for_storage(entry_item))
                            database.save_reference_list(ref_id, processed_entries_for_storage, expires_days=30)
                            ref_list_url = url_for('main.show_references', ref_id=ref_id, _external=True)
                            qr_image_url = generate_qr_data_url(ref_list_url)
                            session['generated_qr_codes'] = generated_qr_codes + 1
                            flash(f'Successfully uploaded {file.filename}', 'success')
                            return render_template('index.html', error=None, qr_image_url=qr_image_url, pending_filename=pending_name, pending_file_id=pending_id, gdoc_url_to_populate=None)
                    except Exception as e:
                        current_app.logger.error(f"Error processing uploaded file: {e}")
                        error = f"An error occurred while processing the file: {str(e)[:100]}" # Truncate long errors
                # If file not allowed or other file error, error variable should be set, will fall through
            
            # If POST but no GDoc URL and no valid file submitted by a verified user
            elif not gdoc_url_submission and (not request.files.get('file') or request.files.get('file').filename == ''):
                 error = 'No selected file or Google Docs URL provided'


    # GET request or fall-through from POST if no action resulted in a direct render/redirect
    return render_template(
        'index.html',
        error=error,
        qr_image_url=qr_image_url,
        pending_filename=pending_name,
        pending_file_id=pending_id,
        gdoc_url_to_populate=gdoc_url_to_populate
    )

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
    <div id="references">
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


@main_bp.route('/verify', methods=['GET', 'POST'])
def verify():
    # If user is already verified, skip straight to index
    if session.get('email_verified') or session.get('phone_verified'):
        flash('You are already verified.', 'info')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        if email:
            code = generate_verification_code()
            session['email_code']    = code
            session['email_verified'] = False
            session['pending_email']  = email   # remember which addr

            send_verification_email(email, code)
            flash('Verification code sent to your email.', 'info')
            return redirect(url_for('main.verify_code'))

        elif phone:
            code = generate_verification_code()
            session['phone_code']    = code
            session['phone_verified'] = False

            send_verification_sms(phone, code)
            flash('Verification code sent to your phone.', 'info')
            return redirect(url_for('main.verify_code'))

    return render_template('verify.html')

@main_bp.route('/verify_code', methods=['GET', 'POST'])
def verify_code():
    if request.method == 'POST':
        entered_code = request.form.get('code', '').strip()

        # Email code matches
        if entered_code == session.get('email_code'):
            session['email_verified'] = True
            flash('Email successfully verified!', 'success')

            # Save to DB once, if not already there
            email = session.pop('pending_email', None)
            if email:
                session['email'] = email  # Store the verified email in the session
                save_verified_email(email)

        # Phone code matches
        elif entered_code == session.get('phone_code'):
            session['phone_verified'] = True
            flash('Phone number successfully verified!', 'success')
        else:
            flash('Invalid verification code.', 'error')

        return redirect(url_for('main.index'))

    return render_template('verify_code.html')

def generate_verification_code():
    return str(random.randint(100000, 999999))


def send_verification_email(email, code):
    msg = Message('Verification Code', recipients=[email])
    msg.body = f'Your verification code is {code}'
    mail.send(msg)


def send_verification_sms(phone, verification_code):
    # Check if the Twilio client is properly initialized
    if current_app.twilio_client is None:
        print("Twilio client is not initialized.")
        return

    try:
        message = current_app.twilio_client.messages.create(
            body=f"Your verification code is: {verification_code}",
            from_=Config.TWILIO_PHONE_NUMBER,  # Your Twilio phone number
            to=phone
        )
        print("SMS sent successfully")
    except Exception as e:
        print(f"Error sending SMS: {e}")