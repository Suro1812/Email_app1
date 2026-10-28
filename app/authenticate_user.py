"""
Authentication script for new users.
Run this to authenticate a new Gmail user and save their credentials to the database.
"""

import asyncio

from app.core.auth import authenticate_user_oauth

if __name__ == "__main__":
    print("Starting Gmail authentication for new user...")
    print("A browser window will open for you to log in with your Gmail account.\n")

    try:
        email, _creds = asyncio.run(authenticate_user_oauth())
        print("\n✓ Authentication successful!")
        print(f"✓ User {email} has been added to the database")
        print("✓ You can now use the Gmail API with this email address")

    except Exception as e:
        print(f"ERROR: Authentication failed: {e}")
        exit(1)
