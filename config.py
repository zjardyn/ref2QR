import os

# Flask configuration
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Limit upload size to 16MB
MAINTENANCE_KEY = 'change_this_key_for_production'

# Allowed file extensions
ALLOWED_EXTENSIONS = {'bib', 'rdf', 'ris', 'xml'}

# Database configuration
DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///ref2qr.db') 