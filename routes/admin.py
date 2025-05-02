from flask import Blueprint, render_template, redirect, url_for, request, abort
import database
from config import MAINTENANCE_KEY
import datetime

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/maintenance/cleanup', methods=['GET'])
def cleanup_expired_references():
    """Clean up expired references from the database."""
    # Check for maintenance key
    if request.args.get('key') != MAINTENANCE_KEY:
        abort(403)
        
    # Clean up references older than 30 days
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=30)
    database.cleanup_expired_references(cutoff_date)
    
    return "Cleanup completed successfully"

@admin_bp.route('/admin/stats', methods=['GET'])
def database_stats():
    """Display database statistics."""
    # Check for maintenance key
    if request.args.get('key') != MAINTENANCE_KEY:
        abort(403)
        
    stats = database.get_database_stats()
    return render_template('admin/stats.html', stats=stats)

@admin_bp.route('/admin/delete-all', methods=['GET'])
def confirm_delete_all():
    """Show confirmation page for deleting all references."""
    # Check for maintenance key
    if request.args.get('key') != MAINTENANCE_KEY:
        abort(403)
        
    return render_template('admin/confirm_delete.html')

@admin_bp.route('/admin/delete-all/confirm', methods=['POST'])
def delete_all_references():
    """Delete all references from the database."""
    # Check for maintenance key
    if request.form.get('key') != MAINTENANCE_KEY:
        abort(403)
        
    # Check for confirmation
    if request.form.get('confirm') != 'yes':
        return redirect(url_for('admin.confirm_delete_all', key=MAINTENANCE_KEY))
        
    # Delete all references
    database.delete_all_references()
    
    return "All references have been deleted" 