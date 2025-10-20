#!/usr/bin/env python3
"""
Create Admin User Script
Creates an admin user for testing/recovery purposes

Usage:
    python create_admin_user.py
"""

from backend.database.session import SessionLocal
from backend.database.models import User
from backend.core.auth import hash_password
import sys


def create_admin():
    """Create admin user interactively"""
    print("=" * 60)
    print("OpenEye - Create Admin User")
    print("=" * 60)
    print()

    # Get user input
    username = input("Enter username (default: admin): ").strip() or "admin"
    email = input("Enter email (default: admin@openeye.local): ").strip() or "admin@openeye.local"
    password = input("Enter password (default: admin123): ").strip() or "admin123"

    print()
    print("Creating user with:")
    print(f"  Username: {username}")
    print(f"  Email: {email}")
    print(f"  Password: {'*' * len(password)}")
    print()

    confirm = input("Continue? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return

    # Create user
    db = SessionLocal()
    try:
        # Check if user already exists
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"\n✗ User '{username}' already exists!")
            print(f"  ID: {existing.id}")
            print(f"  Role: {existing.role}")
            print(f"  Active: {existing.is_active}")

            update = input("\nUpdate password for this user? (y/N): ").strip().lower()
            if update == 'y':
                existing.hashed_password = hash_password(password)
                existing.is_active = True
                db.commit()
                print(f"\n✓ Password updated for '{username}'")
            return

        # Create new user
        hashed_pw = hash_password(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_pw,
            role="admin",
            is_active=True
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"\n✓ Admin user created successfully!")
        print(f"  ID: {user.id}")
        print(f"  Username: {user.username}")
        print(f"  Email: {user.email}")
        print(f"  Role: {user.role}")
        print()
        print("You can now log in at: http://localhost:8000")

    except Exception as e:
        db.rollback()
        print(f"\n✗ Error creating user: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
