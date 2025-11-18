#!/usr/bin/env python3
"""
Initialize SQLite database with schema for AgentFleet.
Creates tables for jobs and incidents with proper indexes.
"""

import sqlite3
import os
from pathlib import Path


def init_database(db_path: str = "./agentfleet.db"):
    """
    Initialize the AgentFleet database with required schema.
    
    Args:
        db_path: Path to the SQLite database file
    """
    # Ensure the directory exists
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    
    # Connect to database (creates file if it doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            incident_id TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            result JSON
        )
    """)
    
    # Create incidents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id TEXT PRIMARY KEY,
            summary TEXT NOT NULL,
            severity TEXT NOT NULL,
            priority_score REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            full_data JSON NOT NULL
        )
    """)
    
    # Create indexes for efficient queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_incidents_severity 
        ON incidents(severity)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_incidents_status 
        ON incidents(status)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_status 
        ON jobs(status)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_incidents_created_at 
        ON incidents(created_at DESC)
    """)
    
    # Commit changes
    conn.commit()
    
    print(f"✓ Database initialized successfully at: {db_path}")
    print(f"✓ Created tables: jobs, incidents")
    print(f"✓ Created indexes: idx_incidents_severity, idx_incidents_status, idx_jobs_status, idx_incidents_created_at")
    
    # Close connection
    conn.close()


if __name__ == "__main__":
    # Default path relative to the data directory
    db_path = os.getenv("DATABASE_PATH", "./agentfleet.db")
    init_database(db_path)
