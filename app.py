from flask import Flask, g
from routes.main import main_bp
from routes.admin import admin_bp
from routes.auth import auth_bp
import database

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # Limit upload size to 16MB
app.config['MAINTENANCE_KEY'] = 'change_this_key_for_production'

# Initialize database with our app
database.init_app(app)

app.register_blueprint(main_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)

@app.context_processor
def inject_current_user():
    try:
        from flask_login import current_user
        return dict(current_user=current_user)
    except ImportError:
        class DummyUser:
            is_authenticated = False
            email = ""
        return dict(current_user=DummyUser())

if __name__ == '__main__':
    # Important: Use host='0.0.0.0' to make the server accessible
    # externally if running inside a container or VM.
    # For local development, '127.0.0.1' (the default) is usually fine.
    
    app.run(debug=False, host='0.0.0.0') 