#!/usr/bin/env python3
import os
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = 'myprojectdb'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = 'admin123'

from app import app, Property

with app.app_context():
    try:
        properties = Property.query.all()
        print(f"Total properties: {len(properties)}")
        print("id | property | type | price | category | status | agent | created_at")
        print("-" * 100)

        for prop in properties:
            print(f"{prop.id} | {prop.property} | {prop.type} | {prop.price} | {prop.category} | {prop.status} | {prop.agent} | {prop.created_at}")

    except Exception as e:
        print(f"Error: {e}")