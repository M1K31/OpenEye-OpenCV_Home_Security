#!/usr/bin/env python3
"""
Create or update test admin user for E2E tests
"""
import sys
import bcrypt

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

# Hash the password
hashed_password = hash_password('admin')
print(f"Hashed password: {hashed_password}")

# Update the database
import sqlite3
conn = sqlite3.connect('surveillance.db')
cursor = conn.cursor()

# Check if admin user exists
cursor.execute("SELECT id FROM users WHERE username = 'admin'")
existing_user = cursor.fetchone()

if existing_user:
    # Update existing admin user's password
    cursor.execute(
        "UPDATE users SET hashed_password = ? WHERE username = 'admin'",
        (hashed_password,)
    )
    print("✓ Updated admin user password to 'admin'")
else:
    # Create new admin user
    cursor.execute(
        "INSERT INTO users (username, hashed_password, is_active) VALUES (?, ?, ?)",
        ('admin', hashed_password, True)
    )
    print("✓ Created new admin user with password 'admin'")

conn.commit()
conn.close()

print("\nAdmin credentials:")
print("  Username: admin")
print("  Password: admin")
