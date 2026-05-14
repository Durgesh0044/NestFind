from datetime import datetime, timezone  # CHANGED: Added timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from core.extensions import db

# Helper function to get current UTC time (backward compatible)
def utc_now():
    """Returns current UTC datetime without timezone (naive)"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    wallet_balance = db.Column(db.Float, default=0.0, server_default='0.0')  # Broker Credit Balance
    created_at = db.Column(db.DateTime, default=utc_now)  # CHANGED: from datetime.utcnow
    
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


class UserFavorite(db.Model):
    __tablename__ = 'user_favorites'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('brokers.broker_id'), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)  # CHANGED: from datetime.utcnow
    
    # Relationships
    user = db.relationship('Broker', backref='favorites')
    property = db.relationship('Property', backref='favorited_by')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'property_id', name='unique_user_property_favorite'),
    )


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    looking_for = db.Column(db.String(100))
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now)  # CHANGED: from datetime.utcnow


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
    created_at = db.Column(db.DateTime, default=utc_now)  # CHANGED: from datetime.utcnow
    
    # ADD THESE TWO LINES:
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    is_featured = db.Column(db.Boolean, default=False, server_default='false')  # Broadcast status


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
    uploaded_at = db.Column(db.DateTime, default=utc_now)  # CHANGED: from datetime.utcnow


class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    icon = db.Column(db.String(10))
    message = db.Column(db.String(500))
    # time_ago = db.Column(db.String(50))
    broker_id = db.Column(db.Integer, db.ForeignKey('brokers.broker_id'), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)  # CHANGED: from datetime.utcnow


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
    created_at = db.Column(db.DateTime, default=utc_now)  # CHANGED: from datetime.utcnow
    contacted_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text)
    is_unlocked = db.Column(db.Boolean, default=False, server_default='false')  # Lead paid reveal status
    
    # Relationships
    property = db.relationship('Property', backref='leads')
    broker = db.relationship('Broker', backref='leads')


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
    created_at = db.Column(db.DateTime, default=utc_now)  # CHANGED: from datetime.utcnow
    
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
        # CHANGED: Use utc_now() instead of datetime.utcnow()
        diff = utc_now() - self.created_at
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
    last_activity = db.Column(db.DateTime, default=utc_now)  # CHANGED: from datetime.utcnow
    created_at = db.Column(db.DateTime, default=utc_now)  # CHANGED: from datetime.utcnow


class WalletTransaction(db.Model):
    __tablename__ = 'wallet_transactions'
    id = db.Column(db.Integer, primary_key=True)
    broker_id = db.Column(db.Integer, db.ForeignKey('brokers.broker_id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # 'credit' or 'debit'
    description = db.Column(db.String(255), nullable=False)
    stripe_session_id = db.Column(db.String(255), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)  # CHANGED: from datetime.utcnow
    
    broker = db.relationship('Broker', backref=db.backref('transactions', order_by="desc(WalletTransaction.created_at)"))