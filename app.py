"""Flask application factory and configuration module.

This module initializes the Flask application, configures extensions,
and registers blueprints for the reference management system.
"""

from flask import Flask
from config import Config
import os
from extensions import init_app, init_twilio
from database import db
from routes.main import main_bp
from routes.admin import admin_bp
from routes.auth import auth_bp


def create_upload_folder(app):
    """Create the upload folder if it doesn't exist.
    
    Args:
        app: Flask application instance
    """
    upload_folder = os.path.join(app.root_path, 'uploads', 'temp')
    os.makedirs(upload_folder, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_folder


def init_db(app):
    """Initialize the database with all tables.
    
    Args:
        app: Flask application instance
    """
    with app.app_context():
        db.create_all()


def create_app():
    """Create and configure the Flask application.
    
    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    init_app(app)
    init_twilio(app)
    
    # Create upload folder
    create_upload_folder(app)
    
    # Initialize database
    init_db(app)

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')