from app import app, db
from sqlalchemy import text

ctx = app.app_context()
ctx.push()

# Check if column already exists
try:
    db.session.execute(text("SELECT role FROM brokers LIMIT 1"))
    print("Column 'role' already exists")
except Exception as e:
    db.session.rollback()
    print("Column 'role' not found. Adding it...")
    try:
        db.session.execute(text("ALTER TABLE brokers ADD COLUMN role VARCHAR(20) DEFAULT 'broker'"))
        db.session.commit()
        print("Successfully added 'role' column.")
    except Exception as e2:
        print(f"Failed to add column: {e2}")
