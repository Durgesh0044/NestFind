from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from flask_login import current_user, login_required
from sqlalchemy import or_
from core.models import UserFavorite, Property, Broker, Notification, Activity
from core.extensions import db
from core.utils import build_image_urls, create_notification, get_user_notifications, get_unread_notifications_count, parse_price_to_number
from datetime import datetime
import re

api_bp = Blueprint('api', __name__)

@api_bp.route("/api/favorites/toggle", methods=["POST"])
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


@api_bp.route("/api/favorites/check", methods=["GET"])
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


@api_bp.route("/api/favorites/list", methods=["GET"])
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


@api_bp.route("/user-favorites")
@login_required
def user_favorites():
    """Public user favorites page"""
    # Only for buyers/regular users, not brokers
    if current_user.role == 'broker':
        return redirect(url_for('api.favorites_page'))
    
    return render_template('user_favorites.html',
        user_name=current_user.name,
        user_initials="".join([n[0] for n in current_user.name.split()[:2]]).upper()
    )


@api_bp.route("/favorites")
@login_required
def favorites_page():
    """Favorites page for users"""
    if getattr(current_user, 'role', 'broker') != 'broker':
        flash('Please login as broker to access favorites', 'warning')
        return redirect(url_for('auth.signin'))
    
    return render_template('favorites.html',
        admin_name=current_user.name,
        admin_initials="".join([n[0] for n in current_user.name.split()[:2]]).upper()
    )


@api_bp.route("/api/favorites/remove", methods=["POST"])
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


@api_bp.route("/api/similar-properties/<int:property_id>")
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


@api_bp.route("/api/notifications")
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


@api_bp.route("/api/notifications/mark-read", methods=["POST"])
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


@api_bp.route("/api/budget-ranges", methods=["GET"])
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


@api_bp.route("/api/properties-for-map")
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


@api_bp.route("/api/activities")
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


@api_bp.route("/api/advanced-search", methods=["GET"])
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
            if max_price:
                max_val = float(max_price)
                if max_val > 0 and price_num > max_val:
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


@api_bp.route("/api/current-user")
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


