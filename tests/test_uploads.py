import sys
import os
import glob
import pytest

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app

# Directory containing example files
EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), '../old')
FILE_TYPES = ['bib', 'rdf', 'ris', 'xml']

@pytest.mark.parametrize("file_path", [
    f for ext in FILE_TYPES for f in glob.glob(os.path.join(EXAMPLES_DIR, f'*.{ext}'))
])
def test_upload_file(file_path):
    with app.test_client() as client:
        filename = os.path.basename(file_path)
        ext = filename.split('.')[-1].lower()
        data = {
            'file': (open(file_path, 'rb'), filename)
        }
        response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200, f"Failed for {filename}"
        # Check for QR code image in the response (data URL)
        assert b'data:image/png;base64' in response.data, f"QR code not found in response for {filename}"

def test_google_doc_url():
    with app.test_client() as client:
        data = {
            'gdoc_url': 'https://docs.google.com/document/d/1A2B3C4D5E6F7G8H9I0J/edit'
        }
        response = client.post('/', data=data, follow_redirects=True)
        assert response.status_code == 200, "Failed to submit Google Doc URL"
        assert b'data:image/png;base64' in response.data, "QR code not found in response for Google Doc URL"

def test_fmg_poster_bib():
    """Test uploading FMG_POSTER.bib and check for QR code generation."""
    bib_path = os.path.join(EXAMPLES_DIR, 'FMG_POSTER.bib')
    assert os.path.exists(bib_path), "FMG_POSTER.bib does not exist in old/ directory."
    with app.test_client() as client:
        with open(bib_path, 'rb') as f:
            data = {'file': (f, 'FMG_POSTER.bib')}
            response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=True)
            assert response.status_code == 200, "Failed to upload FMG_POSTER.bib"
            assert b'data:image/png;base64' in response.data, "QR code not found in response for FMG_POSTER.bib" 