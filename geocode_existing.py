from app import app, db, Property
import requests
import time
import sys

def geocode_address(address):
    """Convert address to latitude and longitude"""
    if not address:
        return None, None
    
    try:
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
                return lat, lon
        return None, None
            
    except Exception as e:
        print(f"Error: {e}")
        return None, None

def geocode_existing_properties():
    with app.app_context():
        # Get properties that don't have coordinates
        properties = Property.query.filter(
            Property.latitude.is_(None),
            Property.status == 'Active'
        ).all()
        
        print(f"\n📊 Found {len(properties)} properties to geocode...\n")
        
        updated = 0
        failed = 0
        
        for prop in properties:
            if prop.location:
                print(f"📍 Geocoding: {prop.property} - {prop.location}")
                lat, lon = geocode_address(prop.location)
                
                if lat and lon:
                    prop.latitude = lat
                    prop.longitude = lon
                    updated += 1
                    print(f"   ✅ Success! ({lat}, {lon})")
                else:
                    failed += 1
                    print(f"   ❌ Failed - No coordinates found")
                
                time.sleep(1)  # Wait 1 second between requests (be nice to the API)
            else:
                failed += 1
                print(f"⚠️ {prop.property} - No location provided")
        
        db.session.commit()
        
        print(f"\n{'='*50}")
        print(f"✅ Geocoding Complete!")
        print(f"   Updated: {updated} properties")
        print(f"   Failed: {failed} properties")
        print(f"{'='*50}\n")

if __name__ == "__main__":
    geocode_existing_properties()