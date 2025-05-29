from flask import Blueprint, render_template, redirect, url_for, request, abort
import database
from config import Config
import datetime

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/maintenance/cleanup', methods=['GET'])
def cleanup_expired_references():
    """Clean up expired references from the database."""
    # Check for maintenance key
    if request.args.get('key') != Config.MAINTENANCE_KEY:
        abort(403)
        
    # Clean up references older than 30 days
    database.delete_expired_references()
    
    return "Cleanup completed successfully"

@admin_bp.route('/admin/stats', methods=['GET'])
def database_stats():
    """Display database statistics."""
    # Check for maintenance key
    if request.args.get('key') != Config.MAINTENANCE_KEY:
        abort(403)
        
    stats = database.get_database_stats()
    return render_template('admin/stats.html', stats=stats)

@admin_bp.route('/admin/delete-all', methods=['GET', 'POST'])
def confirm_delete_all():
    """Show confirmation page for deleting all references."""
    # Check for maintenance key
    if request.args.get('key') != Config.MAINTENANCE_KEY:
        abort(403)
    
    if request.method == 'POST':
        step = int(request.form.get('step', 1))
        if step == 1:
            return render_template('admin/confirm_delete.html', 
                                step=2, 
                                message="Are you really sure you want to delete these references?",
                                key=request.args.get('key'))
        elif step == 2:
            return render_template('admin/confirm_delete.html', 
                                step=3, 
                                message="This is your last chance. Are you absolutely certain?",
                                key=request.args.get('key'))
        elif step == 3:
            # Check password on final step
            password = request.form.get('password', '')
            if password != 'hehexd69':
                return render_template('admin/confirm_delete.html',
                                    step=3,
                                    message="This is your last chance. Are you absolutely certain?",
                                    key=request.args.get('key'),
                                    error="Incorrect password. Please try again.")
            count = database.delete_all_references()
            return f"Successfully deleted {count} reference lists from the database."
    
    return render_template('admin/confirm_delete.html', 
                         step=1, 
                         message="Are you sure you want to delete all references?",
                         key=request.args.get('key')) 