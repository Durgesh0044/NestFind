import sqlite3
import os

db_path = 'database.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print('Tables in database:')
    for table in tables:
        print(f'  - {table[0]}')
    print()
    
    # Query properties table
    print('Properties and their status:')
    print('-' * 100)
    cursor.execute('PRAGMA table_info(property)')
    columns = cursor.fetchall()
    col_names = [col[1] for col in columns]
    print('Columns:', ', '.join(col_names))
    print()
    
    cursor.execute('SELECT * FROM property')
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    
    print(f'\nTotal properties: {len(rows)}')
    conn.close()
else:
    print('database.db not found')
