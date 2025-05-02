from flask import Flask
from routes.main import main_bp
import database

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # Limit upload size to 16MB
app.config['MAINTENANCE_KEY'] = 'change_this_key_for_production'

# Initialize database with our app
database.init_app(app)

app.register_blueprint(main_bp)

if __name__ == '__main__':
    # Important: Use host='0.0.0.0' to make the server accessible
    # externally if running inside a container or VM.
    # For local development, '127.0.0.1' (the default) is usually fine.
    
    app.run(debug=False, host='0.0.0.0') 