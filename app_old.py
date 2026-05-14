from flask import Flask, render_template, request, jsonify, send_from_directory, url_for, redirect, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from datetime import datetime
import os
import csv
import pandas as pd
from werkzeug.utils import secure_filename
import uuid
import json
import sys
import re
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import pdfplumber
import requests
import time

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates"),
)

# File upload configuration
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls', 'pdf'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database configuration with fallback to SQLite if PostgreSQL fails
try:
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    
    if all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
        DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        print(f"Using PostgreSQL database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    else:
        raise ValueError("Missing database environment variables")
        
except Exception as e:
    print(f"Warning: PostgreSQL configuration issue: {e}")
    print("Falling back to SQLite database for testing")
    DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'database.db')}"

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "nestfind_secret_key_123")

db = SQLAlchemy(app)

# Mail extension configuration
# Mapping user-provided names to Flask-Mail expected names
app.config['MAIL_SERVER'] = os.getenv('MAIL_HOST', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_ENCRYPTION', 'tls').lower() == 'tls'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

# Handle potentially quoted values from .env
from_address = os.getenv('MAIL_FROM_ADDRESS', os.getenv('MAIL_USERNAME', '')).strip('"').strip("'")
from_name = os.getenv('MAIL_FROM_NAME', 'NestFind').strip('"').strip("'")
app.config['MAIL_DEFAULT_SENDER'] = (from_name, from_address)

mail = Mail(app)

# Serializer for password reset tokens
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])


# Login Manager configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'signin'

@login_manager.user_loader
def load_user(user_id):
    return Broker.query.get(int(user_id))

# --- Database Models ---

class Broker(db.Model, UserMixin):
    __tablename__ = 'brokers'
    broker_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='broker')
    is_active = db.Column(db.Boolean, default=True)  # For blocking brokers
    is_super_admin = db.Column(db.Boolean, default=False)  # NEW: Super admin flag
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    properties = db.relationship('Property', backref='broker_info', lazy=True)
    uploaded_files = db.relationship('UploadedFile', backref='broker_info', lazy=True)
    activities = db.relationship('Activity', backref='broker_info', lazy=True)
    
    def get_id(self):
        return str(self.broker_id)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_admin(self):
        return self.is_super_admin or self.role == 'admin'
    

## User Favourite tables
class UserFavorite(db.Model):
    __tablename__ = 'user_favorites'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('brokers.broker_id'), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('Broker', backref='favorites')
    property = db.relationship('Property', backref='favorited_by')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'property_id', name='unique_user_property_favorite'),
    )

## and its required routes
# ========== FAVORITE PROPERTIES ROUTES ==========

@app.route("/api/favorites/toggle", methods=["POST"])
def toggle_favorite():
    """Toggle favorite status - Store in localStorage if not logged in"""
    try:
        data = request.get_json()
        property_id = data.get('property_id')
        
        if not property_id:
            return jsonify({'success': False, 'message': 'Property ID required'}), 400
        
        # Check if user is logged in
        if not current_user.is_authenticated:
            # Return success but indicate it's a client-side favorite
            return jsonify({
                'success': True, 
                'is_favorite': None,  # None means client-side only
                'message': 'Please login to save favorites permanently',
                'require_login': True
            })
        
        user_id = current_user.broker_id
        
        favorite = UserFavorite.query.filter_by(
            user_id=user_id,
            property_id=property_id
        ).first()
        
        if favorite:
            property_obj = Property.query.get(property_id)
            db.session.delete(favorite)
            db.session.commit()
            
            if property_obj:
                create_notification(
                    recipient_type='broker',
                    recipient_id=user_id,
                    notification_type='favorite_removed',
                    title=f"💔 Removed from Favorites",
                    message=f"'{property_obj.property}' removed from your favorites",
                    icon='💔',
                    link=f'/favorites'
                )
            
            return jsonify({
                'success': True, 
                'is_favorite': False,
                'message': 'Removed from favorites'
            })
        else:
            new_favorite = UserFavorite(
                user_id=user_id,
                property_id=property_id
            )
            db.session.add(new_favorite)
            db.session.commit()
            
            property_obj = Property.query.get(property_id)
            if property_obj:
                create_notification(
                    recipient_type='broker',
                    recipient_id=user_id,
                    notification_type='favorite_added',
                    title=f"❤️ Added to Favorites",
                    message=f"'{property_obj.property}' added to your favorites",
                    icon='❤️',
                    link=f'/favorites'
                )
            
            return jsonify({
                'success': True, 
                'is_favorite': True,
                'message': 'Added to favorites'
            })
            
    except Exception as e:
        print(f"Error toggling favorite: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    

@app.route("/api/favorites/check", methods=["GET"])
@login_required
def check_favorite():
    """Check if property is favorited by current user"""
    try:
        property_id = request.args.get('property_id')
        if not property_id:
            return jsonify({'success': False, 'message': 'Property ID required'}), 400
        
        favorite = UserFavorite.query.filter_by(
            user_id=current_user.broker_id,
            property_id=property_id
        ).first()
        
        return jsonify({
            'success': True,
            'is_favorite': favorite is not None
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/api/favorites/list", methods=["GET"])
@login_required
def get_favorites():
    """Get all favorited properties for current user"""
    try:
        favorites = UserFavorite.query.filter_by(
            user_id=current_user.broker_id
        ).order_by(UserFavorite.created_at.desc()).all()
        
        properties = []
        for fav in favorites:
            prop = fav.property
            if prop and prop.status == 'Active':
                # Get image URL
                default_images = {
                    'Apartment': "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600",
                    'Flat': "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600",
                    'Villa': "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600",
                    'Commercial': "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600",
                    'Plot': "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=600",
                    'Studio': "https://images.unsplash.com/photo-1520637836862-4d197d17c155?w=600"
                }
                image, _ = build_image_urls(prop.image, prop.category, default_images)
                
                properties.append({
                    'id': prop.id,
                    'property': prop.property,
                    'location': prop.location or 'Tricity Region',
                    'price': prop.price,
                    'bedrooms': prop.bedrooms or 'N/A',
                    'area': prop.area or 'N/A',
                    'category': prop.category,
                    'image': image,
                    'type': prop.type,
                    'favorited_at': fav.created_at.isoformat() if fav.created_at else None
                })
        
        return jsonify({
            'success': True,
            'properties': properties,
            'count': len(properties)
        })
    except Exception as e:
        print(f"Error getting favorites: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/user-favorites")
@login_required
def user_favorites():
    """Public user favorites page"""
    # Only for buyers/regular users, not brokers
    if current_user.role == 'broker':
        return redirect(url_for('favorites_page'))
    
    return render_template('user_favorites.html',
        user_name=current_user.name,
        user_initials="".join([n[0] for n in current_user.name.split()[:2]]).upper()
    )



@app.route("/favorites")
@login_required
def favorites_page():
    """Favorites page for users"""
    if getattr(current_user, 'role', 'broker') != 'broker':
        flash('Please login as broker to access favorites', 'warning')
        return redirect(url_for('signin'))
    
    return render_template('favorites.html',
        admin_name=current_user.name,
        admin_initials="".join([n[0] for n in current_user.name.split()[:2]]).upper()
    )


@app.route("/api/favorites/remove", methods=["POST"])
@login_required
def remove_favorite():
    """Remove multiple favorites at once"""
    try:
        data = request.get_json()
        property_ids = data.get('property_ids', [])
        
        if not property_ids:
            return jsonify({'success': False, 'message': 'No properties selected'}), 400
        
        deleted_count = 0
        for property_id in property_ids:
            favorite = UserFavorite.query.filter_by(
                user_id=current_user.broker_id,
                property_id=property_id
            ).first()
            if favorite:
                db.session.delete(favorite)
                deleted_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Removed {deleted_count} properties from favorites'
        })
    except Exception as e:
        print(f"Error removing favorites: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500



@app.route("/super-admin")
@login_required
def super_admin_dashboard():
    """Super Admin Dashboard - Full System Control"""
    if not current_user.is_super_admin:
        flash('Access Denied. Super Admin privileges required.', 'error')
        return redirect(url_for('super_admin_login'))
    
    # Statistics
    total_brokers = Broker.query.filter_by(role='broker').count()
    active_brokers = Broker.query.filter_by(role='broker', is_active=True).count()
    blocked_brokers = Broker.query.filter_by(role='broker', is_active=False).count()
    total_properties = Property.query.count()
    active_properties = Property.query.filter_by(status='Active').count()
    total_leads = Lead.query.count()
    new_leads = Lead.query.filter_by(status='New').count()
    total_users = User.query.count()
    
    # Recent brokers
    recent_brokers = Broker.query.filter(
    Broker.role == 'broker',
    Broker.is_super_admin == False  # Exclude Super Admin
    ).order_by(Broker.created_at.desc()).limit(10).all()
    
    # Recent properties
    recent_properties = Property.query.order_by(Property.created_at.desc()).limit(10).all()
    
    # Property trend (last 7 days)
    from datetime import datetime, timedelta
    property_trend = []
    for i in range(7, 0, -1):
        date = datetime.utcnow() - timedelta(days=i)
        count = Property.query.filter(
            Property.created_at >= date,
            Property.created_at < date + timedelta(days=1)
        ).count()
        property_trend.append({
            'date': date.strftime('%b %d'),
            'count': count
        })
    
    return render_template('superadmin/dashboard.html',
        total_brokers=total_brokers,
        active_brokers=active_brokers,
        blocked_brokers=blocked_brokers,
        total_properties=total_properties,
        active_properties=active_properties,
        total_leads=total_leads,
        new_leads=new_leads,
        total_users=total_users,
        recent_brokers=recent_brokers,
        recent_properties=recent_properties,
        property_trend=property_trend,
        admin_name=current_user.name,
        admin_initials="".join([n[0] for n in current_user.name.split()[:2]]).upper()
    )


@app.route("/super-admin-login", methods=["GET", "POST"])
def super_admin_login():
    """Separate login page for Super Admin only"""
    
    # If already logged in as super admin, go to dashboard
    if current_user.is_authenticated and current_user.is_super_admin:
        return redirect(url_for('super_admin_dashboard'))
    
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        
        broker = Broker.query.filter_by(email=email).first()
        
        # Check if broker exists and is SUPER ADMIN
        if broker and broker.check_password(password) and broker.is_super_admin:
            login_user(broker)
            return redirect(url_for('super_admin_dashboard'))
        else:
            return render_template("super_admin/login.html", error="Invalid super admin credentials")
    
    return render_template("super_admin/login.html")


# ========== SUPER ADMIN MANAGEMENT ROUTES ==========

@app.route("/super-admin/brokers")
@login_required
def super_admin_brokers():
    """Super Admin - View all brokers"""
    if not current_user.is_super_admin:
        flash('Access Denied.', 'error')
        return redirect(url_for('super_admin_login'))
    
    brokers = Broker.query.filter(
        Broker.role == 'broker',
        Broker.is_super_admin == False
    ).order_by(Broker.created_at.desc()).all()
    
    return render_template('superadmin/brokers.html',
        brokers=brokers,
        admin_name=current_user.name,
        admin_initials="".join([n[0] for n in current_user.name.split()[:2]]).upper()
    )


@app.route("/super-admin/properties")
@login_required
def super_admin_properties():
    """Super Admin - View all properties across platform"""
    if not current_user.is_super_admin:
        flash('Access Denied.', 'error')
        return redirect(url_for('super_admin_login'))
    
    properties = Property.query.order_by(Property.created_at.desc()).all()
    
    return render_template('superadmin/properties.html',
        properties=properties,
        admin_name=current_user.name,
        admin_initials="".join([n[0] for n in current_user.name.split()[:2]]).upper()
    )


@app.route("/super-admin/leads")
@login_required
def super_admin_leads():
    """Super Admin - View all leads across platform"""
    if not current_user.is_super_admin:
        flash('Access Denied.', 'error')
        return redirect(url_for('super_admin_login'))
    
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    
    # Calculate time ago for each lead
    for lead in leads:
        time_diff = datetime.utcnow() - lead.created_at
        if time_diff.days > 0:
            lead.time_ago = f"{time_diff.days} days ago"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            lead.time_ago = f"{hours} hours ago"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            lead.time_ago = f"{minutes} minutes ago"
        else:
            lead.time_ago = "Just now"
    
    return render_template('superadmin/leads.html',
        leads=leads,
        admin_name=current_user.name,
        admin_initials="".join([n[0] for n in current_user.name.split()[:2]]).upper()
    )


@app.route("/super-admin/activities")
@login_required
def super_admin_activities():
    """Super Admin - View all activity logs"""
    if not current_user.is_super_admin:
        flash('Access Denied.', 'error')
        return redirect(url_for('super_admin_login'))
    
    activities = Activity.query.order_by(Activity.created_at.desc()).limit(100).all()
    
    # Calculate time ago
    for act in activities:
        time_diff = datetime.utcnow() - act.created_at
        if time_diff.days > 0:
            act.time_ago = f"{time_diff.days} days ago"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            act.time_ago = f"{hours} hours ago"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            act.time_ago = f"{minutes} minutes ago"
        else:
            act.time_ago = "Just now"
    
    return render_template('superadmin/activities.html',
        activities=activities,
        admin_name=current_user.name,
        admin_initials="".join([n[0] for n in current_user.name.split()[:2]]).upper()
    )


@app.route("/super-admin/broker/toggle/<int:broker_id>", methods=["POST"])
@login_required
def super_admin_toggle_broker(broker_id):
    """Super Admin - Activate/Block a broker"""
    if not current_user.is_super_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    broker = Broker.query.get_or_404(broker_id)
    broker.is_active = not broker.is_active
    db.session.commit()
    
    return jsonify({'success': True, 'is_active': broker.is_active})


@app.route("/super-admin/property/delete/<int:property_id>", methods=["DELETE"])
@login_required
def super_admin_delete_property(property_id):
    """Super Admin - Delete any property"""
    if not current_user.is_super_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    property_obj = Property.query.get_or_404(property_id)
    db.session.delete(property_obj)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Property deleted successfully'})


# Test route
@app.route("/test")
def test_route():
    return jsonify({'message': 'Test route works'})

# API routes
@app.route("/api/property/<property_id>", methods=["GET"])
def get_public_property(property_id):
    """Get a single property by ID for public access"""
    try:
        property_id = int(property_id)
        property_obj = Property.query.get_or_404(property_id)
        
        # Block if not Active
        if property_obj.status != 'Active':
            # Still allow if it's the owner previewing (optional, but keep simple for now)
            pass 
        
        
        # Get default image if no image is set
        default_images = {
            'Apartment': "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600",
            'Flat': "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600",
            'Villa': "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600",
            'Commercial': "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600",
            'Plot': "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=600",
            'Studio': "https://images.unsplash.com/photo-1520637836862-4d197d17c155?w=600"
        }
        
        image, all_images = build_image_urls(property_obj.image, property_obj.category, default_images)
        
        # Parse price to get numeric value for sorting
        price_numeric = 0
        price_display = property_obj.price or 'Price on request'
        
        # Try to extract numeric price
        import re
        price_match = re.search(r'[\d,]+(?:\.\d+)?', str(property_obj.price).replace('₹', '').replace(',', ''))
        if price_match:
            try:
                price_numeric = float(price_match.group().replace(',', ''))
                # Convert lakhs/crores if needed
                if 'L' in str(property_obj.price).upper():
                    price_numeric *= 100000
                elif 'Cr' in str(property_obj.price).upper():
                    price_numeric *= 10000000
            except:
                pass
        
        return jsonify({
            'id': property_obj.id,
            'property': property_obj.property,
            'location': property_obj.location,
            'type': property_obj.type,
            'price': price_display,
            'price_numeric': price_numeric,
            'area': property_obj.area,
            'bedrooms': property_obj.bedrooms,
            'category': property_obj.category,
            'status': property_obj.status,
            'agent': property_obj.agent,
            'broker_name': property_obj.broker_info.name if property_obj.broker_info else 'NestFind Agent',
            'broker_phone': property_obj.broker_info.phone if property_obj.broker_info else '+91 00000 00000',
            'image': image,
            'all_images': all_images,
            'created_at': property_obj.created_at.isoformat() if property_obj.created_at else None
        })
    except Exception as e:
        print(f"Error getting property {property_id}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# Example Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    looking_for = db.Column(db.String(100))
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Property(db.Model):
    __tablename__ = 'properties'
    id = db.Column(db.Integer, primary_key=True)
    property = db.Column(db.String(255))
    location = db.Column(db.String(255))
    type = db.Column(db.String(100))
    price = db.Column(db.String(100))
    area = db.Column(db.String(50))
    bedrooms = db.Column(db.String(20))
    category = db.Column(db.String(100))
    status = db.Column(db.String(50), default='Active', server_default='Active')
    agent = db.Column(db.String(255))
    image = db.Column(db.String(500))
    brochure = db.Column(db.String(500))
    broker_id = db.Column(db.Integer, db.ForeignKey('brokers.broker_id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # ADD THESE TWO LINES:
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)


class UploadedFile(db.Model):
    __tablename__ = 'uploaded_files'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=True)
    file_type = db.Column(db.String(20), nullable=True)
    file_size = db.Column(db.String(50), nullable=True)
    rows_count = db.Column(db.Integer, nullable=True)
    property = db.Column(db.String(255), nullable=True)
    type = db.Column(db.String(100), nullable=True)
    price = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='pending')
    agent = db.Column(db.String(255), nullable=True)
    broker_id = db.Column(db.Integer, db.ForeignKey('brokers.broker_id'), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    icon = db.Column(db.String(10))
    message = db.Column(db.String(500))
    # time_ago = db.Column(db.String(50))
    broker_id = db.Column(db.Integer, db.ForeignKey('brokers.broker_id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'))
    property_name = db.Column(db.String(255))
    broker_id = db.Column(db.Integer, db.ForeignKey('brokers.broker_id'))
    message = db.Column(db.Text)
    interest_level = db.Column(db.String(20), default='New')
    status = db.Column(db.String(20), default='New')
    source = db.Column(db.String(50), default='Contact Form')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    contacted_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text)
    
    # Relationships
    property = db.relationship('Property', backref='leads')
    broker = db.relationship('Broker', backref='leads')

def parse_price_to_number(price_str):
    """Convert price string to numeric value for comparison"""
    if not price_str:
        return 0
    
    price_str = str(price_str).lower().replace('₹', '').replace(',', '').strip()
    
    import re
    price_match = re.search(r'[\d,]+(?:\.\d+)?', price_str)
    if not price_match:
        return 0
    
    try:
        price_num = float(price_match.group().replace(',', ''))
        
        if 'lakh' in price_str or ('l' in price_str and 'lakh' not in price_str and 'cr' not in price_str):
            price_num *= 100000
        elif 'cr' in price_str:
            price_num *= 10000000
        elif 'k' in price_str or '/mo' in price_str:
            price_num *= 1000
        
        return price_num
    except:
        return 0
    


def landing_page_context():
    """Demo content for the landing page until CMS/DB-backed content exists."""
    
    # Load apartments from CSV
    apartments = []
    try:
        # Load featured apartments from the properties database
        default_images = {
            'Apartment': "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600",
            'Flat': "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600",
            'Villa': "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600",
            'Commercial': "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600",
            'Plot': "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=600",
            'Studio': "https://images.unsplash.com/photo-1520637836862-4d197d17c155?w=600"
        }
        default_location = 'Tricity Region'

        # Only show Active properties on homepage
        properties = Property.query.filter_by(status='Active').order_by(Property.created_at.desc()).limit(6).all()
        for idx, prop in enumerate(properties):
            prop_name = prop.property or 'Untitled Property'
            prop_type = prop.type or 'For Sale'
            category = prop.category or 'Apartment'
            price = prop.price or 'Price on request'
            area = prop.area or 'N/A'
            bedrooms = prop.bedrooms or 'N/A'

            # Try to derive beds and baths from bedrooms value
            beds = 1
            baths = 1
            sqft = area if area and area != 'N/A' else '1,200 sqft'
            import re
            bhk_match = re.search(r'(\d+)\s*BHK', bedrooms, re.IGNORECASE)
            if bhk_match:
                beds = int(bhk_match.group(1))
                baths = beds
                sqft_estimates = {1: '650', 2: '1,100', 3: '1,450', 4: '2,200'}
                sqft = f"{sqft_estimates.get(beds, '1,200')} sqft"
            elif bedrooms.lower().startswith('studio'):
                beds = 0
                baths = 1
                sqft = sqft if sqft != 'N/A' else '650 sqft'

            badge_class = 'badge-rent' if 'rent' in prop_type.lower() else ''
            featured = idx < 2
            image, all_images = build_image_urls(prop.image, category, default_images)

            price_suffix = '/mo' if 'rent' in prop_type.lower() else ''

            apartments.append({
                'id': prop.id,
                'image': image,
                'images': all_images,
                'badge': prop_type,
                'badge_class': badge_class,
                'featured': featured,
                'price': price,
                'price_suffix': price_suffix,
                'name': prop_name,
                'location': prop.location or default_location,
                'beds': beds,
                'baths': baths,
                'sqft': sqft,
                'broker_name': prop.broker_info.name if prop.broker_info else 'NestFind Agent',
                'broker_phone': prop.broker_info.phone if prop.broker_info else '+91 00000 00000'
            })
    except Exception as e:
        print(f"Error loading apartments from CSV: {e}")
        # Fallback to hardcoded data
        apartments = [
            {
                "image": "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600",
                "badge": "For Sale",
                "badge_class": "",
                "featured": False,
                "price": "₹85 Lakh",
                "price_suffix": "",
                "name": "Skyline Heights, 3BHK",
                "location": "Sector 17, Chandigarh",
                "beds": 3,
                "baths": 2,
                "sqft": "1,450 sqft",
            },
            {
                "image": "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600",
                "badge": "For Rent",
                "badge_class": "badge-rent",
                "featured": True,
                "price": "₹35,000",
                "price_suffix": "/mo",
                "name": "Azure Tower, 2BHK",
                "location": "Mohali, Phase 8",
                "beds": 2,
                "baths": 2,
                "sqft": "1,100 sqft",
            },
            {
                "image": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600",
                "badge": "For Sale",
                "badge_class": "",
                "featured": False,
                "price": "₹1.2 Cr",
                "price_suffix": "",
                "name": "Emerald Residency, 4BHK",
                "location": "Panchkula, Sector 5",
                "beds": 4,
                "baths": 3,
                "sqft": "2,200 sqft",
            },
        ]
    
    return {
        "hero_description": (
            'Discover handpicked apartments & luxury residences'
            '<br class="d-none d-md-block"/> in the most sought-after locations.'
        ),
        "year": datetime.now().year,
        "gallery": [
            {
                "image": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=900",
                "title": "Modern Villa",
            },
            {
                "image": "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=600",
                "title": "City Apartment",
            },
            {
                "image": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=600",
                "title": "Luxury Suite",
            },
            {
                "image": "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=600",
                "title": "Premium Kitchen",
            },
            {
                "image": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=600",
                "title": "Cosy Living Room",
            },
        ],
        "apartments": apartments,
        "testimonials": [
            {
                "message": "NestFind made our home search incredibly smooth. We found our dream apartment within 2 weeks!",
                "name": "Ananya Rao",
                "location": "Chandigarh",
                "initials": "AR",
                "featured": False,
            },
            {
                "message": "Exceptional service and genuine guidance. The team helped us navigate every legal formality with ease.",
                "name": "Rajiv Kapoor",
                "location": "Mohali",
                "initials": "RK",
                "featured": True,
            },
            {
                "message": "Highly professional team with a wide inventory. Found the perfect 4BHK for our family in Panchkula.",
                "name": "Priya Singh",
                "location": "Panchkula",
                "initials": "PS",
                "featured": False,
            },
        ],
    }




@app.route("/property/<int:property_id>")
def property_detail(property_id):
    """Public property detail page - shareable link for customers"""
    try:
        property_obj = Property.query.get_or_404(property_id)
        
        # Only show Active properties to public
        if property_obj.status != 'Active':
            flash('This property is no longer available.', 'warning')
            return redirect(url_for('index'))
        
        # Get default images
        default_images = {
            'Apartment': "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600",
            'Flat': "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600",
            'Villa': "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600",
            'Commercial': "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600",
            'Plot': "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=600",
            'Studio': "https://images.unsplash.com/photo-1520637836862-4d197d17c155?w=600"
        }
        
        # Get image URLs
        image, all_images = build_image_urls(property_obj.image, property_obj.category, default_images)
        
        # Parse bedrooms for display
        bedrooms_display = property_obj.bedrooms or 'N/A'
        beds = 1
        if bedrooms_display != 'N/A':
            import re
            bhk_match = re.search(r'(\d+)\s*BHK', bedrooms_display, re.IGNORECASE)
            if bhk_match:
                beds = int(bhk_match.group(1))
        
        # Create share message for WhatsApp/SMS
        share_text = f"Check out this property: {property_obj.property}\n📍 {property_obj.location or 'Tricity Region'}\n💰 {property_obj.price}\n🏠 {bedrooms_display}\n📐 {property_obj.area or 'N/A'}\n\nView details: {request.url}"
        
        encoded_text = share_text.replace(' ', '%20').replace('\n', '%0A')
        whatsapp_url = f"https://wa.me/?text={encoded_text}"
        sms_url = f"sms:?body={encoded_text}"
        
        return render_template('property_detail.html',
            property=property_obj,
            image=image,
            all_images=all_images,
            beds=beds,
            whatsapp_url=whatsapp_url,
            sms_url=sms_url
        )
        
    except Exception as e:
        print(f"Error loading property detail: {e}")
        flash('Property not found.', 'error')
        return redirect(url_for('index'))

## get_listings_change    
def get_listings_change(broker_id):
    """Calculate percentage change in listings from last month"""
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    this_month_start = datetime(now.year, now.month, 1, 0, 0, 0)
    last_month_start = datetime(now.year - (1 if now.month == 1 else 0), 
                                now.month - 1 if now.month > 1 else 12, 
                                1, 0, 0, 0)
    
    this_month_count = Property.query.filter(
        Property.broker_id == broker_id,
        Property.status != 'Deleted',
        Property.created_at >= this_month_start
    ).count()
    
    last_month_count = Property.query.filter(
        Property.broker_id == broker_id,
        Property.status != 'Deleted',
        Property.created_at >= last_month_start,
        Property.created_at < this_month_start
    ).count()
    
    if last_month_count > 0:
        change_percent = ((this_month_count - last_month_count) / last_month_count * 100)
        if change_percent > 0:
            return f'▲ {change_percent:.0f}% this month'
        elif change_percent < 0:
            return f'▼ {abs(change_percent):.0f}% this month'
        else:
            return '0% this month'
    elif this_month_count > 0:
        return f'▲ +{this_month_count} new this month'
    else:
        return '0 new this month'



def get_admin_dashboard_data(broker_id=None):
    """Prepare all data needed for the admin dashboard with REAL dynamic chart data"""
    
    if not broker_id:
        # Fallback for empty/new broker
        return {
            'chart_data': {
                'weekly_labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                'weekly_sale': [0, 0, 0, 0, 0, 0, 0],
                'weekly_rent': [0, 0, 0, 0, 0, 0, 0],
                'monthly_labels': [],
                'monthly_sale': [],
                'monthly_rent': [],
                'yearly_labels': [str(datetime.now().year)],
                'yearly_sale': [0],
                'yearly_rent': [0],
                'avg_price': '₹0',
                'days_on_market': '0 days',
                'conversion_rate': '0%',
                'total_listings': 0,
                'active_listings': 0
            },
            'stats': {
                'total_listings': '0',
                'total_sales_value': '₹0',
                'active_leads': '0',
                'files_uploaded': '0',
                'listings_change': '0 this month',
                'sales_change': '0 vs last month',
                'leads_change': '0 new today',
                'files_change': '0 pending review'
            },
            'recent_activities': [],
            'recent_files': [],
            'recent_listings': [],
            'recent_leads': [],
            'total_listings': 0,
            'file_count': 0,
            'leads_count': 0,
            'new_leads_count': 0,
            'admin_initials': '??',
            'admin_name': 'New Broker',
            'admin_role': 'Broker',
            'page_title': 'Dashboard Overview'
        }

    # Fetch broker info
    broker = Broker.query.get(broker_id)
    admin_name = broker.name if broker else "Broker"
    initials = "".join([n[0] for n in admin_name.split()[:2]]).upper()

    # Real statistics
    total_listings = Property.query.filter_by(broker_id=broker_id).filter(Property.status != 'Deleted').count()
    total_files = UploadedFile.query.filter_by(broker_id=broker_id).count()
    total_activities = Activity.query.filter_by(broker_id=broker_id).count()
    
        # ========== REAL STATISTICS FOR DASHBOARD CARDS ==========
    
    # 1. Total Listings (already have)
    total_listings = Property.query.filter_by(broker_id=broker_id).filter(Property.status != 'Deleted').count()
    
    # 2. TOTAL SALES VALUE (Sum of all SOLD properties)
    sold_properties = Property.query.filter_by(broker_id=broker_id, status='Sold').all()
    total_sales_value = 0
    for prop in sold_properties:
        price_num = parse_price_to_number(prop.price)
        total_sales_value += price_num
    
    # Format sales value for display
    if total_sales_value >= 10000000:  # Crores
        sales_value_display = f'₹{total_sales_value/10000000:.1f}Cr'
    elif total_sales_value >= 100000:  # Lakhs
        sales_value_display = f'₹{total_sales_value/100000:.0f}L'
    else:
        sales_value_display = f'₹{total_sales_value:,.0f}'
    
    # Calculate sales change from last month
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    last_month = now - timedelta(days=30)
    last_month_sales = 0
    for prop in sold_properties:
        if prop.created_at and prop.created_at >= last_month:
            price_num = parse_price_to_number(prop.price)
            last_month_sales += price_num
    
    if last_month_sales > 0:
        sales_change_percent = ((total_sales_value - last_month_sales) / last_month_sales * 100)
        if sales_change_percent > 0:
            sales_change = f'▲ {sales_change_percent:.0f}% vs last month'
        elif sales_change_percent < 0:
            sales_change = f'▼ {abs(sales_change_percent):.0f}% vs last month'
        else:
            sales_change = '0% vs last month'
    else:
        sales_change = '0% vs last month'
    
    # 3. ACTIVE LEADS (Leads that are New, Contacted, or Interested - not Lost/Converted)
    active_leads_count = Lead.query.filter_by(broker_id=broker_id).filter(
        Lead.status.in_(['New', 'Contacted', 'Interested'])
    ).count()
    
    # New leads today
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
    new_leads_today = Lead.query.filter_by(broker_id=broker_id, status='New').filter(
        Lead.created_at >= today_start
    ).count()
    
    if new_leads_today > 0:
        leads_change = f'▲ {new_leads_today} new today'
    else:
        leads_change = '0 new today'
    
    # 4. FILES UPLOADED (already have total_files)
    total_files = UploadedFile.query.filter_by(broker_id=broker_id).count()
    pending_files = UploadedFile.query.filter_by(broker_id=broker_id, status='pending').count()
    
    if pending_files > 0:
        files_change = f'{pending_files} pending review'
    else:
        files_change = f'{total_files} processed'
    
    # 5. LISTINGS CHANGE (new listings this month vs last month)
    this_month_start = datetime(now.year, now.month, 1, 0, 0, 0)
    last_month_start = datetime(now.year - (1 if now.month == 1 else 0), 
                                now.month - 1 if now.month > 1 else 12, 
                                1, 0, 0, 0)
    
    this_month_listings = Property.query.filter(
        Property.broker_id == broker_id,
        Property.status != 'Deleted',
        Property.created_at >= this_month_start
    ).count()
    
    last_month_listings = Property.query.filter(
        Property.broker_id == broker_id,
        Property.status != 'Deleted',
        Property.created_at >= last_month_start,
        Property.created_at < this_month_start
    ).count()
    
    if last_month_listings > 0:
        listings_change_percent = ((this_month_listings - last_month_listings) / last_month_listings * 100)
        if listings_change_percent > 0:
            listings_change = f'▲ {listings_change_percent:.0f}% this month'
        elif listings_change_percent < 0:
            listings_change = f'▼ {abs(listings_change_percent):.0f}% this month'
        else:
            listings_change = '0% this month'
    elif this_month_listings > 0:
        listings_change = f'▲ +{this_month_listings} new this month'
    else:
        listings_change = '0 new this month'
    
    # Build the stats dictionary
    stats = {
        'total_listings': f'{total_listings:,}',
        'total_sales_value': sales_value_display,
        'active_leads': str(active_leads_count),
        'files_uploaded': str(total_files),
        'listings_change': listings_change,
        'sales_change': sales_change,
        'leads_change': leads_change,
        'files_change': files_change
    }

    # ========== REAL DYNAMIC CHART DATA FROM DATABASE ==========
    from datetime import datetime, timedelta
    
    # Get all properties for this broker
    all_broker_properties = Property.query.filter_by(broker_id=broker_id).filter(Property.status != 'Deleted').all()
    now = datetime.utcnow()
    
    # ========== 1. WEEKLY DATA (Last 7 days) ==========
    weekly_labels = []
    weekly_sale_data = []
    weekly_rent_data = []
    
    for i in range(6, -1, -1):  # Last 7 days
        date = now - timedelta(days=i)
        day_start = datetime(date.year, date.month, date.day, 0, 0, 0)
        day_end = datetime(date.year, date.month, date.day, 23, 59, 59)
        
        day_label = date.strftime('%a')  # Mon, Tue, Wed, etc.
        
        sale_count = 0
        rent_count = 0
        
        for prop in all_broker_properties:
            if prop.created_at and day_start <= prop.created_at <= day_end:
                if prop.type and 'rent' in prop.type.lower():
                    rent_count += 1
                else:
                    sale_count += 1
        
        weekly_labels.append(day_label)
        weekly_sale_data.append(sale_count)
        weekly_rent_data.append(rent_count)
    
    # ========== 2. MONTHLY DATA (Only months with data or recent months) ==========
    monthly_labels = []
    monthly_sale_data = []
    monthly_rent_data = []
    
    # Find earliest property creation date
    earliest_date = now
    for prop in all_broker_properties:
        if prop.created_at and prop.created_at < earliest_date:
            earliest_date = prop.created_at
    
    # Determine start month (show last 12 months or since first property)
    start_month_date = earliest_date
    if (now.year - earliest_date.year) * 12 + (now.month - earliest_date.month) > 12:
        start_month_date = now - timedelta(days=365)  # Last 12 months only
    
    # Generate months from start to now
    current = start_month_date.replace(day=1)
    end = now.replace(day=1)
    
    while current <= end:
        month_start = datetime(current.year, current.month, 1, 0, 0, 0)
        
        # Calculate month end
        if current.month == 12:
            month_end = datetime(current.year + 1, 1, 1, 0, 0, 0) - timedelta(seconds=1)
        else:
            month_end = datetime(current.year, current.month + 1, 1, 0, 0, 0) - timedelta(seconds=1)
        
        month_label = current.strftime('%b %Y')
        
        sale_count = 0
        rent_count = 0
        
        for prop in all_broker_properties:
            if prop.created_at and month_start <= prop.created_at <= month_end:
                if prop.type and 'rent' in prop.type.lower():
                    rent_count += 1
                else:
                    sale_count += 1
        
        monthly_labels.append(month_label)
        monthly_sale_data.append(sale_count)
        monthly_rent_data.append(rent_count)
        
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    # ========== 3. YEARLY DATA (All years with properties) ==========
    yearly_labels = []
    yearly_sale_data = []
    yearly_rent_data = []
    
    # Get unique years from properties
    years_with_data = set()
    for prop in all_broker_properties:
        if prop.created_at:
            years_with_data.add(prop.created_at.year)
    
    # Also include current year even if no data yet
    years_with_data.add(now.year)
    
    if years_with_data:
        start_year = min(years_with_data)
        end_year = max(years_with_data)
        
        for year in range(start_year, end_year + 1):
            year_start = datetime(year, 1, 1, 0, 0, 0)
            year_end = datetime(year, 12, 31, 23, 59, 59)
            
            sale_count = 0
            rent_count = 0
            
            for prop in all_broker_properties:
                if prop.created_at and year_start <= prop.created_at <= year_end:
                    if prop.type and 'rent' in prop.type.lower():
                        rent_count += 1
                    else:
                        sale_count += 1
            
            yearly_labels.append(str(year))
            yearly_sale_data.append(sale_count)
            yearly_rent_data.append(rent_count)
    else:
        yearly_labels = [str(now.year)]
        yearly_sale_data = [0]
        yearly_rent_data = [0]
    
    # ========== Calculate Additional Stats ==========
    # Average Price
    active_properties = Property.query.filter_by(broker_id=broker_id, status='Active').all()
    prices = []
    for prop in active_properties:
        if prop.price:
            import re
            price_str = str(prop.price).replace('₹', '').replace(',', '').strip()
            price_match = re.search(r'[\d,]+(?:\.\d+)?', price_str)
            if price_match:
                try:
                    price_num = float(price_match.group().replace(',', ''))
                    if 'L' in str(prop.price).upper():
                        price_num *= 100000
                    elif 'Cr' in str(prop.price).upper():
                        price_num *= 10000000
                    prices.append(price_num)
                except:
                    pass
    
    if prices:
        avg_price_num = sum(prices) / len(prices)
        if avg_price_num >= 10000000:
            avg_price = f'₹{avg_price_num/10000000:.1f}Cr'
        elif avg_price_num >= 100000:
            avg_price = f'₹{avg_price_num/100000:.0f}L'
        else:
            avg_price = f'₹{avg_price_num/1000:.0f}k'
    else:
        avg_price = '₹0'
    
    # Days on Market
    if active_properties:
        total_days = 0
        for prop in active_properties:
            if prop.created_at:
                days = (datetime.utcnow() - prop.created_at).days
                total_days += days
        avg_days = total_days // len(active_properties)
        days_on_market = f'{avg_days} days'
    else:
        days_on_market = '0 days'
    
    # Conversion Rate
    total_props = len(all_broker_properties)
    if total_props > 0:
        sold_rented = Property.query.filter_by(broker_id=broker_id).filter(Property.status.in_(['Sold', 'Rented'])).count()
        conversion_rate = f'{(sold_rented/total_props)*100:.1f}%'
    else:
        conversion_rate = '0%'
    
    chart_data = {
        'weekly_labels': weekly_labels,
        'weekly_sale': weekly_sale_data,
        'weekly_rent': weekly_rent_data,
        'monthly_labels': monthly_labels,
        'monthly_sale': monthly_sale_data,
        'monthly_rent': monthly_rent_data,
        'yearly_labels': yearly_labels,
        'yearly_sale': yearly_sale_data,
        'yearly_rent': yearly_rent_data,
        'avg_price': avg_price,
        'days_on_market': days_on_market,
        'conversion_rate': conversion_rate,
        'total_listings': total_listings,
        'active_listings': len(active_properties)
    }
    
    # ========== Recent Activities ==========
    activities_list = Activity.query.filter_by(broker_id=broker_id).order_by(Activity.created_at.desc()).limit(5).all()
    recent_activities = []
    for a in activities_list:
        time_diff = datetime.utcnow() - a.created_at
        if time_diff.days > 0:
            if time_diff.days == 1:
                time_str = "Yesterday"
            else:
                time_str = f"{time_diff.days} days ago"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            time_str = f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            time_str = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            time_str = "Just now"
        
        recent_activities.append({
            'icon': a.icon,
            'msg': a.message,
            'time': time_str
        })
    
    # ========== Recent Files ==========
    files_list = UploadedFile.query.filter_by(broker_id=broker_id).order_by(UploadedFile.uploaded_at.desc()).limit(5).all()
    recent_files = [{
        'type': f.file_type.lower(),
        'name': f.filename,
        'rows': f'{f.rows_count} rows' if f.rows_count else '',
        'size': f.file_size,
        'date': f.uploaded_at.strftime('%b %d, %Y'),
        'status': f.status,
        'progress': 100 if f.status == 'completed' else 65
    } for f in files_list]
    
    # ========== Recent Listings ==========
    recent_listings = []
    try:
        properties = Property.query.filter_by(broker_id=broker_id).filter(Property.status != 'Deleted').order_by(Property.created_at.desc()).limit(10).all()
        for prop in properties:
            category_lower = prop.category.lower() if prop.category else ''
            type_class = 'for-sale' if 'sale' in category_lower else 'for-rent' if 'rent' in category_lower else 'for-sale'
            
            status_lower = prop.status.lower() if prop.status else ''
            status_class = 'active' if status_lower in ['available', 'active'] else 'sold' if status_lower in ['sold', 'rented'] else 'review'
            
            recent_listings.append({
                'name': prop.property,
                'location': prop.location or 'Tricity Region',
                'type': prop.type,
                'type_class': type_class,
                'price': prop.price,
                'area': prop.area,
                'bedrooms': prop.bedrooms,
                'category': prop.category,
                'status': prop.status.title() if prop.status else 'Active',
                'status_class': status_class,
                'agent': prop.agent,
                'id': prop.id,
                'created_at': prop.created_at
            })
    except Exception as e:
        print(f"Error fetching recent listings: {e}")
    
    # ========== Leads Data ==========
    leads_list = Lead.query.filter_by(broker_id=broker_id).order_by(Lead.created_at.desc()).limit(20).all()
    recent_leads = []
    for lead in leads_list:
        time_diff = datetime.utcnow() - lead.created_at
        if time_diff.days > 0:
            if time_diff.days == 1:
                time_str = "Yesterday"
            else:
                time_str = f"{time_diff.days} days ago"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            time_str = f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            time_str = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            time_str = "Just now"
        
        recent_leads.append({
            'id': lead.id,
            'name': lead.name,
            'email': lead.email,
            'phone': lead.phone or 'N/A',
            'property_name': lead.property_name or 'General Inquiry',
            'message': lead.message[:100] + '...' if lead.message and len(lead.message) > 100 else lead.message,
            'status': lead.status,
            'source': lead.source,
            'time': time_str,
            'created_at': lead.created_at
        })
    
    leads_count = Lead.query.filter_by(broker_id=broker_id).count()
    new_leads_count = Lead.query.filter_by(broker_id=broker_id, status='New').count()
    
    # Registered users
    try:
        buyers = Broker.query.filter_by(role='buyer').order_by(Broker.created_at.desc()).all()
        registered_users = []
        for b in buyers:
            registered_users.append({
                'name': b.name,
                'email': b.email,
                'phone': b.phone,
                'role': b.role,
                'created_at': b.created_at
            })
        users_count = len(registered_users)
    except Exception as e:
        print(f"Error fetching users: {e}")
        registered_users = []
        users_count = 0

    return {
        'chart_data': chart_data,
        'stats': stats,
        'recent_activities': recent_activities,
        'recent_files': recent_files,
        'recent_listings': recent_listings,
        'recent_leads': recent_leads,
        'total_listings': total_listings,
        'file_count': total_files,
        'leads_count': leads_count,
        'new_leads_count': new_leads_count,
        'admin_initials': initials,
        'admin_name': admin_name,
        'admin_role': 'Broker',
        'page_title': 'Dashboard Overview',
        'registered_users': registered_users,
        'users_count': users_count
    }


@app.route("/admin/api/property/update-status/<int:property_id>", methods=["POST"])
@login_required
def update_property_status(property_id):
    """Update property status (Active, Sold, Rented, Disconnected)"""
    try:
        property_obj = Property.query.get_or_404(property_id)
        
        # Verify ownership
        if property_obj.broker_id != current_user.broker_id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        data = request.get_json()
        new_status = data.get('status')
        
        valid_statuses = ['Active', 'Sold', 'Rented', 'Disconnected']
        if new_status not in valid_statuses:
            return jsonify({'success': False, 'message': 'Invalid status'}), 400
        
        old_status = property_obj.status
        property_obj.status = new_status
        db.session.commit()
        
        # Add activity log
        add_activity(
            current_user.broker_id,
            '🔄',
            f'<strong>Status Changed</strong> — {property_obj.property} from {old_status} to {new_status}'
        )
        
        # Create notification for broker
        create_notification(
            recipient_type='broker',
            recipient_id=current_user.broker_id,
            notification_type='property_status_change',
            title=f"🏠 Property Status Updated",
            message=f"'{property_obj.property}' is now {new_status}",
            icon='🔄',
            link=f'/property/{property_id}'
        )
        
        return jsonify({'success': True, 'message': f'Property status updated to {new_status}'})
    except Exception as e:
        print(f"Error updating property status: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    
    
# --- Authentication Routes ---

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        if getattr(current_user, 'role', 'broker') == 'broker':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('index'))
    
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
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            return render_template("auth/signup.html", error=f"Signup failed: {str(e)}")
            
    return render_template("auth/signup.html")


@app.route("/signin", methods=["GET", "POST"])
def signin():
    if current_user.is_authenticated:
        # Check for Super Admin first
        if current_user.is_super_admin:
            return redirect(url_for('super_admin_dashboard'))
        elif getattr(current_user, 'role', 'broker') == 'broker':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('index'))
    
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        
        broker = Broker.query.filter_by(email=email).first()
        if broker and broker.check_password(password):
            login_user(broker)
            # Check role after login
            if broker.is_super_admin:
                return redirect(url_for('super_admin_dashboard'))
            elif getattr(broker, 'role', 'broker') == 'broker':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            return render_template("auth/signin.html", error="Invalid email or password")
            
    return render_template("auth/signin.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        if getattr(current_user, 'role', 'broker') == 'broker':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('index'))
    
    if request.method == "POST":
        email = request.form.get('email')
        broker = Broker.query.filter_by(email=email).first()
        
        if broker:
            token = s.dumps(email, salt='password-reset-salt')
            reset_link = url_for('reset_password', token=token, _external=True)
            
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



@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    try:
        # Token valid for 1 hour (3600 seconds)
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        return render_template("auth/forgot_password.html", error="The reset link is invalid or has expired.")
    
    if request.method == "POST":
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            return render_template("auth/reset_password.html", token=token, error="Passwords do not match")
        
        # Password complexity validation: 6-8 chars, letters and special characters
        if not (6 <= len(password) <= 8):
            return render_template("auth/reset_password.html", token=token, error="Password must be 6-8 characters long")
        
        if not re.search(r"[a-zA-Z]", password) or not re.search(r"[^a-zA-Z0-9]", password):
            return render_template("auth/reset_password.html", token=token, error="Password must include at least one letter and one special character")
        
        broker = Broker.query.filter_by(email=email).first()
        if broker:
            broker.set_password(password)
            db.session.commit()
            flash("Your password has been reset successfully. Please sign in.", "success")
            return redirect(url_for('signin'))
        else:
            return render_template("auth/forgot_password.html", error="User not found")
            
    return render_template("auth/reset_password.html", token=token)


@app.route("/")
def index():
    return render_template("index.html", **landing_page_context())


@app.route("/search")
def search():
    return render_template("index.html", **landing_page_context())


@app.route("/property/<type>")
def property_type(type):
    return render_template("index.html", **landing_page_context())


@app.route("/portfolio/<int:broker_id>")
def broker_portfolio(broker_id):
    """Display properties for a specific broker"""
    try:
        broker = Broker.query.get_or_404(broker_id)
        default_images = {
            'Apartment': "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600",
            'Flat': "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600",
            'Villa': "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600",
            'Commercial': "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600",
            'Plot': "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=600",
            'Studio': "https://images.unsplash.com/photo-1520637836862-4d197d17c155?w=600"
        }
        
        # Only show Active properties for this specific broker
        broker_props = Property.query.filter_by(broker_id=broker_id, status='Active').order_by(Property.created_at.desc()).all()
        
        display_properties = []
        for prop in broker_props:
            prop_data = {
                'id': prop.id,
                'name': prop.property or 'Untitled Property',
                'price': prop.price or 'Price on request',
                'location': prop.location or 'Tricity Region',
                'beds': prop.bedrooms or 'N/A',
                'baths': 'N/A',
                'sqft': prop.area or 'N/A',
                'badge': prop.status or 'Active',
                'badge_class': 'sale' if 'Sale' in (prop.type or '') else 'rent',
                'featured': False,
                'broker_name': broker.name,
                'broker_phone': broker.phone or '+91 00000 00000'
            }
            
            image_url, image_list = build_image_urls(prop.image, prop.category, default_images)
            prop_data['image'] = image_url
            prop_data['images'] = image_list
            display_properties.append(prop_data)
            
        return render_template("properties.html", properties=display_properties, portfolio_broker=broker)
        
    except Exception as e:
        print(f"Error loading broker portfolio: {e}")
        return redirect(url_for('index'))



@app.route("/properties")
def all_properties():
    """Route to display all properties with advanced filters"""
    try:
        default_images = {
            'Apartment': "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600",
            'Flat': "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600",
            'Villa': "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600",
            'Commercial': "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600",
            'Plot': "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=600",
            'Studio': "https://images.unsplash.com/photo-1520637836862-4d197d17c155?w=600"
        }
        
        # Start with Active properties only
        query = Property.query.filter(Property.status == 'Active')
        
        # ========== GET ALL FILTER PARAMETERS ==========
        location = request.args.get('location', '').strip()
        property_type = request.args.get('type', '').strip()
        min_price = request.args.get('min_price', '').strip()
        max_price = request.args.get('max_price', '').strip()
        min_area = request.args.get('min_area', '').strip()
        max_area = request.args.get('max_area', '').strip()
        bedrooms_param = request.args.get('bedrooms', '').strip()
        category_param = request.args.get('category', '').strip()
        listing_type_param = request.args.get('listing_type', '').strip()
        
        print(f"🔍 SEARCH PARAMS: location={location}, type={property_type}, min_price={min_price}, max_price={max_price}")
        
        # ========== 1. LOCATION FILTER ==========
        if location:
            query = query.filter(
                or_(
                    Property.property.ilike(f'%{location}%'),
                    Property.location.ilike(f'%{location}%')
                )
            )
            print(f"📍 Location filter applied: {location}")
        
        # ========== 2. PROPERTY TYPE FILTER ==========
        if property_type and property_type != '':
            query = query.filter(
                or_(
                    Property.category.ilike(f'%{property_type}%'),
                    Property.type.ilike(f'%{property_type}%')
                )
            )
            print(f"🏢 Type filter applied: {property_type}")
        
        # ========== 3. LISTING TYPE FILTER (Sale/Rent) ==========
        if listing_type_param and listing_type_param != '':
            query = query.filter(Property.type.ilike(f'%{listing_type_param}%'))
            print(f"📋 Listing type filter applied: {listing_type_param}")
        
        # Get all properties after basic filters
        properties = query.all()
        
        # ========== APPLY NUMERIC FILTERS (Price, Area, Bedrooms, Category) ==========
        filtered_properties = []
        for prop in properties:
            # Parse price to number
            price_num = parse_price_to_number(prop.price)
            
            # Parse area
            area_num = 0
            if prop.area:
                try:
                    import re
                    area_match = re.search(r'(\d+)', str(prop.area))
                    if area_match:
                        area_num = int(area_match.group(1))
                except:
                    area_num = 0
            
            # ========== PRICE RANGE FILTER ==========
            if min_price:
                try:
                    if price_num < float(min_price):
                        continue
                except:
                    pass
            
            if max_price:
                try:
                    if price_num > float(max_price):
                        continue
                except:
                    pass
            
            # ========== AREA RANGE FILTER ==========
            if min_area:
                try:
                    if area_num < float(min_area):
                        continue
                except:
                    pass
            
            if max_area:
                try:
                    if area_num > float(max_area):
                        continue
                except:
                    pass
            
            # ========== BEDROOMS FILTER ==========
            if bedrooms_param and bedrooms_param != '':
                # Split multiple bedroom values (e.g., "1 BHK,2 BHK")
                bedroom_list = bedrooms_param.split(',')
                bedroom_match = False
                for bed in bedroom_list:
                    if prop.bedrooms and bed.strip() in prop.bedrooms:
                        bedroom_match = True
                        break
                if not bedroom_match:
                    continue
            
            # ========== CATEGORY FILTER ==========
            if category_param and category_param != '':
                category_list = category_param.split(',')
                category_match = False
                for cat in category_list:
                    if prop.category and cat.strip() in prop.category:
                        category_match = True
                        break
                if not category_match:
                    continue
            
            # If all filters passed, add to results
            filtered_properties.append(prop)
        
        print(f"✅ Found {len(filtered_properties)} properties after all filters")
        
        # ========== CONVERT TO RESPONSE FORMAT ==========
        display_properties = []
        for prop in filtered_properties:
            bedrooms_display = prop.bedrooms or 'N/A'
            beds = 1
            baths = 1
            sqft = prop.area or 'N/A'
            
            if bedrooms_display != 'N/A':
                import re
                bhk_match = re.search(r'(\d+)\s*BHK', bedrooms_display, re.IGNORECASE)
                if bhk_match:
                    beds = int(bhk_match.group(1))
                    baths = beds
                    sqft_estimates = {1: '650', 2: '1,100', 3: '1,450', 4: '2,200'}
                    sqft = f"{sqft_estimates.get(beds, '1,200')} sqft"
                elif bedrooms_display.lower().startswith('studio'):
                    beds = 0
                    baths = 1
                    sqft = '550 sqft'
            
            badge_class = 'rent' if prop.type and 'rent' in prop.type.lower() else 'sale'
            
            # Get image URL
            image_url = default_images.get(prop.category, default_images['Apartment'])
            image_list = []
            if prop.image:
                try:
                    import json
                    imgs = json.loads(prop.image)
                    if isinstance(imgs, list) and len(imgs) > 0:
                        image_list = [url_for('uploaded_file', filename=f) for f in imgs]
                        image_url = image_list[0]
                    else:
                        image_url = url_for('uploaded_file', filename=prop.image)
                        image_list = [image_url]
                except:
                    image_url = url_for('uploaded_file', filename=prop.image)
                    image_list = [image_url]
            
            display_properties.append({
                'id': prop.id,
                'name': prop.property or 'Untitled Property',
                'price': prop.price or 'Price on request',
                'location': prop.location or 'Tricity Region',
                'beds': beds,
                'baths': baths,
                'sqft': sqft,
                'badge': prop.type or 'For Sale',
                'badge_class': badge_class,
                'featured': False,
                'broker_name': prop.broker_info.name if prop.broker_info else 'NestFind Agent',
                'broker_phone': prop.broker_info.phone if prop.broker_info else '+91 00000 00000',
                'image': image_url,
                'images': image_list
            })
        
        return render_template("properties.html", properties=display_properties)
        
    except Exception as e:
        print(f"❌ Error loading properties page: {e}")
        import traceback
        traceback.print_exc()
        return render_template("properties.html", properties=[])
    


def parse_price_to_number(price_str):
    """Convert price string to numeric value for comparison"""
    if not price_str:
        return 0
    
    price_str = str(price_str).lower().replace('₹', '').replace(',', '').strip()
    
    import re
    price_match = re.search(r'[\d,]+(?:\.\d+)?', price_str)
    if not price_match:
        return 0
    
    try:
        price_num = float(price_match.group().replace(',', ''))
        
        if 'lakh' in price_str or ('l' in price_str and 'lakh' not in price_str and 'cr' not in price_str):
            price_num *= 100000
        elif 'cr' in price_str:
            price_num *= 10000000
        elif 'k' in price_str or '/mo' in price_str:
            price_num *= 1000
        
        return price_num
    except:
        return 0


@app.route("/subscribe", methods=["POST"])
def subscribe_newsletter():
    return "Subscribed!"  # Simple response for now


@app.route("/contact", methods=["POST"])
def submit_contact():
    try:
        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        looking_for = request.form.get('looking_for')
        message = request.form.get('message')
        
        # Get property and broker info
        property_id = request.form.get('property_id')
        property_name = request.form.get('property_name')
        broker_id = request.form.get('broker_id')

        print(f"📝 Contact Form Submission:")
        print(f"   Name: {name}")
        print(f"   Email: {email}")
        print(f"   Looking for: {looking_for}")
        print(f"   Property: {property_name}")
        print(f"   Broker ID: {broker_id}")

        # Validate required fields
        if not name or not email:
            return jsonify({'success': False, 'message': 'Name and email are required'}), 400

        # ========== PREVENT DUPLICATE SUBMISSIONS ==========
        # Check for duplicate in last 5 seconds
        from datetime import timedelta
        time_threshold = datetime.utcnow() - timedelta(seconds=5)
        
        recent_lead = Lead.query.filter(
            Lead.email == email,
            Lead.name == name,
            Lead.created_at >= time_threshold
        ).first()
        
        if recent_lead:
            print(f"⚠️ Duplicate submission detected for {email} - ignoring")
            return jsonify({'success': True, 'message': 'Your inquiry has already been received!'})

        # Save to User table
        new_contact = User(
            name=name,
            email=email,
            phone=phone,
            looking_for=looking_for,
            message=message
        )
        db.session.add(new_contact)
        
        # Create Lead record
        lead = Lead(
            name=name,
            email=email,
            phone=phone,
            property_id=int(property_id) if property_id else None,
            property_name=property_name or 'General Inquiry',
            broker_id=int(broker_id) if broker_id else None,
            message=message,
            source='Contact Form',
            status='New',
            interest_level='New',
            created_at=datetime.utcnow()
        )
        db.session.add(lead)
        db.session.commit()
        
        print(f"✅ Lead created with ID: {lead.id}")
        
        # 🔔 CREATE NOTIFICATION FOR BROKER (if broker_id exists)
        if broker_id:
            try:
                notification_title = f"📋 New Lead: {name}"
                notification_message = f"{name} inquired about '{property_name or 'property'}'"
                
                create_notification(
                    recipient_type='broker',
                    recipient_id=int(broker_id),
                    notification_type='lead_new',
                    title=notification_title,
                    message=notification_message,
                    icon='📋',
                    link='/admin/leads',
                    extra_data={
                        'lead_id': lead.id,
                        'customer_name': name,
                        'customer_email': email,
                        'property_name': property_name
                    }
                )
                print(f"🔔 Notification sent to broker {broker_id}")
            except Exception as notify_error:
                print(f"❌ Failed to send notification: {notify_error}")
                
        else:
            print(f"⚠️ No broker_id provided - sending to Super Admin instead")
            
            # Send notification to SUPER ADMIN
            super_admins = Broker.query.filter_by(is_super_admin=True).all()
            if super_admins:
                for admin in super_admins:
                    try:
                        create_notification(
                            recipient_type='broker',
                            recipient_id=admin.broker_id,
                            notification_type='lead_new',
                            title=f"📋 New General Inquiry: {name}",
                            message=f"{name} submitted an inquiry: {looking_for}",
                            icon='📋',
                            link='/super-admin/leads',
                            extra_data={'lead_id': lead.id, 'customer_name': name}
                        )
                        print(f"🔔 Notification sent to Super Admin: {admin.name} (ID: {admin.broker_id})")
                    except Exception as e:
                        print(f"❌ Failed to notify super admin: {e}")
            else:
                print(f"⚠️ No Super Admin found! Create a super admin first.")
        
        # 🔔 CREATE NOTIFICATION FOR USER
        if email:
            try:
                user_notification_title = "✅ Inquiry Received"
                user_notification_message = f"We've received your inquiry. Our team will contact you soon!"
                
                create_notification(
                    recipient_type='user',
                    recipient_id=email,
                    notification_type='inquiry_confirmation',
                    title=user_notification_title,
                    message=user_notification_message,
                    icon='✅',
                    link='/'
                )
                print(f"🔔 User notification sent to {email}")
            except Exception as user_notify_error:
                print(f"❌ Failed to send user notification: {user_notify_error}")
        
        return jsonify({'success': True, 'message': 'Thank you for contacting us! We will get back to you soon.'})

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error saving contact: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'}), 500
    
    
@app.route("/compare")
def compare_properties():
    """Property comparison page"""
    return render_template("compare.html")



@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if getattr(current_user, 'role', 'broker') != 'broker':
        flash('Access Denied. You must be a broker to access the dashboard.', 'error')
        return redirect(url_for('index'))
    # Get all dashboard data for current broker
    dashboard_data = get_admin_dashboard_data(current_user.broker_id)
    
    return render_template("admin/dashboard.html", **dashboard_data)


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def normalize_image_value(raw_value):
    """Normalize imported image values into a single filename/URL or JSON list."""
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    if not value or value.lower() in {'nan', 'none', 'null'}:
        return None

    # Handle comma/semicolon/pipe separated lists of images
    if any(sep in value for sep in [',', ';', '|']):
        parts = [part.strip() for part in re.split(r'[;,|]+', value) if part.strip() and part.strip().lower() not in {'nan', 'none', 'null'}]
        if len(parts) > 1:
            return json.dumps(parts)
        if len(parts) == 1:
            return parts[0]

    return value


def build_image_urls(prop_image, category, default_images):
    """Return the primary image and image list for a property."""
    default = default_images.get(category, default_images['Apartment'])
    if not prop_image:
        return default, [default]

    try:
        img_data = json.loads(prop_image)
    except Exception:
        img_data = prop_image

    def resolve_image_url(img):
        img_str = str(img).strip()
        if not img_str:
            return None
        if img_str.lower().startswith(('http://', 'https://')):
            return img_str
        return url_for('uploaded_file', filename=img_str)

    if isinstance(img_data, list):
        resolved = [resolve_image_url(img) for img in img_data]
        resolved = [img for img in resolved if img]
        if resolved:
            return resolved[0], resolved
        return default, [default]

    if isinstance(img_data, str):
        resolved = resolve_image_url(img_data)
        if resolved:
            return resolved, [resolved]

    return default, [default]


def get_file_size_mb(size_bytes):
    """Convert bytes to MB string"""
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def process_csv_file(filepath, filename, broker_id):
    """Process CSV file and import data to database associated with a broker"""
    try:
        # Read CSV file
        df = pd.read_csv(filepath)
        
        # ========== NEW: VALIDATION SECTION ==========
        validation_errors = []
        validation_warnings = []
        
        # Check if file is empty
        if df.empty:
            return {
                'success': False,
                'message': 'CSV file is empty. Please add some data.'
            }
        
        # Check minimum rows (at least 1 data row)
        if len(df) < 1:
            return {
                'success': False,
                'message': 'CSV file has no data rows. Please add at least one property.'
            }
        
        # Check for required columns (property and price)
        required_columns = ['property', 'price']
        found_columns = [col.lower().replace(' ', '_') for col in df.columns]
        
        missing_columns = []
        for req in required_columns:
            if not any(req in col for col in found_columns):
                missing_columns.append(req)
        
        if missing_columns:
            return {
                'success': False,
                'message': f'Missing required columns: {", ".join(missing_columns)}. Please ensure your CSV has "property" and "price" columns.',
                'help': 'Download our sample template to see the correct format.'
            }
        
        # Check if file has too many empty rows
        empty_rows = df.isnull().all(axis=1).sum()
        if empty_rows > len(df) * 0.5:
            validation_warnings.append(f'Found {empty_rows} empty rows. Please clean up your file.')
        
        # Validate price formats
        price_column = None
        for col in df.columns:
            if 'price' in col.lower():
                price_column = col
                break
        
        if price_column:
            invalid_prices = []
            for idx, val in df[price_column].head(10).items():
                if pd.notna(val):
                    val_str = str(val).strip()
                    # Check if price looks valid
                    if not any(c.isdigit() for c in val_str):
                        invalid_prices.append(f"Row {idx+2}: '{val_str}'")
            
            if invalid_prices:
                validation_warnings.append(f'Found unusual price formats: {", ".join(invalid_prices[:3])}. Use formats like "50 Lakhs", "1.2 Cr", or "25000/mo"')
        
        # ========== CONTINUE WITH EXISTING PROCESSING ==========
        
        # Check if the first row contains data instead of headers
        first_row_values = df.iloc[0].astype(str).str.strip().str.lower()
        has_headers = True
        
        # Check if any column name looks like actual data
        for col in df.columns:
            col_str = str(col).strip().lower()
            if any(char in col_str for char in ['₹', '$', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']) or \
               col_str in ['villa', 'apartment', 'sale', 'rent', 'available', 'sold', 'pending']:
                has_headers = False
                break
        
        # If no headers detected, add the first row as data and use default column names
        if not has_headers:
            default_headers = ['property', 'type', 'price', 'category', 'status', 'agent']
            df = df.iloc[:, :6].copy()
            df.columns = default_headers[:len(df.columns)]
            validation_warnings.append('No headers detected. Using default column mapping.')
        
        # Strip whitespace from column names and convert to lowercase
        df.columns = df.columns.astype(str).str.strip().str.lower().str.replace(' ', '_')
        
        rows_count = len(df)
        imported_count = 0
        errors = []
        geocoded_count = 0
        
        # Column mapping (existing)
        column_mapping = {
            'property': ['property', 'property_name', 'name', 'title', 'listing_name'],
            'type': ['type', 'listing_type', 'property_type', 'offer_type'],
            'price': ['price', 'amount', 'listing_price', 'cost'],
            'category': ['category', 'property_category', 'listing_category', 'unit_type'],
            'location': ['location', 'city', 'address', 'area', 'region'],
            'area': ['area', 'sqft', 'size', 'sq_ft', 'square_feet', 'sqft_area'],
            'bedrooms': ['bedrooms', 'bhk', 'bedroom', 'rooms', 'beds', 'bed'], 
            'status': ['status', 'listing_status', 'property_status'],
            'agent': ['agent', 'agent_name', 'listing_agent', 'realtor'],
            'image': ['image', 'images', 'photo', 'photos', 'image_url', 'image_urls', 'picture', 'picture_url']
        }
        
        # Find actual column names in the dataframe
        actual_columns = {}
        for target_field, possible_names in column_mapping.items():
            for possible_name in possible_names:
                if possible_name in df.columns:
                    actual_columns[target_field] = possible_name
                    break
        
        # Print debug info
        print(f"\n📊 CSV Columns found: {list(df.columns)}")
        print(f"📊 Column mapping: {actual_columns}")
        
        # Process each row
        for index, row in df.iterrows():
            try:
                property_name = str(row[actual_columns.get('property', 'property')]).strip()
                if not property_name or property_name == 'nan':
                    errors.append(f"Row {index + 2}: Missing property name")
                    continue
                
                price = str(row[actual_columns.get('price', 'price')]).strip()
                if not price or price == 'nan':
                    errors.append(f"Row {index + 2}: Missing price")
                    continue
                
                # Validate price format
                price_lower = price.lower()
                if not any(char.isdigit() for char in price_lower):
                    errors.append(f"Row {index + 2}: Price '{price}' doesn't contain numbers. Use format like '50 Lakhs' or '25000'")
                    continue
                
                property_type = str(row[actual_columns.get('type', 'type')]).strip() if actual_columns.get('type') else 'For Sale'
                if property_type == 'nan':
                    property_type = 'For Sale'
                
                category = str(row[actual_columns.get('category', 'category')]).strip() if actual_columns.get('category') else 'Apartment'
                if category == 'nan':
                    category = 'Apartment'
                
                status = 'Active'
                agent = str(row[actual_columns.get('agent', 'agent')]).strip() if actual_columns.get('agent') else 'System Import'
                if agent == 'nan':
                    agent = 'System Import'

                image_value = None
                if actual_columns.get('image'):
                    image_value = normalize_image_value(row[actual_columns['image']])
                
                area_value = None
                if actual_columns.get('area'):
                    area_value = str(row[actual_columns['area']]).strip()
                    if area_value == 'nan' or area_value == 'None' or area_value == '':
                        area_value = None
                
                bedrooms_value = None
                if actual_columns.get('bedrooms'):
                    bedrooms_value = str(row[actual_columns['bedrooms']]).strip()
                    if bedrooms_value == 'nan' or bedrooms_value == 'None' or bedrooms_value == '':
                        bedrooms_value = None
                
                # ========== NEW: Get location and geocode ==========
                location_value = None
                latitude = None
                longitude = None
                
                if actual_columns.get('location'):
                    location_value = str(row[actual_columns['location']]).strip()
                    if location_value and location_value != 'nan' and location_value != 'None':
                        # Geocode the address to get coordinates
                        try:
                            print(f"📍 Geocoding: {location_value} (Row {index + 2})")
                            lat, lng = geocode_address(location_value)
                            if lat and lng:
                                latitude = lat
                                longitude = lng
                                geocoded_count += 1
                                print(f"   ✅ Coordinates found: ({lat}, {lng})")
                            else:
                                print(f"   ⚠️ Could not geocode: {location_value}")
                            time.sleep(0.5)  # Rate limiting for Nominatim API
                        except Exception as e:
                            print(f"   ❌ Geocoding error: {e}")

                # Create property record with all fields INCLUDING COORDINATES
                new_property = Property(
                    property=property_name,
                    location=location_value,
                    type=property_type,
                    price=price,
                    area=area_value,
                    bedrooms=bedrooms_value,
                    category=category,
                    status=status,
                    agent=agent,
                    image=image_value,
                    broker_id=broker_id,
                    latitude=latitude,    # ADDED - for map
                    longitude=longitude   # ADDED - for map
                )
                db.session.add(new_property)
                imported_count += 1
                
                print(f"   ✅ Imported: {property_name}")
                
            except Exception as e:
                errors.append(f"Row {index + 2}: {str(e)}")
                continue
        
        db.session.commit()
        
        # Build result message with warnings
        result_message = f"Successfully imported {imported_count} properties from {rows_count} rows"
        if geocoded_count > 0:
            result_message += f"\n🗺️ Geocoded {geocoded_count} properties for map display"
        if validation_warnings:
            result_message += f"\n⚠️ Warnings: {'; '.join(validation_warnings[:3])}"
        if errors:
            result_message += f"\n❌ Errors ({len(errors)}): {', '.join(errors[:5])}"
        
        return {
            'success': True,
            'message': result_message,
            'imported_count': imported_count,
            'total_rows': rows_count,
            'geocoded_count': geocoded_count,
            'errors': errors,
            'warnings': validation_warnings
        }
        
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        
        # User-friendly error messages
        if "Expected" in error_msg and "fields" in error_msg:
            error_msg = "CSV format issue: " + error_msg + ". Download our sample template for correct format."
        elif "does not exist" in error_msg:
            error_msg = "File cannot be read. Please save as CSV (comma-separated) format."
        
        return {
            'success': False,
            'message': f"Error processing CSV: {error_msg}"
        }
    


def process_excel_file(filepath, filename, broker_id):
    """Process Excel file and import data to database associated with a broker"""
    try:
        # Read Excel file
        df = pd.read_excel(filepath)
        
        # Check if the first row contains data instead of headers
        first_row_values = df.iloc[0].astype(str).str.strip().str.lower()
        has_headers = True
        
        # Check if any column name looks like actual data
        for col in df.columns:
            col_str = str(col).strip().lower()
            # If column name contains numbers, currency symbols, or common data values
            if any(char in col_str for char in ['₹', '$', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']) or \
               col_str in ['villa', 'apartment', 'sale', 'rent', 'available', 'sold', 'pending']:
                has_headers = False
                break
        
        # If no headers detected, add the first row as data and use default column names
        if not has_headers:
            # Create new dataframe with default headers
            default_headers = ['property', 'type', 'price', 'category', 'status', 'agent']
            # Take only the first 6 columns if more exist
            df = df.iloc[:, :6].copy()
            df.columns = default_headers[:len(df.columns)]
        
        # Strip whitespace from column names and convert to lowercase
        df.columns = df.columns.astype(str).str.strip().str.lower()
        
        rows_count = len(df)
        imported_count = 0
        errors = []
        
        # Map possible column name variations
        column_mapping = {
            'property': ['property', 'property_name', 'name', 'title', 'listing_name'],
            'type': ['type', 'listing_type', 'property_type', 'offer_type'],
            'price': ['price', 'amount', 'listing_price', 'cost'],
            'category': ['category', 'property_category', 'listing_category', 'unit_type'],
            'location': ['location', 'city', 'address', 'area', 'region'],
            'status': ['status', 'listing_status', 'property_status'],
            'agent': ['agent', 'agent_name', 'listing_agent', 'realtor'],
            'image': ['image', 'images', 'photo', 'photos', 'image_url', 'image_urls', 'picture', 'picture_url']
        }
        
        # Find actual column names in the dataframe
        actual_columns = {}
        for target_field, possible_names in column_mapping.items():
            for possible_name in possible_names:
                if possible_name in df.columns:
                    actual_columns[target_field] = possible_name
                    break
        
        # Check if we have at least property column
        if 'property' not in actual_columns:
            return {
                'success': False,
                'message': f'Excel file missing required column. Found columns: {list(df.columns)}. Expected at least "property" column.'
            }
        
        # Process each row
        for index, row in df.iterrows():
            try:
                # Get property name (required)
                property_name = str(row[actual_columns.get('property', 'property')]).strip()
                if not property_name or property_name == 'nan':
                    errors.append(f"Row {index + 2}: Missing property name")
                    continue
                
                # Get price (required)
                price = str(row[actual_columns.get('price', 'price')]).strip()
                if not price or price == 'nan':
                    errors.append(f"Row {index + 2}: Missing price")
                    continue
                
                # Get other fields with defaults
                property_type = str(row[actual_columns.get('type', 'type')]).strip() if actual_columns.get('type') else 'For Sale'
                if property_type == 'nan':
                    property_type = 'For Sale'
                
                category = str(row[actual_columns.get('category', 'category')]).strip() if actual_columns.get('category') else 'Apartment'
                if category == 'nan':
                    category = 'Apartment'
                
                # Always set new imports to Active as requested
                status = 'Active'
                
                agent = str(row[actual_columns.get('agent', 'agent')]).strip() if actual_columns.get('agent') else 'System Import'
                if agent == 'nan':
                    agent = 'System Import'

                image_value = None
                if actual_columns.get('image'):
                    image_value = normalize_image_value(row[actual_columns['image']])
                
                # Create property record
                new_property = Property(
                    property=property_name,
                    location=str(row[actual_columns.get('location', 'location')]).strip() if actual_columns.get('location') else None,
                    type=property_type,
                    price=price,
                    category=category,
                    status=status,
                    agent=agent,
                    image=image_value,
                    broker_id=broker_id
                )
                db.session.add(new_property)
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Row {index + 2}: {str(e)}")
                continue
        
        # Commit all successful imports
        db.session.commit()
        
        result_message = f"Successfully imported {imported_count} properties from {rows_count} rows"
        if errors:
            result_message += f". Errors: {', '.join(errors[:5])}"
        
        return {
            'success': True,
            'message': result_message,
            'imported_count': imported_count,
            'total_rows': rows_count,
            'errors': errors
        }
        
    except Exception as e:
        db.session.rollback()
        return {
            'success': False,
            'message': f"Error processing Excel: {str(e)}"
        }


def batch_geocode_existing_properties(broker_id=None):
    """Geocode all active properties without coordinates"""
    from datetime import datetime
    import time
    
    query = Property.query.filter(
        Property.latitude.is_(None),
        Property.longitude.is_(None),
        Property.status == 'Active'
    )
    
    if broker_id:
        query = query.filter_by(broker_id=broker_id)
    
    properties = query.all()
    
    print(f"\n🗺️ Found {len(properties)} properties without coordinates")
    
    updated = 0
    for prop in properties:
        if prop.location:
            print(f"📍 Geocoding: {prop.property} - {prop.location}")
            lat, lng = geocode_address(prop.location)
            if lat and lng:
                prop.latitude = lat
                prop.longitude = lng
                updated += 1
                print(f"   ✅ Coordinates added")
            else:
                print(f"   ❌ Failed to geocode")
            time.sleep(0.5)  # Rate limiting
    
    db.session.commit()
    print(f"\n✅ Updated {updated} properties with coordinates")
    return updated


@app.route("/api/similar-properties/<int:property_id>")
def get_similar_properties(property_id):
    property_obj = Property.query.get_or_404(property_id)
    similar = Property.query.filter(
        Property.category == property_obj.category,
        Property.id != property_id,
        Property.status == 'Active'
    ).limit(3).all()
    
    return jsonify([{
        'id': p.id,
        'property': p.property,
        'price': p.price,
        'location': p.location,
        'image': build_image_urls(p.image, p.category, {})[0]
    } for p in similar])



def process_pdf_file(filepath, filename, broker_id):
    """Process PDF file and import data using tables and heuristic text parsing"""
    try:
        imported_count = 0
        total_pages = 0
        errors = []
        
        with pdfplumber.open(filepath) as pdf:
            total_pages = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages):
                # --- Method 1: Table Extraction ---
                tables = page.extract_tables()
                page_imported = 0
                if tables:
                    for table in tables:
                        if not table or len(table) < 1: continue
                        
                        # Heuristic: Find header row
                        headers = [str(cell).strip().lower() for cell in table[0] if cell]
                        column_mapping = {
                            'property': ['property', 'name', 'title', 'listing'],
                            'price': ['price', 'amount', 'cost', 'val'],
                            'area': ['area', 'sqft', 'size', 'sq ft'],
                            'category': ['category', 'type', 'unit'],
                        }
                        
                        mapping = {}
                        for field, options in column_mapping.items():
                            for i, h in enumerate(headers):
                                if any(opt in h for opt in options):
                                    mapping[field] = i
                                    break
                        
                        # Process rows (skip header if mapping found)
                        start_row = 1 if len(mapping) > 0 else 0
                        for row in table[start_row:]:
                            try:
                                # Clean row (remove None)
                                row = [str(c).strip() if c else "" for c in row]
                                if not any(row): continue
                                
                                prop_name = row[mapping.get('property', 0)] if 'property' in mapping else row[0]
                                price = row[mapping.get('price', 1)] if 'price' in mapping else (row[1] if len(row) > 1 else "")
                                
                                if prop_name and price and prop_name != 'None' and price != 'None':
                                    new_prop = Property(
                                        property=prop_name,
                                        price=price,
                                        area=row[mapping.get('area', -1)] if 'area' in mapping else "",
                                        category=row[mapping.get('category', -1)] if 'category' in mapping else "Apartment",
                                        type="For Sale",
                                        status="Active",
                                        agent="PDF Import",
                                        broker_id=broker_id
                                    )
                                    db.session.add(new_prop)
                                    imported_count += 1
                                    page_imported += 1
                            except: continue
                    if page_imported > 0:
                        continue # If tables processed and properties found, skip text extraction for this page to avoid duplicates
                
                # --- Method 2: Heuristic Text Parsing ---
                text = page.extract_text()
                if not text: continue
                
                lines = text.split('\n')
                for i, line in enumerate(lines):
                    # Look for Price Pattern (₹, Lakh, Cr, Rs)
                    price_match = re.search(r'((₹|Rs\.?)\s?[\d,.]+(\s?(Lakh|Cr|k))?|[\d,.]+\s?(Lakh|Cr))', line, re.IGNORECASE)
                    if price_match:
                        price = price_match.group(0)
                        # Heuristic: Property Name is likely in the current line or previous line
                        name = line.replace(price, "").strip()
                        if len(name) < 5 and i > 0:
                            name = lines[i-1].strip() + " " + name
                        
                        if len(name) > 3:
                            # Search for features in surrounding text
                            context = " ".join(lines[max(0, i-1):min(len(lines), i+2)])
                            
                            area_match = re.search(r'[\d,.]+\s?(sq\s?ft|sq\s?yd|yard|meter)', context, re.IGNORECASE)
                            bhk_match = re.search(r'\d\s?BHK', context, re.IGNORECASE)
                            
                            final_name = name.strip()
                            if bhk_match:
                                final_name += f" ({bhk_match.group(0)})"
                                
                            new_prop = Property(
                                property=final_name[:100],
                                price=price,
                                area=area_match.group(0) if area_match else "",
                                category="Apartment", # Default
                                type="For Sale",
                                status="Active",
                                agent="PDF AI Import",
                                broker_id=broker_id
                            )
                            db.session.add(new_prop)
                            imported_count += 1

        db.session.commit()
        return {
            'success': True,
            'message': f"Successfully imported {imported_count} properties from {total_pages} pages",
            'imported_count': imported_count
        }
    except Exception as e:
        db.session.rollback()
        return {
            'success': False,
            'message': f"Error processing PDF: {str(e)}"
        }


# Add these routes after your existing routes

@app.route("/api/notifications")
def get_notifications():
    """Get notifications for current user"""
    try:
        if current_user.is_authenticated:
            # Broker/Admin notifications
            notifications = get_user_notifications(user_id=current_user.broker_id)
            unread_count = get_unread_notifications_count(user_id=current_user.broker_id)
        else:
            # Public user notifications (by session or email)
            user_email = request.args.get('email')
            if user_email:
                notifications = get_user_notifications(user_email=user_email)
                unread_count = get_unread_notifications_count(user_email=user_email)
            else:
                notifications = []
                unread_count = 0
        
        return jsonify({
            'success': True,
            'notifications': [n.to_dict() for n in notifications],
            'unread_count': unread_count
        })
    except Exception as e:
        print(f"Error getting notifications: {e}")
        return jsonify({'success': False, 'notifications': [], 'unread_count': 0})


@app.route("/api/notifications/mark-read", methods=["POST"])
def mark_notifications_read():
    """Mark notifications as read"""
    try:
        data = request.get_json()
        notification_ids = data.get('notification_ids', [])
        
        if notification_ids:
            Notification.query.filter(Notification.id.in_(notification_ids)).update(
                {'is_read': True}, synchronize_session=False
            )
        else:
            # Mark all as read
            if current_user.is_authenticated:
                Notification.query.filter_by(user_id=current_user.broker_id, is_read=False).update(
                    {'is_read': True}, synchronize_session=False
                )
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error marking notifications read: {e}")
        return jsonify({'success': False}), 500

# API endpoints for AJAX calls
@app.route("/admin/api/upload", methods=["POST"])
@login_required
def upload_file():
    """Handle file uploads via AJAX"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    file_type = request.form.get('type', 'unknown')
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            'success': False, 
            'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400
    
    # Generate secure filename with unique ID
    original_filename = secure_filename(file.filename)
    file_extension = original_filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    
    try:
        # Save the file
        file.save(filepath)
        file_size_bytes = os.path.getsize(filepath)
        file_size_mb = get_file_size_mb(file_size_bytes)
        
        # Process file based on type
        processing_result = None
        rows_count = None
        imported_count = None
        
        if file_extension in ['csv']:
            processing_result = process_csv_file(filepath, original_filename, current_user.broker_id)
            # Get row count for metadata
            try:
                df = pd.read_csv(filepath)
                rows_count = len(df)
                if processing_result.get('success'):
                    imported_count = processing_result.get('imported_count', 0)
            except Exception as e:
                print(f"Error reading CSV: {e}")
                
        elif file_extension in ['xlsx', 'xls']:
            processing_result = process_excel_file(filepath, original_filename, current_user.broker_id)
            # Get row count for metadata
            try:
                df = pd.read_excel(filepath)
                rows_count = len(df)
                if processing_result.get('success'):
                    imported_count = processing_result.get('imported_count', 0)
            except Exception as e:
                print(f"Error reading Excel: {e}")
                
        elif file_extension == 'pdf':
            processing_result = process_pdf_file(filepath, original_filename, current_user.broker_id)
            # PDF doesn't have a simple row count usually, but we can get imported count
            if processing_result.get('success'):
                imported_count = processing_result.get('imported_count', 0)
                rows_count = imported_count # Approximate for feedback
        
        # Check if processing was successful
        if not processing_result or not processing_result.get('success', False):
            # Clean up file if processing failed
            if os.path.exists(filepath):
                os.remove(filepath)
            
            error_msg = processing_result.get('message', 'Unknown error occurred') if processing_result else 'Processing failed'
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # Save file metadata to database
        uploaded_file = UploadedFile(
            filename=original_filename,
            file_type=file_extension.upper(),
            file_size=file_size_mb,
            rows_count=rows_count if rows_count else (imported_count if imported_count else None),
            status='completed',
            broker_id=current_user.broker_id
        )
        db.session.add(uploaded_file)
        db.session.commit()
        
        # Create activity log
        activity_icon = '📄' if file_extension == 'pdf' else '📊'
        activity_message = f'<strong>{file_extension.upper()} Uploaded</strong> — {original_filename}'
        
        if imported_count:
            activity_message += f' ({imported_count} properties imported)'
        elif rows_count:
            activity_message += f' ({rows_count} rows processed)'
        
        activity = Activity(
            icon=activity_icon,
            message=activity_message,
            # time_ago='Just now',
            broker_id=current_user.broker_id
        )
        db.session.add(activity)
        db.session.commit()
        
        # Prepare response
        response_data = {
            'success': True,
            'filename': original_filename,
            'type': file_extension.upper(),
            'size': file_size_mb,
            'rows': rows_count,
            'imported_count': imported_count,
            'message': processing_result.get('message', 'File uploaded and processed successfully')
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        # Clean up file if something went wrong
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
        
        return jsonify({
            'success': False,
            'error': f'Upload failed: {str(e)}'
        }), 500


@app.route("/admin/api/property", methods=["POST"])
@login_required
def add_property():
    """Add a new property via AJAX"""
    data = request.get_json()
    print(f"Received property data: {data}")  # Debug log
    
    # Handle image upload if present
    image_filename = None
    if 'image' in request.files:
        image_file = request.files['image']
        if image_file and image_file.filename:
            # Generate unique filename
            filename = secure_filename(image_file.filename)
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            
            # Save image to uploads directory
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            image_file.save(image_path)
            image_filename = unique_filename
            print(f"Image saved: {image_filename}")  # Debug log
    
    # Create new property record
    new_property = Property(
        property=data.get('title'),
        location=data.get('location'),
        type=data.get('property_type'),
        price=data.get('price'),
        area=data.get('area'),
        bedrooms=data.get('bedrooms'),
        category=data.get('category'),
        status='Active',
        agent=data.get('agent'),
        image=image_filename,
        broker_id=current_user.broker_id
    )
    
    try:
        db.session.add(new_property)
        db.session.commit()
        print(f"Property saved successfully with ID: {new_property.id}")  # Debug log
        return jsonify({'success': True, 'message': 'Property added successfully', 'id': new_property.id})
    except Exception as e:
        print(f"Error saving property: {e}")  # Debug log
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/admin/api/properties", methods=["GET"])
@login_required
def get_properties():
    """Get all properties for current broker with optional filters"""
    try:
        # Get filter parameters
        property_type = request.args.get('type', '')  # 'For Sale' or 'For Rent'
        period_type = request.args.get('period', '')  # 'week', 'month', 'year'
        period_label = request.args.get('label', '')  # 'Mon', 'Jan 2024', etc.
        limit = request.args.get('limit', 50, type=int)
        
        # Start with base query
        query = Property.query.filter_by(broker_id=current_user.broker_id).filter(Property.status != 'Deleted')
        
        # Filter by property type (For Sale / For Rent)
        if property_type:
            if property_type == 'For Sale':
                query = query.filter(~Property.type.ilike('%rent%'))
            elif property_type == 'For Rent':
                query = query.filter(Property.type.ilike('%rent%'))
        
        # Filter by period (date range)
        if period_type and period_label:
            from datetime import datetime, timedelta
            
            now = datetime.utcnow()
            
            if period_type == 'week':
                # Map day names to day numbers
                days_map = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
                if period_label in days_map:
                    target_day = days_map[period_label]
                    today_weekday = now.weekday()
                    days_ago = today_weekday - target_day
                    target_date = now - timedelta(days=days_ago)
                    start_date = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
                    end_date = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)
                    query = query.filter(Property.created_at >= start_date, Property.created_at <= end_date)
            
            elif period_type == 'month':
                # Parse month label like "May 2026"
                try:
                    month_abbr = period_label.split()[0]
                    year = int(period_label.split()[1])
                    month_map = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                                'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
                    month = month_map.get(month_abbr, 1)
                    start_date = datetime(year, month, 1, 0, 0, 0)
                    if month == 12:
                        end_date = datetime(year + 1, 1, 1, 0, 0, 0) - timedelta(seconds=1)
                    else:
                        end_date = datetime(year, month + 1, 1, 0, 0, 0) - timedelta(seconds=1)
                    query = query.filter(Property.created_at >= start_date, Property.created_at <= end_date)
                except:
                    pass
            
            elif period_type == 'year':
                try:
                    year = int(period_label)
                    start_date = datetime(year, 1, 1, 0, 0, 0)
                    end_date = datetime(year, 12, 31, 23, 59, 59)
                    query = query.filter(Property.created_at >= start_date, Property.created_at <= end_date)
                except:
                    pass
        
        # Get properties
        properties = query.order_by(Property.created_at.desc()).limit(limit).all()
        
        return jsonify([{
            'id': p.id,
            'property': p.property,
            'type': p.type,
            'price': p.price,
            'category': p.category,
            'status': p.status,
            'agent': p.agent,
            'location': p.location,
            'created_at': p.created_at.isoformat() if p.created_at else None
        } for p in properties])
    except Exception as e:
        print(f"Error getting properties: {e}")
        return jsonify([]), 500


@app.route("/admin/api/property-with-image", methods=["POST"])
@login_required
def add_property_with_image():
    """Add a new property with multiple image uploads."""
    try:
        # Get property data from form
        property_data_str = request.form.get('property_data')
        if not property_data_str:
            return jsonify({'success': False, 'message': 'Property data is required'}), 400

        data = json.loads(property_data_str)

        # --- Get location FIRST (before using it) ---
        location = data.get('location', '')
        
        # --- Check for manually entered coordinates from map picker ---
        manual_lat = data.get('manual_lat')
        manual_lng = data.get('manual_lng')
        
        # --- Determine coordinates ---
        latitude = None
        longitude = None
        
        if manual_lat and manual_lng:
            try:
                latitude = float(manual_lat)
                longitude = float(manual_lng)
                print(f"📍 Using manual coordinates from map picker: {latitude}, {longitude}")
            except:
                if location:
                    latitude, longitude = geocode_address(location)
                else:
                    print(f"⚠️ Invalid manual coordinates and no location")
        else:
            if location:
                latitude, longitude = geocode_address(location)
                print(f"📍 Geocoded from address: {location} → ({latitude}, {longitude})")
            else:
                print(f"⚠️ No location provided for property")

        # --- Handle multiple images ---
        ALLOWED_IMAGE_EXTS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp','jfif'}
        uploaded_filenames = []

        image_files = request.files.getlist('images[]')
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        for image_file in image_files:
            if not image_file or not image_file.filename:
                continue
            original_name = secure_filename(image_file.filename)
            ext = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else ''
            if ext not in ALLOWED_IMAGE_EXTS:
                continue
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            image_file.save(image_path)
            uploaded_filenames.append(unique_filename)

        # Store as JSON array if multiple
        if len(uploaded_filenames) == 0:
            image_value = None
        elif len(uploaded_filenames) == 1:
            image_value = uploaded_filenames[0]
        else:
            image_value = json.dumps(uploaded_filenames)

        # --- Handle PDF Brochure ---
        brochure_filename = None
        if 'brochure' in request.files:
            pdf_file = request.files['brochure']
            if pdf_file and pdf_file.filename.lower().endswith('.pdf'):
                brochure_filename = f"{uuid.uuid4().hex}_{secure_filename(pdf_file.filename)}"
                pdf_file.save(os.path.join(app.config['UPLOAD_FOLDER'], brochure_filename))

        # Create new property record with coordinates
        new_property = Property(
            property=data.get('title'),
            location=location,
            type=data.get('property_type'),
            price=data.get('price'),
            area=data.get('area'),
            bedrooms=data.get('bedrooms'),
            category=data.get('category'),
            status='Active',
            agent=data.get('agent'),
            image=image_value,
            brochure=brochure_filename,
            broker_id=current_user.broker_id,
            latitude=latitude,
            longitude=longitude
        )

        db.session.add(new_property)
        db.session.commit()
        
        # Add activity log
        activity = Activity(
            icon='🏡',
            message=f'<strong>New Listing</strong> — {data.get("title")} added',
            broker_id=current_user.broker_id
        )
        db.session.add(activity)
        db.session.commit()

        primary = uploaded_filenames[0] if uploaded_filenames else None
        return jsonify({
            'success': True,
            'message': 'Property added successfully',
            'id': new_property.id,
            'primary_image': primary,
            'all_images': uploaded_filenames
        })
    except Exception as e:
        print(f"Error saving property: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    

@app.route("/admin/api/upload-image", methods=["POST"])
def upload_image():
    """Upload image for property update"""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': 'No image file provided'}), 400
        
        image_file = request.files['image']
        if not image_file or not image_file.filename:
            return jsonify({'success': False, 'message': 'No image file selected'}), 400
        
        # Generate unique filename
        filename = secure_filename(image_file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        unique_filename = f"{uuid.uuid4().hex}.{ext}"
        
        # Ensure upload directory exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Save image to uploads directory
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        image_file.save(image_path)
        
        print(f"Image uploaded: {unique_filename}")  # Debug log
        return jsonify({'success': True, 'filename': unique_filename})
    except Exception as e:
        print(f"Error uploading image: {e}")  # Debug log
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/admin/api/upload-images", methods=["POST"])
def upload_images():
    """Upload multiple images for property update"""
    try:
        if 'images[]' not in request.files:
            return jsonify({'success': False, 'message': 'No image files provided'}), 400
        
        image_files = request.files.getlist('images[]')
        if not image_files or len(image_files) == 0:
            return jsonify({'success': False, 'message': 'No image files selected'}), 400
        
        uploaded_filenames = []
        
        for image_file in image_files:
            if not image_file or not image_file.filename:
                continue
            
            # Generate unique filename
            filename = secure_filename(image_file.filename)
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            
            # Ensure upload directory exists
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            # Save image to uploads directory
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            image_file.save(image_path)
            
            uploaded_filenames.append(unique_filename)
        
        print(f"Images uploaded: {uploaded_filenames}")  # Debug log
        return jsonify({'success': True, 'filenames': uploaded_filenames})
    except Exception as e:
        print(f"Error uploading images: {e}")  # Debug log
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)




def geocode_address(address):
    """Convert address to latitude and longitude using OpenStreetMap Nominatim (free, no API key)"""
    if not address:
        return None, None
    
    try:
        # Add "Chandigarh, India" to help with geocoding
        full_address = f"{address}, Chandigarh, India"
        
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': full_address,
            'format': 'json',
            'limit': 1,
            'addressdetails': 1
        }
        headers = {
            'User-Agent': 'NestFind Real Estate App/1.0'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                print(f"✅ Geocoded: {address} → ({lat}, {lon})")
                return lat, lon
            else:
                print(f"❌ No coordinates found for: {address}")
                return None, None
        else:
            print(f"❌ Geocoding failed: {response.status_code}")
            return None, None
            
    except Exception as e:
        print(f"❌ Geocoding error: {e}")
        return None, None

@app.route("/api/search", methods=["GET"])
def search_properties():
    """Search properties with filters"""
    try:
        # Get search parameters
        location = request.args.get('location', '').strip()
        property_type = request.args.get('type', '').strip()
        min_budget = request.args.get('min_budget')
        max_budget = request.args.get('max_budget')
        
        
        # For public search, only show Active properties
        query = Property.query.filter(Property.status == 'Active')
        
        # Apply filters
        if location:
            # Search in both property name and location field
            query = query.filter(
                or_(
                    Property.property.ilike(f'%{location}%'),
                    Property.location.ilike(f'%{location}%')
                )
            )
        
        if property_type and property_type != 'Property Type':
            query = query.filter(
                or_(
                    Property.category.ilike(f'%{property_type}%'),
                    Property.type.ilike(f'%{property_type}%')
                )
            )
        
        # Get all properties first to apply price filtering
        properties = query.all()
        
        # Filter by budget if specified
        if min_budget or max_budget:
            filtered_properties = []
            for prop in properties:
                price_numeric = 0
                price_str = str(prop.price or '').replace('₹', '').replace(',', '').strip()
                
                # Extract numeric value
                import re
                price_match = re.search(r'[\d,]+(?:\.\d+)?', price_str)
                if price_match:
                    try:
                        price_numeric = float(price_match.group().replace(',', ''))
                        # Convert lakhs/crores
                        if 'L' in price_str.upper():
                            price_numeric *= 100000
                        elif 'Cr' in price_str.upper():
                            price_numeric *= 10000000
                        elif 'k' in price_str.lower() or '/mo' in price_str.lower():
                            # Monthly rent in thousands
                            price_numeric *= 1000
                        
                        # Apply budget filters
                        if min_budget:
                            try:
                                min_val = float(min_budget.replace('₹', '').replace(',', '').replace('L', '00000').replace('Cr', '0000000'))
                                if price_numeric < min_val:
                                    continue
                            except:
                                pass
                        
                        if max_budget:
                            try:
                                max_val = float(max_budget.replace('₹', '').replace(',', '').replace('L', '00000').replace('Cr', '0000000'))
                                if price_numeric > max_val:
                                    continue
                            except:
                                pass
                        
                        filtered_properties.append(prop)
                    except:
                        # If can't parse price, include it anyway
                        filtered_properties.append(prop)
                else:
                    # If no price match, include it
                    filtered_properties.append(prop)
            
            properties = filtered_properties
        
        # Convert to response format
        results = []
        default_images = {
            'Apartment': "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600",
            'Flat': "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600",
            'Villa': "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600",
            'Commercial': "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600",
            'Plot': "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=600",
            'Studio': "https://images.unsplash.com/photo-1520637836862-4d197d17c155?w=600"
        }
        
        for prop in properties[:20]:  # Limit to 20 results
            image, all_images = build_image_urls(prop.image, prop.category, default_images)
            
            results.append({
                'id': prop.id,
                'name': prop.property or 'Untitled Property',
                'location': prop.location or 'Tricity Region',
                'price': prop.price or 'Price on request',
                'type': prop.type or 'For Sale',
                'category': prop.category or 'Apartment',
                'bedrooms': prop.bedrooms or 'N/A',
                'area': prop.area or 'N/A',
                'image': image,
                'all_images': all_images,
                'agent': prop.agent or 'NestFind Agent',
                'broker_name': prop.broker_info.name if prop.broker_info else 'NestFind Agent',
                'broker_phone': prop.broker_info.phone if prop.broker_info else '+91 00000 00000'
            })
        
        return jsonify({
            'success': True,
            'properties': results,
            'count': len(results)
        })
        
    except Exception as e:
        print(f"Error searching properties: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/api/budget-ranges", methods=["GET"])
def get_budget_ranges():
    """Get dynamic budget ranges based on available properties"""
    try:
        properties = Property.query.filter(Property.status != 'Deleted').all()
        
        prices = []
        for prop in properties:
            price_str = str(prop.price or '').replace('₹', '').replace(',', '').strip()
            
            # Extract numeric value
            import re
            price_match = re.search(r'[\d,]+(?:\.\d+)?', price_str)
            if price_match:
                try:
                    price_numeric = float(price_match.group().replace(',', ''))
                    # Convert lakhs/crores
                    if 'L' in price_str.upper():
                        price_numeric *= 100000
                    elif 'Cr' in price_str.upper():
                        price_numeric *= 10000000
                    elif 'k' in price_str.lower() or '/mo' in price_str.lower():
                        # Monthly rent in thousands
                        price_numeric *= 1000
                    
                    prices.append(price_numeric)
                except:
                    pass
        
        if not prices:
            # Default ranges if no prices found
            return jsonify({
                'ranges': [
                    'Under ₹20L',
                    '₹20L – ₹50L',
                    '₹50L – ₹1Cr',
                    '₹1Cr – ₹2Cr',
                    'Above ₹2Cr'
                ]
            })
        
        min_price = min(prices)
        max_price = max(prices)
        
        # Create dynamic ranges
        ranges = []
        
        # Under minimum
        if min_price > 1000000:  # 10L
            ranges.append(f'Under ₹{int(min_price/100000)}L')
        
        # Create 4-5 ranges
        range_size = (max_price - min_price) / 4
        
        current = min_price
        for i in range(4):
            next_val = current + range_size
            if current >= 10000000:  # Crores
                current_display = f'₹{current/10000000:.1f}Cr'
                next_display = f'₹{next_val/10000000:.1f}Cr'
            elif current >= 100000:  # Lakhs
                current_display = f'₹{int(current/100000)}L'
                next_display = f'₹{int(next_val/100000)}L'
            else:
                current_display = f'₹{int(current/1000)}k'
                next_display = f'₹{int(next_val/1000)}k'
            
            ranges.append(f'{current_display} – {next_display}')
            current = next_val
        
        # Above maximum
        if max_price >= 10000000:  # Crores
            ranges.append(f'Above ₹{max_price/10000000:.1f}Cr')
        elif max_price >= 100000:  # Lakhs
            ranges.append(f'Above ₹{int(max_price/100000)}L')
        else:
            ranges.append(f'Above ₹{int(max_price/1000)}k')
        
        return jsonify({'ranges': ranges})
        
    except Exception as e:
        print(f"Error getting budget ranges: {e}")
        return jsonify({
            'ranges': [
                'Under ₹20L',
                '₹20L – ₹50L', 
                '₹50L – ₹1Cr',
                '₹1Cr – ₹2Cr',
                'Above ₹2Cr'
            ]
        }), 500


@app.route("/admin/api/property/<int:property_id>", methods=["GET"])
def get_property(property_id):
    """Get a single property by ID"""
    try:
        property_obj = Property.query.get_or_404(property_id)
        
        # Handle multi-image logic - return the full image data for editing
        image_data = property_obj.image
        try:
            if property_obj.image:
                img_parsed = json.loads(property_obj.image)
                if isinstance(img_parsed, list):
                    image_data = property_obj.image  # Keep as JSON string for frontend parsing
                else:
                    image_data = property_obj.image  # Single image filename
        except:
            image_data = property_obj.image  # Fallback to original

        return jsonify({
            'id': property_obj.id,
            'property': property_obj.property,
            'location': property_obj.location,
            'type': property_obj.type,
            'price': property_obj.price,
            'area': property_obj.area,
            'bedrooms': property_obj.bedrooms,
            'category': property_obj.category,
            'status': property_obj.status,
            'agent': property_obj.agent,
            'image': image_data,
            'brochure': property_obj.brochure,
            'created_at': property_obj.created_at.isoformat() if property_obj.created_at else None
        })
    except Exception as e:
        print(f"Error getting property {property_id}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/admin/api/property/<int:property_id>", methods=["PUT"])
@login_required
def update_property(property_id):
    """Update a property by ID"""
    try:
        property_obj = Property.query.get_or_404(property_id)
        
        # Verify ownership
        if property_obj.broker_id != current_user.broker_id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
            
        data = request.get_json()
        
        # Update fields
        property_obj.property = data.get('title', property_obj.property)
        property_obj.location = data.get('location', property_obj.location)
        property_obj.type = data.get('property_type', property_obj.type)
        property_obj.price = data.get('price', property_obj.price)
        property_obj.area = data.get('area', property_obj.area)
        property_obj.bedrooms = data.get('bedrooms', property_obj.bedrooms)
        property_obj.category = data.get('category', property_obj.category)
        property_obj.status = data.get('status', property_obj.status)
        property_obj.agent = data.get('agent', property_obj.agent)
        property_obj.image = data.get('image', property_obj.image)
        
        db.session.commit()
        print(f"Property {property_id} updated successfully")
        return jsonify({'success': True, 'message': 'Property updated successfully'})
    except Exception as e:
        print(f"Error updating property {property_id}: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/admin/api/property/<int:property_id>", methods=["DELETE"])
@login_required
def delete_property(property_id):
    """Delete a property by ID"""
    try:
        property_to_delete = Property.query.get_or_404(property_id)
        
        # Verify ownership
        if property_to_delete.broker_id != current_user.broker_id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
            
        property_to_delete.status = 'Deleted'
        db.session.commit()
        print(f"Property {property_id} marked deleted successfully")  # Debug log
        return jsonify({'success': True, 'message': 'Property deleted successfully'})
    except Exception as e:
        print(f"Error deleting property {property_id}: {e}")  # Debug log
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/admin/api/properties/delete", methods=["POST"])
@login_required
def delete_multiple_properties():
    """Delete multiple properties by IDs"""
    data = request.get_json()
    property_ids = data.get('property_ids', [])
    
    if not property_ids:
        return jsonify({'success': False, 'message': 'No property IDs provided'}), 400
    
    try:
        deleted_count = 0
        for property_id in property_ids:
            property_to_delete = Property.query.get(property_id)
            if property_to_delete and property_to_delete.status != 'Deleted':
                # Verify ownership
                if property_to_delete.broker_id == current_user.broker_id:
                    property_to_delete.status = 'Deleted'
                    deleted_count += 1
        
        db.session.commit()
        print(f"Deleted {deleted_count} properties successfully")  # Debug log
        return jsonify({'success': True, 'message': f'{deleted_count} properties deleted successfully'})
    except Exception as e:
        print(f"Error deleting properties: {e}")  # Debug log
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/admin/api/uploaded-files", methods=["GET"])
def get_uploaded_files():
    """Get list of uploaded files"""
    files = UploadedFile.query.order_by(UploadedFile.uploaded_at.desc()).limit(20).all()
    return jsonify([{
        'id': f.id,
        'filename': f.filename,
        'file_type': f.file_type,
        'file_size': f.file_size,
        'rows_count': f.rows_count,
        'status': f.status,
        'uploaded_at': f.uploaded_at.isoformat() if f.uploaded_at else None
    } for f in files])



# ========== LEAD MANAGEMENT API ENDPOINTS ==========

@app.route("/admin/api/lead/status", methods=["POST"])  # Keep this route
@login_required
def update_lead_status():  # Keep this function name
    """Update lead status and notify user"""
    try:
        data = request.get_json()
        lead = Lead.query.get_or_404(data.get('lead_id'))
        
        # Check if lead is unassigned
        if lead.broker_id is None:
            lead.broker_id = current_user.broker_id
            print(f"📋 Lead {lead.id} assigned to broker {current_user.name}")
        
        if lead.broker_id != current_user.broker_id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        old_status = lead.status
        new_status = data.get('status')
        lead.status = new_status
        
        if new_status == 'Contacted' and old_status != 'Contacted':
            lead.contacted_at = datetime.utcnow()
        
        db.session.commit()
        
        # 🔔 NOTIFY BROKER about status change
        create_notification(
            recipient_type='broker',
            recipient_id=current_user.broker_id,
            notification_type='lead_status_change',
            title=f"📞 Lead Status Updated",
            message=f"Lead '{lead.name}' status changed from {old_status} to {new_status}",
            icon='📞',
            link='/admin/leads'
        )
        
        # 🔔 NOTIFY USER about status update
        if lead.email:
            status_messages = {
                'Contacted': "A broker has reached out to you. Check your inbox/phone!",
                'Interested': "The broker is very interested in helping you find your dream home!",
                'Converted': "Congratulations! Your inquiry has been converted. The broker will share details soon.",
                'Lost': "Unfortunately, this opportunity didn't work out. Explore other properties on NestFind."
            }
            
            user_message = status_messages.get(new_status, f"Your inquiry status has been updated to: {new_status}")
            
            create_notification(
                recipient_type='user',
                recipient_id=lead.email,
                notification_type='lead_update',
                title=f"🏠 Inquiry Update",
                message=user_message,
                icon='🏠',
                link='/'
            )
        
        # Add activity log
        add_activity(
            current_user.broker_id,
            '📞',
            f'<strong>Lead Updated</strong> — {lead.name} status changed from {old_status} to {new_status}'
        )
        
        return jsonify({'success': True, 'message': 'Lead status updated successfully'})
    except Exception as e:
        print(f"Error updating lead status: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    


@app.route("/admin/api/lead/<int:lead_id>", methods=["GET"])
@login_required
def get_lead_details(lead_id):
    """Get detailed information about a specific lead"""
    try:
        lead = Lead.query.get_or_404(lead_id)
        
        # Verify ownership
        if lead.broker_id != current_user.broker_id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        # Calculate time ago for display
        from datetime import datetime
        time_diff = datetime.utcnow() - lead.created_at
        if time_diff.days > 0:
            if time_diff.days == 1:
                time_str = "Yesterday"
            else:
                time_str = f"{time_diff.days} days ago"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            time_str = f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            time_str = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            time_str = "Just now"
        
        return jsonify({
            'id': lead.id,
            'name': lead.name,
            'email': lead.email,
            'phone': lead.phone,
            'property_name': lead.property_name,
            'property_id': lead.property_id,
            'message': lead.message,
            'source': lead.source,
            'status': lead.status,
            'interest_level': lead.interest_level,
            'time': time_str,
            'created_at': lead.created_at.isoformat() if lead.created_at else None,
            'contacted_at': lead.contacted_at.isoformat() if lead.contacted_at else None,
            'notes': lead.notes
        })
    except Exception as e:
        print(f"Error getting lead details: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== END LEAD MANAGEMENT API ENDPOINTS ==========

def add_activity(broker_id, icon, message):
    """Add an activity log entry"""
    try:
        activity = Activity(
            icon=icon,
            message=message,
            broker_id=broker_id,
            created_at=datetime.utcnow()
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        print(f"Error adding activity: {e}")
        db.session.rollback()




@app.route("/admin/leads")
@login_required
def admin_leads():
    """Dedicated leads management page"""
    if getattr(current_user, 'role', 'broker') != 'broker':
        flash('Access Denied.', 'error')
        return redirect(url_for('index'))
    
    # Get leads assigned to this broker
    assigned_leads = Lead.query.filter_by(broker_id=current_user.broker_id).order_by(Lead.created_at.desc()).all()
    
    # Get unassigned leads (available for all brokers)
    unassigned_leads = Lead.query.filter_by(broker_id=None).order_by(Lead.created_at.desc()).all()
    
    # Combine: Assigned leads first, then unassigned
    all_leads = assigned_leads + unassigned_leads
    
    # Calculate time ago for each lead
    for lead in all_leads:
        time_diff = datetime.utcnow() - lead.created_at
        if time_diff.days > 0:
            if time_diff.days == 1:
                lead.time_ago = "Yesterday"
            else:
                lead.time_ago = f"{time_diff.days} days ago"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            lead.time_ago = f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            lead.time_ago = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            lead.time_ago = "Just now"
    
    # Count leads by status
    new_count = Lead.query.filter_by(broker_id=current_user.broker_id, status='New').count()
    contacted_count = Lead.query.filter_by(broker_id=current_user.broker_id, status='Contacted').count()
    interested_count = Lead.query.filter_by(broker_id=current_user.broker_id, status='Interested').count()
    converted_count = Lead.query.filter_by(broker_id=current_user.broker_id, status='Converted').count()
    
    return render_template('admin/leads.html',
        leads=all_leads,
        new_count=new_count,
        contacted_count=contacted_count,
        interested_count=interested_count,
        converted_count=converted_count,
        admin_name=current_user.name,
        admin_initials="".join([n[0] for n in current_user.name.split()[:2]]).upper()
    )


## Notification model to store notifications for brokers and public users 
class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('brokers.broker_id'), nullable=True)  # For broker notifications
    user_email = db.Column(db.String(120), nullable=True)  # For public user notifications (by email)
    notification_type = db.Column(db.String(50), nullable=False)  # lead_new, lead_response, property_inquiry, etc.
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    icon = db.Column(db.String(50), default='🔔')
    link = db.Column(db.String(500), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    extra_data = db.Column(db.Text, nullable=True)  # JSON data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    broker = db.relationship('Broker', backref=db.backref('notifications', lazy='dynamic'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.notification_type,
            'title': self.title,
            'message': self.message,
            'icon': self.icon,
            'link': self.link,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'time_ago': self.get_time_ago()
        }
    
    def get_time_ago(self):
        if not self.created_at:
            return "Just now"
        diff = datetime.utcnow() - self.created_at
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "Just now"


class UserSession(db.Model):
    """Store anonymous user session for notifications"""
    __tablename__ = 'user_sessions'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    user_email = db.Column(db.String(120), nullable=True)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



# Add after the models
def create_notification(recipient_type, recipient_id, notification_type, title, message, icon='🔔', link=None, extra_data=None):
    """Create a notification for broker or user"""
    try:
        notification = Notification(
            notification_type=notification_type,
            title=title,
            message=message,
            icon=icon,
            link=link,
            extra_data=json.dumps(extra_data) if extra_data else None,
            is_read=False,
            created_at=datetime.utcnow()
        )
        
        if recipient_type == 'broker':
            notification.user_id = recipient_id
        elif recipient_type == 'user':
            notification.user_email = recipient_id
        
        db.session.add(notification)
        db.session.commit()
        
        # Also send email if needed (optional)
        if recipient_type == 'broker':
            send_email_notification(recipient_id, title, message)
        
        return notification
    except Exception as e:
        print(f"Error creating notification: {e}")
        db.session.rollback()
        return None


def send_email_notification(broker_id, title, message):
    """Send email notification to broker (optional)"""
    try:
        broker = Broker.query.get(broker_id)
        if broker and broker.email:
            # You can implement email sending here
            print(f"📧 Email to {broker.email}: {title}")
    except:
        pass


def get_unread_notifications_count(user_id=None, user_email=None):
    """Get unread notifications count"""
    try:
        if user_id:
            return Notification.query.filter_by(user_id=user_id, is_read=False).count()
        elif user_email:
            return Notification.query.filter_by(user_email=user_email, is_read=False).count()
        return 0
    except:
        return 0


def get_user_notifications(user_id=None, user_email=None, limit=20):
    """Get notifications for user/broker"""
    try:
        if user_id:
            return Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).limit(limit).all()
        elif user_email:
            return Notification.query.filter_by(user_email=user_email).order_by(Notification.created_at.desc()).limit(limit).all()
        return []
    except:
        return []
    


@app.route("/admin/api/property/toggle-status/<int:property_id>", methods=["POST"])
@login_required
def toggle_property_status(property_id):
    """Toggle property status between Active and Disconnected"""
    try:
        property_obj = Property.query.get_or_404(property_id)
        
        # Verify ownership
        if property_obj.broker_id != current_user.broker_id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
            
        # Treat 'Active' and 'Available' as active states
        if property_obj.status in ['Active', 'Available']:
            new_status = 'Disconnected'
        else:
            new_status = 'Active'
        
        property_obj.status = new_status
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'new_status': new_status,
            'message': f'Property is now {new_status}'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


def reset_db():
    """Reset database by dropping all tables and recreating them"""
    with app.app_context():
        try:
            print("Dropping all tables...")
            db.drop_all()
            print("Creating all tables...")
            db.create_all()
            print("[OK] Database reset successfully")
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Database reset error: {e}")


def init_db():
    """Initialize database and create tables if they don't exist"""
    with app.app_context():
        try:
            db.create_all()
            print("[OK] Database tables created/verified successfully")
            
            # Check if properties table exists and has data
            property_count = Property.query.count()
            print(f"[OK] Current properties in database: {property_count}")
            
            # Check if activities table exists and has data
            activity_count = Activity.query.count()
            print(f"[OK] Current activities in database: {activity_count}")
            
            # Check if uploaded_files table exists and has data
            files_count = UploadedFile.query.count()
            print(f"[OK] Current uploaded files in database: {files_count}")
            
        except Exception as e:
            print(f"[ERROR] Database initialization error: {e}")
            print("Please check your database configuration in .env file")
            print("The app will continue but some features may not work.")


@app.route("/api/properties-for-map")
def get_properties_for_map():
    """Get properties with coordinates for map display"""
    try:
        # Get active properties that have coordinates
        properties = Property.query.filter(
            Property.status == 'Active',
            Property.latitude.isnot(None),
            Property.longitude.isnot(None)
        ).all()
        
        map_properties = []
        for prop in properties:
            map_properties.append({
                'id': prop.id,
                'name': prop.property,
                'location': prop.location or 'Tricity Region',
                'price': prop.price,
                'lat': prop.latitude,
                'lng': prop.longitude,
                'category': prop.category
            })
        
        return jsonify(map_properties)
    except Exception as e:
        print(f"Error getting map properties: {e}")
        return jsonify([])

@app.route("/api/activities")
@login_required
def get_activities():
    """Get recent activities for current broker"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        activities = Activity.query.filter_by(broker_id=current_user.broker_id).order_by(Activity.created_at.desc()).limit(10).all()
        
        activities_data = []
        for act in activities:
            time_diff = datetime.utcnow() - act.created_at
            if time_diff.days > 0:
                if time_diff.days == 1:
                    time_str = "Yesterday"
                else:
                    time_str = f"{time_diff.days} days ago"
            elif time_diff.seconds > 3600:
                hours = time_diff.seconds // 3600
                time_str = f"{hours} hour{'s' if hours > 1 else ''} ago"
            elif time_diff.seconds > 60:
                minutes = time_diff.seconds // 60
                time_str = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
            else:
                time_str = "Just now"
            
            activities_data.append({
                'icon': act.icon,
                'message': act.message,
                'time_ago': time_str
            })
        
        return jsonify({'success': True, 'activities': activities_data})
    except Exception as e:
        print(f"Error getting activities: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@app.route("/api/advanced-search", methods=["GET"])
def advanced_search():
    """Advanced search with multiple filters"""
    try:
        query = Property.query.filter(Property.status == 'Active')
        
        # Location filter
        location = request.args.get('location', '').strip()
        if location:
            query = query.filter(
                or_(
                    Property.property.ilike(f'%{location}%'),
                    Property.location.ilike(f'%{location}%')
                )
            )
        
        # Property type filter
        property_type = request.args.get('type', '').strip()
        if property_type and property_type != 'Property Type':
            query = query.filter(
                or_(
                    Property.category.ilike(f'%{property_type}%'),
                    Property.type.ilike(f'%{property_type}%')
                )
            )
        
        # Bedrooms filter
        bedrooms = request.args.getlist('bedrooms')
        if bedrooms:
            bedroom_conditions = []
            for b in bedrooms:
                bedroom_conditions.append(Property.bedrooms.ilike(f'%{b}%'))
            query = query.filter(or_(*bedroom_conditions))
        
        # Listing type filter (For Sale / For Rent)
        listing_types = request.args.getlist('listing_type')
        if listing_types:
            type_conditions = []
            for lt in listing_types:
                type_conditions.append(Property.type.ilike(f'%{lt}%'))
            query = query.filter(or_(*type_conditions))
        
        # Category filter
        categories = request.args.getlist('category')
        if categories:
            category_conditions = []
            for cat in categories:
                category_conditions.append(Property.category.ilike(f'%{cat}%'))
            query = query.filter(or_(*category_conditions))
        
        # Price range filter
        min_price = request.args.get('min_price')
        max_price = request.args.get('max_price')
        
        properties = query.all()
        
        # Apply price and area filters (need numeric conversion)
        filtered_properties = []
        for prop in properties:
            price_num = parse_price_to_number(prop.price)
            area_num = 0
            if prop.area:
                try:
                    area_num = int(re.search(r'\d+', str(prop.area)).group()) if re.search(r'\d+', str(prop.area)) else 0
                except:
                    area_num = 0
            
            # Price filter
            if min_price and price_num < float(min_price):
                continue
            if max_price and price_num > float(max_price):
                continue
            
            # Area filter
            min_area = request.args.get('min_area')
            max_area = request.args.get('max_area')
            if min_area and area_num < float(min_area):
                continue
            if max_area and area_num > float(max_area):
                continue
            
            filtered_properties.append(prop)
        
        # Convert to response format
        default_images = {
            'Apartment': "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600",
            'Flat': "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=600",
            'Villa': "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600",
            'Commercial': "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600",
            'Plot': "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=600",
            'Studio': "https://images.unsplash.com/photo-1520637836862-4d197d17c155?w=600"
        }
        
        results = []
        for prop in filtered_properties[:50]:
            image, _ = build_image_urls(prop.image, prop.category, default_images)
            results.append({
                'id': prop.id,
                'name': prop.property,
                'location': prop.location or 'Tricity Region',
                'price': prop.price,
                'type': prop.type,
                'category': prop.category,
                'bedrooms': prop.bedrooms,
                'area': prop.area,
                'image': image
            })
        
        return jsonify({
            'success': True,
            'properties': results,
            'count': len(results)
        })
    except Exception as e:
        print(f"Advanced search error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    
@app.route("/api/current-user")
def get_current_user():
    """Get current logged-in user details"""
    try:
        if current_user.is_authenticated:
            return jsonify({
                'success': True,
                'name': current_user.name,
                'email': current_user.email,
                'phone': current_user.phone or '',
                'role': current_user.role
            })
        else:
            return jsonify({'success': False, 'message': 'Not logged in'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== TEST ROUTE FOR EMAIL ==========
@app.route('/test-yopmail')
def test_yopmail():
    from flask_mail import Message
    try:
        msg = Message('Test Email',
                      sender='saniyatanyal1@gmail.com',
                      recipients=['admin@yopmail.com'],
                      body='Plain text test email.')
        mail.send(msg)
        return "✅ Email sent to Yopmail! Check your inbox."
    except Exception as e:
        return f"❌ Error: {e}"

if __name__ == "__main__":
    import sys
    
    print("\n" + "="*50)
    print("NestFind Application Starting...")
    print("="*50)
    
    # Check for reset command
    if len(sys.argv) > 1 and sys.argv[1] == 'reset-db':
        print("Resetting database...")
        reset_db()
        print("Database reset complete. Exiting.")
        sys.exit(0)
    
    # Initialize database
    init_db()
    
    print("\n" + "="*50)
    print("Server Details:")
    print(f"  - URL: http://localhost:5000")
    print(f"  - Admin Dashboard: http://localhost:5000/admin/dashboard")
    print(f"  - File Upload API: http://localhost:5000/admin/api/upload")
    print("="*50)
    print("\nPress CTRL+C to stop the server\n")
    
    # Run the app
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"\n[ERROR] Failed to start server: {e}")
        print("Make sure you have installed all required dependencies:")
        print("  pip install flask flask-sqlalchemy python-dotenv pandas openpyxl werkzeug")
        sys.exit(1)