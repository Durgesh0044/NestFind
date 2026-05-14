import sys
import os
sys.path.append('.')
from app import app, db, Property

with app.app_context():
    # Add a property without a status
    test_prop = Property(
        property="Test Status Property",
        type="🏡 For Sale",
        price="1,00,000",
        broker_id=1 # Assuming broker 1 exists
    )
    db.session.add(test_prop)
    db.session.commit()
    
    # Check its status
    p = Property.query.filter_by(property="Test Status Property").first()
    print(f"Created property status: {p.status}")
    
    # Clean up
    db.session.delete(p)
    db.session.commit()
