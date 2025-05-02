from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models.user import User, UploadHistory
from flask_mail import Message
from extensions import db, mail
import os
import secrets

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if existing_user.is_verified:
                flash('Email already registered', 'error')
                return redirect(url_for('auth.register'))
            else:
                # Delete the unverified user to allow re-registration
                db.session.delete(existing_user)
                db.session.commit()
        
        user = User(email=email)
        user.set_password(password)
        user.verification_token = secrets.token_urlsafe(32)
        
        db.session.add(user)
        db.session.commit()
        
        # Send verification email
        send_verification_email(user)
        
        flash('Registration successful! Please check your email to verify your account.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_verified:
                flash('Please verify your email before logging in.', 'error')
                return redirect(url_for('auth.login'))
            login_user(user)
            return redirect(url_for('index'))
        
        flash('Invalid email or password', 'error')
        return redirect(url_for('auth.login'))
    
    return render_template('login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@auth.route('/verify/<token>')
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()
    if user:
        user.is_verified = True
        user.verification_token = None
        db.session.commit()
        flash('Email verified successfully! You can now log in.', 'success')
    else:
        flash('Invalid verification token.', 'error')
    return redirect(url_for('auth.login'))

def send_verification_email(user):
    token = user.verification_token
    verify_url = url_for('auth.verify_email', token=token, _external=True)
    msg = Message('Verify your email',
                  recipients=[user.email])
    msg.body = f'''To verify your email, visit the following link:
{verify_url}

If you did not make this request, please ignore this email.
'''
    mail.send(msg) 