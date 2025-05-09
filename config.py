import os
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables from .env file
load_dotenv()

class Config:
    # Flask configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Limit upload size to 16MB
    MAINTENANCE_KEY = os.getenv('MAINTENANCE_KEY', 'change_this_key_for_production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Allowed file extensions
    ALLOWED_EXTENSIONS = {'bib', 'rdf', 'ris', 'xml'}

    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://username:password@localhost:5432/mydatabase')

    # Email configuration
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')

    # Twilio configuration
    TWILIO_SID = os.getenv('TWILIO_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)

    # Secret key for sessions
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_secret_key')