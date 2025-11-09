"""
Independent workflow saving module
Handles saving workflows to database
DO NOT MODIFY TRACKING OR CONVERSION FUNCTIONALITY HERE
"""
import json
import time
from pathlib import Path
from models.database import Workflow
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Database setup - use project root data directory or app data dir for packaged apps
import os
if os.environ.get('APP_PACKAGED') == '1' or Path(__file__).parent.parent.parent.name == 'Resources':
    # Packaged app - use app support directory
    if os.name == 'darwin':  # macOS
        DATA_DIR = Path.home() / "Library" / "Application Support" / "AGI Assistant" / "data"
    elif os.name == 'nt':  # Windows
        DATA_DIR = Path(os.environ.get('APPDATA', Path.home())) / "AGI Assistant" / "data"
    else:  # Linux
        DATA_DIR = Path.home() / ".local" / "share" / "AGI Assistant" / "data"
else:
    # Development mode - use project root
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    DATA_DIR = PROJECT_ROOT / "data"

DATABASE_PATH = DATA_DIR / "workflows.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.absolute()}"
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class WorkflowSaver:
    """Independent workflow saver - handles database operations"""
    
    def __init__(self):
        pass
    
    def save_workflow(self, workflow_data, steps):
        """
        Save workflow to database
        This is the ONLY function that should save workflows
        Returns: (success: bool, workflow_id: int or None, error: str or None)
        """
        db = SessionLocal()
        try:
            print(f"   💾 Saving workflow to database...")
            print(f"   📊 Workflow: {workflow_data.get('name', 'Unnamed')}")
            print(f"   📊 Steps to save: {len(steps)}")
            
            # Validate and serialize steps JSON
            steps_json_str = self._validate_and_serialize_steps(steps)
            if steps_json_str is None:
                return False, None, "Failed to serialize steps to JSON"
            
            # Create workflow object
            workflow = Workflow(
                name=workflow_data.get("name", "New Workflow"),
                description=workflow_data.get("description", ""),
                steps_json=steps_json_str,
            )
            
            db.add(workflow)
            print(f"   💾 Committing to database...")
            db.commit()
            db.refresh(workflow)
            print(f"   ✅ Database commit successful")
            
            # Verify workflow was saved
            saved_steps = workflow.get_steps()
            if len(saved_steps) != len(steps):
                print(f"   ⚠️  WARNING: Saved {len(saved_steps)} steps but expected {len(steps)}")
            else:
                print(f"   ✅ Workflow saved with {len(saved_steps)} steps")
            
            print(f"💾 Created workflow ID {workflow.id}: {workflow.name}")
            print(f"✅✅✅ WORKFLOW SAVED SUCCESSFULLY ✅✅✅")
            
            return True, workflow.id, None
            
        except Exception as e:
            print(f"   ❌ CRITICAL: Database error while saving workflow: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
            return False, None, str(e)
        finally:
            try:
                db.close()
                print(f"   ✅ Database connection closed")
            except Exception as close_error:
                print(f"   ⚠️  Error closing database: {close_error}")
    
    def _validate_and_serialize_steps(self, steps):
        """Validate and serialize steps to JSON, fixing common issues"""
        try:
            # First attempt - direct serialization
            steps_json_str = json.dumps(steps)
            json.loads(steps_json_str)  # Verify it's valid
            print(f"   ✅ Steps JSON validated ({len(steps_json_str)} chars)")
            return steps_json_str
        except Exception as e:
            print(f"   ❌ Error creating JSON from steps: {e}")
            print(f"   🔧 Attempting to fix JSON issues...")
            
            try:
                # Try to fix by removing problematic fields
                import copy
                clean_steps = copy.deepcopy(steps)
                for step in clean_steps:
                    # Remove complex objects that might not serialize
                    step.pop('app_info', None)
                    # Ensure all values are JSON-serializable
                    for key, value in list(step.items()):
                        if value is not None and not isinstance(value, (str, int, float, bool, list, dict)):
                            step[key] = str(value)
                
                steps_json_str = json.dumps(clean_steps)
                json.loads(steps_json_str)  # Verify
                print(f"   ✅ Fixed JSON issues, retrying with cleaned steps")
                return steps_json_str
            except Exception as e2:
                print(f"   ❌ Could not fix JSON issues: {e2}")
                import traceback
                traceback.print_exc()
                return None

