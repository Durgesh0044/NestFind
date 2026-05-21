from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, current_user, login_required
from core.models import Broker
from core.extensions import db, mail
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Message
import re

auth_bp = Blueprint('auth', __name__)

s = URLSafeTimedSerializer('your-secret-key')

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        if getattr(current_user, 'role', 'broker') == 'broker':
            return redirect(url_for('admin.admin_dashboard'))
        else:
            return redirect(url_for('public.index'))
    
    if request.method == "POST":
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role', 'buyer')
        
        if not name or not email or not password or not confirm_password:
            return render_template("auth/signup.html", error="All fields are required")
        
        if password != confirm_password:
            return render_template("auth/signup.html", error="Passwords do not match")
        
        # Password complexity validation: 6-8 chars, letters and special characters
        # In signup route, replace the password validation with:
        # Password validation: at least 8 characters, with letter and special character
        if len(password) < 8:
            return render_template("auth/signup.html", error="Password must be at least 8 characters long")

        if not re.search(r"[a-zA-Z]", password):
            return render_template("auth/signup.html", error="Password must include at least one letter")

        if not re.search(r"[0-9]", password):
            return render_template("auth/signup.html", error="Password must include at least one number")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return render_template("auth/signup.html", error="Password must include at least one special character")
        
        existing_broker = Broker.query.filter_by(email=email).first()
        if existing_broker:
            return render_template("auth/signup.html", error="Email already registered")
        
        new_broker = Broker(name=name, email=email, phone=phone, role=role)
        new_broker.set_password(password)
        
        try:
            db.session.add(new_broker)
            db.session.commit()
            login_user(new_broker)
            if new_broker.role == 'broker':
                return redirect(url_for('admin.admin_dashboard'))
            else:
                return redirect(url_for('public.index'))
        except Exception as e:
            db.session.rollback()
            return render_template("auth/signup.html", error=f"Signup failed: {str(e)}")
            
    return render_template("auth/signup.html")


@auth_bp.route("/signin", methods=["GET", "POST"])
def signin():
    if current_user.is_authenticated:
        # Check for Super Admin first
        if current_user.is_super_admin:
            return redirect(url_for('superadmin.super_admin_dashboard'))
        elif getattr(current_user, 'role', 'broker') == 'broker':
            return redirect(url_for('admin.admin_dashboard'))
        else:
            return redirect(url_for('public.index'))
    
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        
        broker = Broker.query.filter_by(email=email).first()
        if broker and broker.check_password(password):
            login_user(broker)
            # Check role after login
            if broker.is_super_admin:
                return redirect(url_for('superadmin.super_admin_dashboard'))
            elif getattr(broker, 'role', 'broker') == 'broker':
                return redirect(url_for('admin.admin_dashboard'))
            else:
                return redirect(url_for('public.index'))
        else:
            return render_template("auth/signin.html", error="Invalid email or password")
            
    return render_template("auth/signin.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('public.index'))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        if getattr(current_user, 'role', 'broker') == 'broker':
            return redirect(url_for('admin.admin_dashboard'))
        else:
            return redirect(url_for('public.index'))
    
    if request.method == "POST":
        email = request.form.get('email')
        broker = Broker.query.filter_by(email=email).first()
        
        if broker:
            token = s.dumps(email, salt='password-reset-salt')
            reset_link = url_for('auth.reset_password', token=token, _external=True)
            
            print(f"\n🔐 PASSWORD RESET LINK FOR {email}:")
            print(f"👉 {reset_link}")
            
            try:
                # Create PLAIN TEXT email only (no HTML)
                msg = Message(
                    subject='Password Reset Request - NestFind',
                    sender='saniyatanyal1@gmail.com',
                    recipients=[email],
                    body=f"Hello {broker.name},\n\n"
                         f"Someone requested a password reset for your NestFind account.\n\n"
                         f"To reset your password, click the link below:\n\n"
                         f"{reset_link}\n\n"
                         f"This link will expire in 1 hour.\n\n"
                         f"If you did not request this, please ignore this email.\n\n"
                         f"Best regards,\n"
                         f"The NestFind Team"
                )
                mail.send(msg)
                print(f"✅ Email sent to {email}")
                return render_template("auth/forgot_password.html", 
                                       message=f"Password reset link has been sent to {email}")
            except Exception as e:
                print(f"❌ Email failed: {e}")
                return render_template("auth/forgot_password.html", 
                                       error=f"Failed to send email: {str(e)}")
        else:
            return render_template("auth/forgot_password.html", error="Email not found")
    
    # GET request - just show the form
    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('admin.admin_dashboard'))
    
    try:
        # Token valid for 1 hour (3600 seconds)
        email = s.loads(token, salt='password-reset-salt', max_age=3600)

    except:
        return render_template(
            "auth/forgot_password.html",
            error="The reset link is invalid or has expired."
        )
    
    if request.method == "POST":

        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            return render_template(
                "auth/reset_password.html",
                token=token,
                error="Passwords do not match"
            )
        
        # Password validation
        if len(password) < 8:
            return render_template(
                "auth/reset_password.html",
                token=token,
                error="Password must be at least 8 characters long"
            )

        if not re.search(r"[a-zA-Z]", password):
            return render_template(
                "auth/reset_password.html",
                token=token,
                error="Password must include at least one letter"
            )

        if not re.search(r"[0-9]", password):
            return render_template(
                "auth/reset_password.html",
                token=token,
                error="Password must include at least one number"
            )

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return render_template(
                "auth/reset_password.html",
                token=token,
                error="Password must include at least one special character"
            )
        
        broker = Broker.query.filter_by(email=email).first()

        if broker:
            broker.set_password(password)
            db.session.commit()

            flash(
                "Your password has been reset successfully. Please sign in.",
                "success"
            )

            return redirect(url_for('auth.signin'))

        else:
            return render_template(
                "auth/forgot_password.html",
                error="User not found"
            )
            
    return render_template("auth/reset_password.html", token=token)