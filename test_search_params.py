import os
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = 'myprojectdb'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = 'admin123'

from app import app

with app.app_context():
    with app.test_client() as client:
        # Test 1: No filters
        print("TEST 1: No filters")
        response = client.get('/properties')
        html = response.data.decode()
        if 'No properties found' in html:
            print("  RESULT: No properties found")
        else:
            count = html.count('apt-card')
            print(f"  RESULT: {count} properties shown")
        
        # Test 2: With location filter
        print("\nTEST 2: With location='Chandigarh'")
        response = client.get('/properties?location=Chandigarh')
        html = response.data.decode()
        if 'No properties found' in html:
            print("  RESULT: No properties found")
        else:
            count = html.count('apt-card')
            print(f"  RESULT: {count} properties shown")
        
        # Test 3: With type filter
        print("\nTEST 3: With type='Apartment'")
        response = client.get('/properties?type=Apartment')
        html = response.data.decode()
        if 'No properties found' in html:
            print("  RESULT: No properties found")
        else:
            count = html.count('apt-card')
            print(f"  RESULT: {count} properties shown")
            
        # Test 4: With price range
        print("\nTEST 4: With min_price=0&max_price=100000")
        response = client.get('/properties?min_price=0&max_price=100000')
        html = response.data.decode()
        if 'No properties found' in html:
            print("  RESULT: No properties found")
        else:
            count = html.count('apt-card')
            print(f"  RESULT: {count} properties shown")
