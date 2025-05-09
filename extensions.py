from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config
from twilio.rest import Client
from database import db
from flask import current_app

# Initialize the extensions
mail = Mail()
login_manager = LoginManager()
migrate = Migrate()

# Initialize email in your app initialization
def init_app(app):
    # Initialize all extensions here
    db.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

# Initialize the Twilio client as None globally
twilio_client = None

def init_twilio(app):
    if not hasattr(app, 'twilio_client'):  # Check if already initialized
        app.twilio_client = Client(Config.TWILIO_SID, Config.TWILIO_AUTH_TOKEN)
        print("Twilio client initialized successfully")