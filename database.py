from flask_sqlalchemy import SQLAlchemy
import json
import datetime

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

class VerifiedEmail(db.Model):
    """A single row per e‑mail address that has successfully passed verification."""

    __tablename__ = "verified_emails"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(320), unique=True, nullable=False)
    verified_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)

def save_reference_list(ref_id, entries, expires_days=None):
    """Save a reference list to the database"""
    expires_at = None
    if expires_days:
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=expires_days)

    reference_list = ReferenceList(id=ref_id, entries=entries, expires_at=expires_at)
    db.session.add(reference_list)
    db.session.commit()

def get_reference_list(ref_id):
    """Get a reference list from the database by ID"""
    reference_list = ReferenceList.query.get(ref_id)
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

def get_database_stats():
    """Return statistics about the reference lists in the database."""
    now = datetime.datetime.utcnow()
    total_count = ReferenceList.query.count()
    active_count = ReferenceList.query.filter(
        (ReferenceList.expires_at.is_(None)) | (ReferenceList.expires_at > now)
    ).count()
    expired_count = ReferenceList.query.filter(
        ReferenceList.expires_at.isnot(None),
        ReferenceList.expires_at <= now
    ).count()
    newest = ReferenceList.query.order_by(
        ReferenceList.created_at.desc()
    ).limit(5).all()
    newest_info = []
    for ref in newest:
        entries = json.loads(ref.entries)
        newest_info.append({
            'id': ref.id,
            'created_at': ref.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'expires_at': ref.expires_at.strftime('%Y-%m-%d %H:%M:%S') if ref.expires_at else 'Never',
            'entries_count': len(entries)
        })
    return {
        'total_count': total_count,
        'active_count': active_count,
        'expired_count': expired_count,
        'newest_info': newest_info
    }

def save_verified_email(email: str):
    """Insert *email* into VerifiedEmail if it isn’t already there."""
    if not VerifiedEmail.query.filter_by(email=email).first():
        db.session.add(VerifiedEmail(email=email))
        db.session.commit()


def is_email_verified(email: str) -> bool:
    return VerifiedEmail.query.filter_by(email=email).first() is not None