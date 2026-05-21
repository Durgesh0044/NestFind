import os
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = 'myprojectdb'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = 'admin123'

from app import app

with app.app_context():
    with app.test_client() as client:
        response = client.get('/properties')
        print(f'Status: {response.status_code}')
        html = response.data.decode()
        
        if 'No properties found' in html:
            print('ERROR: Shows "No properties found" message')
        elif 'apt-card' in html:
            # Count how many property cards are shown
            count = html.count('apt-card')
            print(f'SUCCESS: Shows {count} property cards')
        else:
            print('Response snippet:')
            # Find and print relevant section
            if 'Exclusive' in html:
                start = html.find('Exclusive')
                print(html[start:start+400])
