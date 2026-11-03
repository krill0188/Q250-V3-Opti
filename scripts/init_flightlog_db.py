#!/usr/bin/env python3
"""
Initialize Flight Log Database for Q250-V3-Opti

Creates SQLite database with multi-modal flight log schema.
Based on references/flightlog-schema.sql
"""

import sqlite3
from pathlib import Path
import sys


def init_database(db_path: str) -> None:
    """Initialize the flight log database with all tables and indexes."""
    schema_path = Path(__file__).parent.parent / "references" / "flightlog-schema.sql"

    if not schema_path.exists():
        print(f"Schema file not found: {schema_path}")
        sys.exit(1)

    with open(schema_path, "r") as f:
        schema_sql = f.read()

    # Split by semicolon (simple approach, works for this schema)
    statements = [s.strip() for s in schema_sql.split(";") if s.strip()]

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"Initializing database: {db_path}")
    print(f"Executing {len(statements)} statements...")

    for i, stmt in enumerate(statements, 1):
        try:
            cursor.execute(stmt)
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(statements)}")
        except sqlite3.Error as e:
            print(f"Error in statement {i}: {e}")
            print(f"Statement: {stmt[:100]}...")
            conn.rollback()
            raise

    conn.commit()

    # Verify tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    print(f"\nCreated {len(tables)} tables:")
    for table in tables:
        print(f"  - {table[0]}")

    # Verify indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
    indexes = cursor.fetchall()
    print(f"\nCreated {len(indexes)} indexes")

    conn.close()
    print("\nDatabase initialization complete!")


def verify_database(db_path: str) -> None:
    """Verify database structure and constraints."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check foreign key constraints
    cursor.execute("PRAGMA foreign_keys")
    fk = cursor.fetchone()
    print(f"Foreign keys enabled: {fk[0]}")

    # Check table counts
    cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        cols = cursor.fetchall()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"{table}: {len(cols)} columns, {count} rows")

    conn.close()


if __name__ == "__main__":
    db_path = "/Users/amaster/projectm/Q250-V3-Opti/flight_logs/db/flightlog.db"

    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    # Enable foreign keys
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()

    init_database(db_path)
    print("\n" + "=" * 50)
    verify_database(db_path)
