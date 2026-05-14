from flask import url_for
import re
from datetime import datetime, timedelta
import requests
import json
import uuid
import os
import csv
import pandas as pd
import pdfplumber
from core.extensions import db
from core.models import Property, Broker, Lead, UploadedFile, Activity, Notification

def load_user(user_id):
    return Broker.query.get(int(user_id))


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

        # Only show Active properties on homepage, ordering by premium Featured status first!
        properties = Property.query.filter_by(status='Active').order_by(Property.is_featured.desc(), Property.created_at.desc()).limit(6).all()
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
            featured = getattr(prop, 'is_featured', False)
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
        return url_for('admin.uploaded_file', filename=img_str)

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


