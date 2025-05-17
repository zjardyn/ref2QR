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

main_bp = Blueprint('main', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


@main_bp.route('/', methods=['GET', 'POST'])
def index():
    MAX_QR_CODES_PER_SESSION = 15
    generated_qr_codes = session.get('generated_qr_codes', 0)
    pending_id   = session.get('pending_file_id')
    pending_name = session.get('pending_filename')

    # 1) Limit check
    if generated_qr_codes >= MAX_QR_CODES_PER_SESSION:
        flash(f'You’ve reached the max of {MAX_QR_CODES_PER_SESSION} QR codes this session.')
        session.clear()
        return redirect(url_for('main.index'))

    error = None
    qr_image_url = None

    if request.method == 'POST':

        # 2) “Finish pending” button
        if request.form.get('pending_file_id'):
            # 1) grab the ID straight from the form
            file_id = request.form['pending_file_id']
            if not file_id:
                return redirect(url_for('main.index'))

            # 2) persist your reference list so you can show it later
            #    (you probably want to store something real here—
            #     you can store an empty list or metadata if you just
            #     need a placeholder)
            example_entry = [{
                'type': 'file',
                'filename': session.get('pending_filename'),
                # if you saved additional metadata on disk, point to it here
            }]
            database.save_reference_list(file_id, example_entry, expires_days=30)

            # 3) build the external URL to your reference list
            ref_list_url = url_for('main.show_references',
                                   ref_id=file_id,
                                   _external=True)

            # 4) generate the QR code data URL
            qr_image_url = generate_qr_data_url(ref_list_url)

            # 5) increment your counter
            session['generated_qr_codes'] = generated_qr_codes + 1

            # 6) clean up both session keys and the temp file
            session.pop('pending_file_id', None)
            session.pop('pending_filename', None)
            upload_folder = current_app.config['UPLOAD_FOLDER']
            temp_path = os.path.join(upload_folder, file_id)
            if os.path.exists(temp_path):
                os.remove(temp_path)

            return render_template(
                'index.html',
                error=error,
                qr_image_url=qr_image_url
            )

        # 3) Not yet verified → stage file or redirect
        if not session.get('email_verified') and not session.get('phone_verified'):
            file = request.files.get('file')
            if file and file.filename and allowed_file(file.filename):
                # save temp file
                file_id = str(uuid.uuid4())
                filename = secure_filename(file.filename)
                temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_id)
                file.save(temp_path)

                session['pending_file_id']  = file_id
                session['pending_filename'] = filename

                flash('Please verify your email or phone to continue.')
                return redirect(url_for('main.verify'))

            flash('Please verify your email or phone number to upload files.')
            return redirect(url_for('main.verify'))

        # 4) Verified → handle Google‑Doc
        gdoc_url = request.form.get('gdoc_url', '').strip()
        if gdoc_url:
            if 'docs.google.com' not in gdoc_url:
                error = 'Please provide a valid Google Docs URL'
                return render_template('index.html', error=error)

            ref_id = str(uuid.uuid4())
            # … save & generate QR …
            ref_list_url = url_for('main.show_references', ref_id=ref_id, _external=True)
            qr_image_url = generate_qr_data_url(ref_list_url)
            session['generated_qr_codes'] = generated_qr_codes + 1

            return render_template('index.html', error=error, qr_image_url=qr_image_url)

        # 5) Verified → handle fresh file upload
        if 'file' not in request.files:
            error = 'No file part'
            return render_template('index.html', error=error)

        file = request.files['file']
        if file.filename == '':
            error = 'No selected file or Google Docs URL provided'
            return render_template('index.html', error=error)

        if file and allowed_file(file.filename):
            try:
                ref_id = str(uuid.uuid4())
                # … save reference list & generate QR …
                ref_list_url = url_for('main.show_references', ref_id=ref_id, _external=True)
                qr_image_url = generate_qr_data_url(ref_list_url)

                session['generated_qr_codes'] = generated_qr_codes + 1
                session['upload_count'] = session.get('upload_count', 0) + 1
                flash(f'Successfully uploaded {file.filename}')
                return render_template('index.html', error=error, qr_image_url=qr_image_url)

            except Exception as e:
                error = f"An error occurred: {e}"

    # GET or fall‑through
    return render_template(
        'index.html',
        error=error,
        qr_image_url=qr_image_url,
        pending_filename=pending_name,
        pending_file_id=pending_id
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


@main_bp.route('/verify', methods=['GET', 'POST'])
def verify():
    # If user is already verified, skip straight to index
    if session.get('email_verified') or session.get('phone_verified'):
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
            flash('Verification code sent to your email.')
            return redirect(url_for('main.verify_code'))

        elif phone:
            code = generate_verification_code()
            session['phone_code']    = code
            session['phone_verified'] = False

            send_verification_sms(phone, code)
            flash('Verification code sent to your phone.')
            return redirect(url_for('main.verify_code'))

    return render_template('verify.html')

@main_bp.route('/verify_code', methods=['GET', 'POST'])
def verify_code():
    if request.method == 'POST':
        entered_code = request.form.get('code', '').strip()

        # Email code matches
        if entered_code == session.get('email_code'):
            session['email_verified'] = True
            flash('Email successfully verified!')

            # Save to DB once, if not already there
            email = session.pop('pending_email', None)
            if email:
                save_verified_email(email)

        # Phone code matches
        elif entered_code == session.get('phone_code'):
            session['phone_verified'] = True
            flash('Phone number successfully verified!')
        else:
            flash('Invalid verification code.')

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