from flask_sqlalchemy import SQLAlchemy
import json
import datetime
import os

# Initialize SQLAlchemy without binding to an app yet
db = SQLAlchemy()

# Database models
class ReferenceList(db.Model):
    id = db.Column(db.String(36), primary_key=True)  # UUID as string
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)  # Optional expiration
    entries = db.Column(db.Text)  # JSON-serialized reference entries
    
    def __init__(self, id, entries, expires_at=None):
        self.id = id
        self.entries = json.dumps(entries)
        self.expires_at = expires_at
        
    def get_entries(self):
        return json.loads(self.entries)
    
    def is_expired(self):
        if self.expires_at is None:
            return False
        return datetime.datetime.utcnow() > self.expires_at

def init_app(app):
    """Initialize the database with the Flask app"""
    # Database configuration
    # For SQLite (development)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///references.db'
    # For PostgreSQL (production)
    # app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://user:password@localhost/references')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the app with the database
    db.init_app(app)
    
    # Create database tables
    with app.app_context():
        db.create_all()

def save_reference_list(ref_id, entries, expires_days=None):
    """Save a reference list to the database"""
    # Calculate expiration date if provided
    expires_at = None
    if expires_days:
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=expires_days)
        
    # Create and save the reference list
    reference_list = ReferenceList(id=ref_id, entries=entries, expires_at=expires_at)
    db.session.add(reference_list)
    db.session.commit()
    
def get_reference_list(ref_id):
    """Get a reference list from the database by ID"""
    reference_list = ReferenceList.query.get(ref_id)
    
    # Return None if not found or if expired
    if not reference_list or reference_list.is_expired():
        return None
        
    return reference_list.get_entries()
    
def delete_expired_references():
    """Delete all expired reference lists from the database"""
    now = datetime.datetime.utcnow()
    expired = ReferenceList.query.filter(
        ReferenceList.expires_at.isnot(None),
        ReferenceList.expires_at < now
    ).all()
    
    for ref in expired:
        db.session.delete(ref)
        
    db.session.commit()
    return len(expired)

def delete_all_references():
    """Delete all reference lists from the database"""
    count = ReferenceList.query.count()
    ReferenceList.query.delete()
    db.session.commit()
    return count 