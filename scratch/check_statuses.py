from app import app, db, Property

with app.app_context():
    properties = Property.query.all()
    status_counts = {}
    for p in properties:
        status_counts[p.status] = status_counts.get(p.status, 0) + 1
    
    print(f"Total properties: {len(properties)}")
    print("Status counts:")
    for status, count in status_counts.items():
        print(f"  - {status}: {count}")
