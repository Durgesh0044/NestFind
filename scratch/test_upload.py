import io
from app import app, db, Broker
import json

app.config['TESTING'] = True

with app.app_context():
    broker = Broker.query.filter_by(role='broker').first()
    bid = broker.broker_id
    email = broker.email
    print(f'Using broker: {broker.name} | email: {email} | id: {bid}')

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['_user_id'] = str(bid)

    csv_bytes = b'property,price,area,bedrooms,category,type\nSunrise Villa,80 Lakhs,2000 sq ft,3 BHK,Villa,For Sale\nBlue Apt,35 Lakhs,900 sq ft,2 BHK,Apartment,For Rent'

    resp = client.post('/admin/api/upload',
        data={'type': 'csv', 'file': (io.BytesIO(csv_bytes), 'listings.csv')},
        content_type='multipart/form-data'
    )
    print('HTTP Status:', resp.status_code)
    print('Content-Type:', resp.content_type)
    j = resp.get_json()
    print('JSON response:', json.dumps(j, indent=2))
    print()
    if j and j.get('success'):
        print('SUCCESS:', j.get('imported_count'), 'properties imported')
    else:
        print('FAILURE:', j)
