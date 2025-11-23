#!/usr/bin/env python3
"""
Reset admin user password to a custom value
"""
import sys
import bcrypt
import getpass

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

# Get password from user
print("Reset Admin Password")
print("=" * 40)
new_password = getpass.getpass("Enter new password for admin: ")
confirm_password = getpass.getpass("Confirm password: ")

if new_password != confirm_password:
    print("❌ Passwords do not match!")
    sys.exit(1)

if len(new_password) < 4:
    print("❌ Password must be at least 4 characters!")
    sys.exit(1)

# Hash the password
hashed_password = hash_password(new_password)

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
    print("✅ Admin password updated successfully!")
else:
    # Create new admin user
    cursor.execute(
        "INSERT INTO users (username, hashed_password, is_active) VALUES (?, ?, ?)",
        ('admin', hashed_password, True)
    )
    print("✅ Admin user created successfully!")

conn.commit()
conn.close()

print("\nYou can now log in with:")
print("  Username: admin")
print("  Password: (the password you just set)")
