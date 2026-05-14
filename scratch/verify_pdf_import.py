import sys
import os
sys.path.append('.')
from app import app, db, Property, process_pdf_file

with app.app_context():
    # Use one of the existing PDFs for testing
    pdf_path = os.path.join('static', 'uploads', '0005e864e2354d66a5d4113cab0f6ee7_property_listings.pdf')
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        sys.exit(1)
        
    # Broker ID 1 (Assuming it exists)
    result = process_pdf_file(pdf_path, 'test.pdf', 1)
    
    print(f"Import result: {result}")
    
    # Check if any new properties were added
    if result.get('success'):
        print(f"Imported {result.get('imported_count')} properties.")
