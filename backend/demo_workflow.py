#!/usr/bin/env python3
"""
Demo script to create example workflows for testing
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.database import Base, Workflow
import json

# Database setup - use project root data directory
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "workflows.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.absolute()}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_example_workflows():
    """Create some example workflows for demonstration"""
    
    db = SessionLocal()
    
    # Example 1: Simple Text Typing Workflow
    workflow1 = Workflow(
        name="Type Hello World",
        description="A simple workflow that types 'Hello World' in a text editor",
        steps_json=json.dumps([
            {
                "action": "type",
                "text": "Hello, World!",
                "description": "Type greeting message",
                "timestamp": "2024-01-01T12:00:00"
            },
            {
                "action": "hotkey",
                "keys": ["enter"],
                "description": "Press Enter",
                "timestamp": "2024-01-01T12:00:01"
            },
            {
                "action": "type",
                "text": "This is a demo workflow from AGI Assistant.",
                "description": "Type description",
                "timestamp": "2024-01-01T12:00:02"
            }
        ])
    )
    
    # Example 2: Click and Type Workflow
    workflow2 = Workflow(
        name="Open and Search",
        description="Demonstrates clicking and typing actions",
        steps_json=json.dumps([
            {
                "action": "click",
                "x": 500,
                "y": 300,
                "button": "left",
                "description": "Click on search box",
                "timestamp": "2024-01-01T12:01:00"
            },
            {
                "action": "wait",
                "duration": 0.5,
                "description": "Wait for focus",
                "timestamp": "2024-01-01T12:01:01"
            },
            {
                "action": "type",
                "text": "AGI Assistant Demo",
                "description": "Type search query",
                "timestamp": "2024-01-01T12:01:02"
            },
            {
                "action": "hotkey",
                "keys": ["enter"],
                "description": "Submit search",
                "timestamp": "2024-01-01T12:01:03"
            }
        ])
    )
    
    # Example 3: Keyboard Shortcuts Workflow
    workflow3 = Workflow(
        name="Keyboard Shortcuts Demo",
        description="Demonstrates various keyboard shortcuts",
        steps_json=json.dumps([
            {
                "action": "hotkey",
                "keys": ["cmd", "space"],
                "description": "Open Spotlight (macOS) or Start Menu (Windows)",
                "timestamp": "2024-01-01T12:02:00"
            },
            {
                "action": "wait",
                "duration": 1.0,
                "description": "Wait for menu to open",
                "timestamp": "2024-01-01T12:02:01"
            },
            {
                "action": "type",
                "text": "TextEdit",
                "description": "Type application name",
                "timestamp": "2024-01-01T12:02:02"
            },
            {
                "action": "hotkey",
                "keys": ["enter"],
                "description": "Launch application",
                "timestamp": "2024-01-01T12:02:03"
            }
        ])
    )
    
    # Add workflows to database
    db.add(workflow1)
    db.add(workflow2)
    db.add(workflow3)
    db.commit()
    
    print("✅ Created 3 example workflows:")
    print(f"  1. {workflow1.name}")
    print(f"  2. {workflow2.name}")
    print(f"  3. {workflow3.name}")
    print("\nYou can now test these workflows in the AGI Assistant!")
    
    db.close()

if __name__ == "__main__":
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    print("🚀 Creating example workflows...\n")
    create_example_workflows()
    print("\n✨ Done!")


