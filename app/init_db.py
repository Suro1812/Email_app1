"""
Initialize the database and create tables.
Run this once to set up PostgreSQL.
"""

from app.core.database import init_db

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("✓ Database tables created successfully!")
    print("You can now run your Gmail MCP server.")