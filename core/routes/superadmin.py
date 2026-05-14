from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user, login_required, login_user
from core.models import Broker, Property, Lead, Activity, User
from core.extensions import db
from datetime import datetime, timezone, timedelta  # CHANGED: Added timezone

superadmin_bp = Blueprint('superadmin', __name__)

# Helper function to get current UTC time (backward compatible)
def utc_now():
    """Returns current UTC datetime without timezone (naive)"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@superadmin_bp.route("/super-admin")
@login_required
def super_admin_dashboard():
    """Super Admin Dashboard - Full System Control"""
    if not current_user.is_super_admin:
        flash('Access Denied. Super Admin privileges required.', 'error')
        return redirect(url_for('superadmin.super_admin_login'))
    
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
    # FIXED: Replaced datetime.utcnow() with utc_now()
    property_trend = []
    for i in range(7, 0, -1):
        date = utc_now() - timedelta(days=i)
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


@superadmin_bp.route("/super-admin-login", methods=["GET", "POST"])
def super_admin_login():
    """Separate login page for Super Admin only"""
    
    # If already logged in as super admin, go to dashboard
    if current_user.is_authenticated and current_user.is_super_admin:
        return redirect(url_for('superadmin.super_admin_dashboard'))
    
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        
        broker = Broker.query.filter_by(email=email).first()
        
        # Check if broker exists and is SUPER ADMIN
        if broker and broker.check_password(password) and broker.is_super_admin:
            login_user(broker)
            return redirect(url_for('superadmin.super_admin_dashboard'))
        else:
            return render_template("super_admin/login.html", error="Invalid super admin credentials")
    
    return render_template("super_admin/login.html")


@superadmin_bp.route("/super-admin/brokers")
@login_required
def super_admin_brokers():
    """Super Admin - View all brokers with their stats"""
    if not current_user.is_super_admin:
        flash('Access Denied.', 'error')
        return redirect(url_for('superadmin.super_admin_login'))
    
    brokers = Broker.query.filter(
        Broker.role == 'broker',
        Broker.is_super_admin == False
    ).order_by(Broker.created_at.desc()).all()
    
    # Get stats for each broker
    broker_stats = []
    for broker in brokers:
        # Count properties
        total_properties = Property.query.filter_by(broker_id=broker.broker_id, status='Active').count()
        total_listings = Property.query.filter_by(broker_id=broker.broker_id).count()
        
        # Count leads
        total_leads = Lead.query.filter_by(broker_id=broker.broker_id).count()
        new_leads = Lead.query.filter_by(broker_id=broker.broker_id, status='New').count()
        
        # Get recent properties (last 5)
        recent_properties = Property.query.filter_by(broker_id=broker.broker_id).order_by(Property.created_at.desc()).limit(5).all()
        
        # Get recent leads (last 5)
        recent_leads = Lead.query.filter_by(broker_id=broker.broker_id).order_by(Lead.created_at.desc()).limit(5).all()
        
        broker_stats.append({
            'broker': broker,
            'total_properties': total_properties,
            'total_listings': total_listings,
            'total_leads': total_leads,
            'new_leads': new_leads,
            'recent_properties': recent_properties,
            'recent_leads': recent_leads
        })
    
    return render_template('superadmin/brokers.html',
        broker_stats=broker_stats,
        admin_name=current_user.name,
        admin_initials="".join([n[0] for n in current_user.name.split()[:2]]).upper()
    )


@superadmin_bp.route("/super-admin/properties")
@login_required
def super_admin_properties():
    """Super Admin - View all properties across platform"""
    if not current_user.is_super_admin:
        flash('Access Denied.', 'error')
        return redirect(url_for('superadmin.super_admin_login'))
    
    properties = Property.query.order_by(Property.created_at.desc()).all()
    
    return render_template('superadmin/properties.html',
        properties=properties,
        admin_name=current_user.name,
        admin_initials="".join([n[0] for n in current_user.name.split()[:2]]).upper()
    )


@superadmin_bp.route("/super-admin/leads")
@login_required
def super_admin_leads():
    """Super Admin - View all leads across platform"""
    if not current_user.is_super_admin:
        flash('Access Denied.', 'error')
        return redirect(url_for('superadmin.super_admin_login'))
    
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    
    # Calculate time ago for each lead
    # FIXED: Replaced datetime.utcnow() with utc_now()
    for lead in leads:
        time_diff = utc_now() - lead.created_at
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


@superadmin_bp.route("/super-admin/activities")
@login_required
def super_admin_activities():
    """Super Admin - View all activity logs"""
    if not current_user.is_super_admin:
        flash('Access Denied.', 'error')
        return redirect(url_for('superadmin.super_admin_login'))
    
    activities = Activity.query.order_by(Activity.created_at.desc()).limit(100).all()
    
    # Calculate time ago
    # FIXED: Replaced datetime.utcnow() with utc_now()
    for act in activities:
        time_diff = utc_now() - act.created_at
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


@superadmin_bp.route("/super-admin/broker/toggle/<int:broker_id>", methods=["POST"])
@login_required
def super_admin_toggle_broker(broker_id):
    """Super Admin - Activate/Block a broker"""
    if not current_user.is_super_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    broker = Broker.query.get_or_404(broker_id)
    broker.is_active = not broker.is_active
    db.session.commit()
    
    return jsonify({'success': True, 'is_active': broker.is_active})


@superadmin_bp.route("/super-admin/property/delete/<int:property_id>", methods=["DELETE"])
@login_required
def super_admin_delete_property(property_id):
    """Super Admin - Delete any property"""
    if not current_user.is_super_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    property_obj = Property.query.get_or_404(property_id)
    db.session.delete(property_obj)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Property deleted successfully'})


# NEW: API endpoint for viewing lead details (used by the leads.html)
@superadmin_bp.route("/admin/api/lead/<int:lead_id>")
@login_required
def admin_api_lead(lead_id):
    """API endpoint to get lead details for modal view"""
    if not current_user.is_super_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    lead = Lead.query.get_or_404(lead_id)
    
    # Calculate time
    time_diff = utc_now() - lead.created_at
    if time_diff.days > 0:
        time_ago = f"{time_diff.days} days ago"
    elif time_diff.seconds > 3600:
        hours = time_diff.seconds // 3600
        time_ago = f"{hours} hours ago"
    elif time_diff.seconds > 60:
        minutes = time_diff.seconds // 60
        time_ago = f"{minutes} minutes ago"
    else:
        time_ago = "Just now"
    
    return jsonify({
        'id': lead.id,
        'name': lead.name,
        'email': lead.email,
        'phone': lead.phone,
        'property_name': lead.property_name,
        'broker_name': lead.broker.name if lead.broker else 'Unassigned',
        'source': lead.source,
        'status': lead.status,
        'message': lead.message,
        'time': time_ago,
        'created_at': lead.created_at.strftime('%Y-%m-%d %H:%M:%S') if lead.created_at else None
    })