from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_from_directory
import os
import stripe
import uuid
import json
import pandas as pd
from datetime import datetime
from werkzeug.utils import secure_filename
from flask_login import current_user, login_required
from core.models import Property, Broker, Lead, UploadedFile, Activity, WalletTransaction
from core.extensions import db
from sqlalchemy import or_
import traceback
from core.utils import (
    get_admin_dashboard_data, add_activity, create_notification, 
    process_csv_file, process_excel_file, process_pdf_file, 
    build_image_urls, parse_price_to_number, get_file_size_mb,
    allowed_file, geocode_address
)

# Configure Stripe API Key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif',
    'webp', 'bmp', 'jfif',
    'pdf', 'csv', 'xlsx', 'xls'
}

ALLOWED_IMAGE_EXTS = {
    'jpg', 'jpeg', 'png',
    'gif', 'webp', 'bmp', 'jfif'
}

admin_bp = Blueprint('admin', __name__)

@admin_bp.route("/admin/api/property/update-status/<int:property_id>", methods=["POST"])
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


@admin_bp.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if getattr(current_user, 'role', 'broker') != 'broker':
        flash('Access Denied. You must be a broker to access the dashboard.', 'error')
        return redirect(url_for('public.index'))
    # Get all dashboard data for current broker
    dashboard_data = get_admin_dashboard_data(current_user.broker_id)
    
    return render_template("admin/dashboard.html", **dashboard_data)


@admin_bp.route("/admin/api/upload", methods=["POST"])
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
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    
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


@admin_bp.route("/admin/api/property", methods=["POST"])
@login_required
def add_property():
    """Add a new property via AJAX"""
    data = request.form
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
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
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


@admin_bp.route("/admin/api/properties", methods=["GET"])
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


@admin_bp.route("/admin/api/property-with-image", methods=["POST"])
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
        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)

        for image_file in image_files:
            if not image_file or not image_file.filename:
                continue
            original_name = secure_filename(image_file.filename)
            ext = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else ''
            if ext not in ALLOWED_IMAGE_EXTS:
                continue
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
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
                pdf_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], brochure_filename))

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


@admin_bp.route("/admin/api/upload-image", methods=["POST"])
def upload_image():
    """Upload image for property update"""
    try:
        if 'image' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No image file provided'
            }), 400

        image_file = request.files['image']

        if not image_file or not image_file.filename:
            return jsonify({
                'success': False,
                'message': 'No image file selected'
            }), 400

        filename = secure_filename(image_file.filename)

        if '.' not in filename:
            return jsonify({
                'success': False,
                'message': 'Invalid file'
            }), 400

        ext = filename.rsplit('.', 1)[1].lower()

        if ext not in ALLOWED_IMAGE_EXTS:
            return jsonify({
                'success': False,
                'message': f'File type .{ext} not allowed'
            }), 400

        unique_filename = f"{uuid.uuid4().hex}.{ext}"

        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)

        image_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            unique_filename
        )

        image_file.save(image_path)

        return jsonify({
            'success': True,
            'filename': unique_filename
        })

    except Exception as e:
        traceback.print_exc()

        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@admin_bp.route("/admin/api/upload-images", methods=["POST"])
def upload_images():
    """Upload multiple images for property update"""
    try:
        if 'images[]' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No image files provided'
            }), 400

        image_files = request.files.getlist('images[]')

        if not image_files or len(image_files) == 0:
            return jsonify({
                'success': False,
                'message': 'No image files selected'
            }), 400

        uploaded_filenames = []

        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)

        for image_file in image_files:

            if not image_file or not image_file.filename:
                continue

            filename = secure_filename(image_file.filename)

            if '.' not in filename:
                continue

            ext = filename.rsplit('.', 1)[1].lower()

            if ext not in ALLOWED_IMAGE_EXTS:
                continue

            unique_filename = f"{uuid.uuid4().hex}.{ext}"

            image_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'],
                unique_filename
            )

            image_file.save(image_path)

            uploaded_filenames.append(unique_filename)

        if not uploaded_filenames:
            return jsonify({
                'success': False,
                'message': 'No valid images uploaded'
            }), 400

        return jsonify({
            'success': True,
            'filenames': uploaded_filenames
        })

    except Exception as e:
        traceback.print_exc()

        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@admin_bp.route('/static/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@admin_bp.route("/api/search", methods=["GET"])
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


@admin_bp.route("/admin/api/property/<int:property_id>", methods=["GET"])
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


@admin_bp.route("/admin/api/property/<int:property_id>", methods=["PUT"])
@login_required
def update_property(property_id):
    """Update a property by ID"""
    try:
        property_obj = Property.query.get_or_404(property_id)
        
        # Verify ownership
        if property_obj.broker_id != current_user.broker_id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
            
        data = request.get_json(silent=True) or request.form.to_dict()
        
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


@admin_bp.route("/admin/api/property/<int:property_id>", methods=["DELETE"])
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


@admin_bp.route("/admin/api/properties/delete", methods=["POST"])
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


@admin_bp.route("/admin/api/uploaded-files", methods=["GET"])
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


@admin_bp.route("/admin/api/lead/status", methods=["POST"])  # Keep this route
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


@admin_bp.route("/admin/api/lead/<int:lead_id>", methods=["GET"])
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


@admin_bp.route("/admin/leads")
@login_required
def admin_leads():
    """Dedicated leads management page"""
    if getattr(current_user, 'role', 'broker') != 'broker':
        flash('Access Denied.', 'error')
        return redirect(url_for('public.index'))
    
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


@admin_bp.route("/admin/api/property/toggle-status/<int:property_id>", methods=["POST"])
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




# ==========================================
#           WALLET & PREMIUM ROUTES
# ==========================================

@admin_bp.route("/admin/wallet")
@login_required
def admin_wallet():
    """Display wallet and transactions history"""
    if getattr(current_user, 'role', 'broker') != 'broker':
        flash('Access Denied.', 'error')
        return redirect(url_for('public.index'))
        
    transactions = WalletTransaction.query.filter_by(broker_id=current_user.broker_id).order_by(WalletTransaction.created_at.desc()).all()
    
    admin_initials = current_user.name[:2].upper() if current_user.name else "BR"
    admin_name = current_user.name or "Broker"
    
    # Required fields to maintain layout
    new_leads_count = Lead.query.filter_by(broker_id=current_user.broker_id, status='New').count()
    
    return render_template(
        'admin/wallet.html', 
        transactions=transactions,
        admin_initials=admin_initials,
        admin_name=admin_name,
        new_leads_count=new_leads_count
    )

@admin_bp.route("/admin/api/stripe/create-checkout-session", methods=["POST"])
@login_required
def create_checkout_session():
    """Generates a Stripe checkout session for depositing funds"""
    try:
        if not stripe.api_key:
            stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
            
        data = request.get_json() or {}
        amount = float(data.get('amount', 0))
        
        if amount < 50:
            return jsonify({'success': False, 'message': 'Minimum deposit amount is ₹50 to satisfy processing gateways'}), 400
            
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'inr',
                    'product_data': {
                        'name': 'NestFind Broker Wallet Deposit',
                        'description': f'Crediting ₹{amount:,.2f} to balance',
                    },
                    'unit_amount': int(amount * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=request.url_root.rstrip('/') + url_for('admin.stripe_success') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.url_root.rstrip('/') + url_for('admin.admin_wallet') + '?error=cancelled',
            metadata={
                'broker_id': current_user.broker_id,
                'amount': str(amount)
            }
        )
        
        return jsonify({'success': True, 'session_id': checkout_session.id, 'checkout_url': checkout_session.url})
    except Exception as e:
        print(f"Stripe session error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route("/admin/stripe/success")
@login_required
def stripe_success():
    """Handles post-stripe success callback and credits balance safely"""
    session_id = request.args.get('session_id')
    if not session_id:
        flash("Invalid Stripe callback.", "error")
        return redirect(url_for('admin.admin_wallet'))
        
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status != "paid":
            flash("Stripe payment could not be verified.", "error")
            return redirect(url_for('admin.admin_wallet'))
            
        existing_txn = WalletTransaction.query.filter_by(stripe_session_id=session_id).first()
        if existing_txn:
            flash("Funds have already been credited for this transaction.", "info")
            return redirect(url_for('admin.admin_wallet'))
            
        session_dict = session.to_dict()
        metadata = session_dict.get('metadata', {})
        amount = float(metadata.get('amount', 0))
        broker = Broker.query.get(current_user.broker_id)
        
        broker.wallet_balance = (broker.wallet_balance or 0.0) + amount
        
        txn = WalletTransaction(
            broker_id=current_user.broker_id,
            amount=amount,
            transaction_type='credit',
            description=f'Deposit via Stripe (₹{amount:,.2f})',
            stripe_session_id=session_id
        )
        
        add_activity(broker.broker_id, '💳', f"Successfully deposited ₹{amount} via Stripe")
        
        db.session.add(txn)
        db.session.commit()
        
        flash(f"Payment Successful! ₹{amount:,.2f} credited to your wallet.", "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"Stripe verify callback error: {e}")
        flash(f"An error occurred crediting funds: {e}", "error")
        
    return redirect(url_for('admin.admin_wallet'))

@admin_bp.route("/admin/api/property/broadcast/<int:property_id>", methods=["POST"])
@login_required
def broadcast_property(property_id):
    """Charges 200 to broadcast property to top listing / featured banner"""
    try:
        prop = Property.query.get_or_404(property_id)
        
        if prop.broker_id != current_user.broker_id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
            
        if prop.is_featured:
            return jsonify({'success': False, 'message': 'Property is already broadcasted!'}), 400
            
        BROADCAST_COST = 200.00
        broker = Broker.query.get(current_user.broker_id)
        
        if (broker.wallet_balance or 0.0) < BROADCAST_COST:
            return jsonify({'success': False, 'message': 'Insufficient funds. Please add credits to your wallet.'}), 402
            
        # Deduct amount
        broker.wallet_balance -= BROADCAST_COST
        prop.is_featured = True
        
        # Create transaction record
        txn = WalletTransaction(
            broker_id=current_user.broker_id,
            amount=BROADCAST_COST,
            transaction_type='debit',
            description=f"Broadcasted Property: {prop.property}"
        )
        
        db.session.add(txn)
        db.session.commit()  # IMPORTANT: Commit the changes
        
        # Add activity after commit
        add_activity(current_user.broker_id, '📣', f"Broadcasted '{prop.property}' for ₹{BROADCAST_COST}")
        
        print(f"✅ Broadcast successful! Property {prop.id} is now featured. New balance: {broker.wallet_balance}")
        
        return jsonify({
            'success': True,
            'message': f'Successfully broadcasted! Property promoted to the top.',
            'new_balance': broker.wallet_balance
        })
    except Exception as e:
        db.session.rollback()
        print(f"❌ Broadcast error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
    


@admin_bp.route("/admin/api/lead/unlock/<int:lead_id>", methods=["POST"])
@login_required
def unlock_lead(lead_id):
    """Charges 50 to unlock full contact information for a lead"""
    try:
        lead = Lead.query.get_or_404(lead_id)
        
        # Check if lead already unlocked by this broker
        if lead.is_unlocked and lead.broker_id == current_user.broker_id:
            return jsonify({'success': False, 'message': 'Lead already unlocked!'}), 400
        
        UNLOCK_COST = 50.00
        broker = Broker.query.get(current_user.broker_id)
        
        print(f"🔓 Unlock Lead Request")
        print(f"Lead ID: {lead_id}, Customer: {lead.name}")
        print(f"Broker: {broker.name}, Wallet balance: ₹{broker.wallet_balance}")
        
        if (broker.wallet_balance or 0.0) < UNLOCK_COST:
            return jsonify({'success': False, 'message': f'Insufficient funds. Need ₹{UNLOCK_COST}. Current balance: ₹{broker.wallet_balance}'}), 402
        
        # Deduct from wallet
        broker.wallet_balance -= UNLOCK_COST
        
        # Mark lead as unlocked and assign to broker
        lead.is_unlocked = True
        if not lead.broker_id:
            lead.broker_id = current_user.broker_id
        
        # Create transaction record
        txn = WalletTransaction(
            broker_id=current_user.broker_id,
            amount=UNLOCK_COST,
            transaction_type='debit',
            description=f"Unlocked Lead Contact: {lead.name}"
        )
        
        db.session.add(txn)
        db.session.commit()
        
        print(f"✅ Lead unlocked! New balance: ₹{broker.wallet_balance}")
        
        return jsonify({
            'success': True,
            'message': 'Lead contact unlocked successfully!',
            'new_balance': broker.wallet_balance,
            'contact_info': {
                'email': lead.email,
                'phone': lead.phone or 'N/A'
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Unlock error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

