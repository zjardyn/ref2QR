from flask import Flask
from config import Config
from extensions import init_app, init_twilio
from database import db
from routes.main import main_bp

app = Flask(__name__)
app.config.from_object(Config)  # Load the config values

# Initialize the extensions
init_app(app)
init_twilio(app)

with app.app_context():
    db.create_all()

# Register blueprints
app.register_blueprint(main_bp)

if __name__ == '__main__':
    app.run(debug=True)