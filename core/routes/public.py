from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from sqlalchemy import or_
from core.models import Property, Broker, Lead, User
from core.extensions import db
from core.utils import build_image_urls, parse_price_to_number, landing_page_context, create_notification
from datetime import datetime
import json

public_bp = Blueprint('public', __name__)

@public_bp.route("/api/property/<property_id>", methods=["GET"])
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


@public_bp.route("/property/<int:property_id>")
def property_detail(property_id):
    """Public property detail page - shareable link for customers"""
    try:
        property_obj = Property.query.get_or_404(property_id)
        
        # Only show Active properties to public
        if property_obj.status != 'Active':
            flash('This property is no longer available.', 'warning')
            return redirect(url_for('public.index'))
        
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
        return redirect(url_for('public.index'))


@public_bp.route("/")
def index():
    return render_template("index.html", **landing_page_context())


@public_bp.route("/search")
def search():
    return render_template("index.html", **landing_page_context())


@public_bp.route("/property/<type>")
def property_type(type):
    return render_template("index.html", **landing_page_context())


@public_bp.route("/portfolio/<int:broker_id>")
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
        
        # Only show Active properties for this specific broker, sorted by Featured status first
        broker_props = Property.query.filter_by(broker_id=broker_id, status='Active').order_by(Property.is_featured.desc(), Property.created_at.desc()).all()
        
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
                'featured': getattr(prop, 'is_featured', False),
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
        return redirect(url_for('public.index'))


@public_bp.route("/properties")
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
        
        print(f"SEARCH PARAMS: location={location}, type={property_type}, min_price={min_price}, max_price={max_price}")
        
        # ========== 1. LOCATION FILTER ==========
        if location:
            query = query.filter(
                or_(
                    Property.property.ilike(f'%{location}%'),
                    Property.location.ilike(f'%{location}%')
                )
            )
            print(f"Location filter applied: {location}")
        
        # ========== 2. PROPERTY TYPE FILTER ==========
        if property_type and property_type != '':
            query = query.filter(
                or_(
                    Property.category.ilike(f'%{property_type}%'),
                    Property.type.ilike(f'%{property_type}%')
                )
            )
            print(f"Type filter applied: {property_type}")
        
        # ========== 3. LISTING TYPE FILTER (Sale/Rent) - FIXED ==========
        if listing_type_param and listing_type_param != '':
            # Split multiple values (e.g., "For Sale,For Rent")
            listing_types = listing_type_param.split(',')
            
            # Create OR conditions for each listing type
            type_conditions = []
            for lt in listing_types:
                lt = lt.strip()
                if lt:
                    type_conditions.append(Property.type.ilike(f'%{lt}%'))
            
            if type_conditions:
                query = query.filter(or_(*type_conditions))
                print(f"📋 Listing type filter applied: {listing_types}")
        
        # Get all properties after basic filters, sorted by Featured first!
        properties = query.order_by(Property.is_featured.desc(), Property.created_at.desc()).all()
        
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
                    max_val = float(max_price)
                    if max_val > 0 and price_num > max_val:
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
        
        print(f"Found {len(filtered_properties)} properties after all filters")
        
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
                        image_list = [url_for('admin.uploaded_file', filename=f) for f in imgs]
                        image_url = image_list[0]
                    else:
                        image_url = url_for('admin.uploaded_file', filename=prop.image)
                        image_list = [image_url]
                except:
                    image_url = url_for('admin.uploaded_file', filename=prop.image)
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
                'featured': getattr(prop, 'is_featured', False),
                'broker_name': prop.broker_info.name if prop.broker_info else 'NestFind Agent',
                'broker_phone': prop.broker_info.phone if prop.broker_info else '+91 00000 00000',
                'image': image_url,
                'images': image_list
            })
        
        return render_template("properties.html", properties=display_properties)
        
    except Exception as e:
        print(f"Error loading properties page: {e}")
        import traceback
        traceback.print_exc()
        return render_template("properties.html", properties=[])


@public_bp.route("/subscribe", methods=["POST"])
def subscribe_newsletter():
    return "Subscribed!"  # Simple response for now


@public_bp.route("/contact", methods=["POST"])
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

        print(f"Contact Form Submission:")
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
            print(f"Duplicate submission detected for {email} - ignoring")
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
        
        print(f"Lead created with ID: {lead.id}")
        
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
                print(f"Notification sent to broker {broker_id}")
            except Exception as notify_error:
                print(f"Failed to send notification: {notify_error}")
                
        else:
            print(f"No broker_id provided - sending to Super Admin instead")
            
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
                        print(f"Notification sent to Super Admin: {admin.name} (ID: {admin.broker_id})")
                    except Exception as e:
                        print(f"Failed to notify super admin: {e}")
            else:
                print(f"No Super Admin found! Create a super admin first.")
        
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
                print(f"User notification sent to {email}")
            except Exception as user_notify_error:
                print(f"Failed to send user notification: {user_notify_error}")
        
        return jsonify({'success': True, 'message': 'Thank you for contacting us! We will get back to you soon.'})

    except Exception as e:
        db.session.rollback()
        print(f"Error saving contact: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'}), 500


@public_bp.route("/compare")
def compare_properties():
    """Property comparison page"""
    return render_template("compare.html")


@public_bp.route('/test-yopmail')
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


@public_bp.route("/test")
def test_route():
    return jsonify({'message': 'Test route works'})


