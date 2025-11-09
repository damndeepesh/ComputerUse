"""
Smart Data Management System
- Deletes older training data when models are stable
- Optimizes screenshot and video storage
- Manages local storage efficiently
"""
import os
import shutil
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json


class DataManager:
    """Manages data storage, cleanup, and optimization"""
    
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.screenshots_dir = self.data_dir / "screenshots"
        self.recordings_dir = self.data_dir / "recordings"
        self.transcripts_dir = self.data_dir / "transcripts"
        self.workflows_db = self.data_dir / "workflows.db"
        
        # Create directories
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.max_screenshots_per_workflow = 50  # Keep only recent screenshots
        self.max_screenshot_age_days = 30  # Delete screenshots older than 30 days
        self.max_recording_age_days = 90  # Keep recordings for 90 days
        self.max_storage_mb = 500  # Max 500MB for screenshots/videos
        self.model_stability_threshold = 5  # Consider model stable after 5 successful workflows
        
        # Track model stability
        self.stability_file = self.data_dir / "model_stability.json"
        self.stability_data = self._load_stability_data()
    
    def _load_stability_data(self) -> Dict:
        """Load model stability tracking data"""
        if self.stability_file.exists():
            try:
                with open(self.stability_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "successful_workflows": 0,
            "last_cleanup": None,
            "model_stable": False
        }
    
    def _save_stability_data(self):
        """Save model stability tracking data"""
        try:
            with open(self.stability_file, 'w') as f:
                json.dump(self.stability_data, f, indent=2)
        except Exception as e:
            print(f"Error saving stability data: {e}")
    
    def record_workflow_success(self):
        """Record a successful workflow creation"""
        self.stability_data["successful_workflows"] += 1
        
        # Mark model as stable if threshold reached
        if (self.stability_data["successful_workflows"] >= self.model_stability_threshold and 
            not self.stability_data["model_stable"]):
            self.stability_data["model_stable"] = True
            print(f"✅ Model is now stable ({self.stability_data['successful_workflows']} successful workflows)")
            # Trigger cleanup of old training data
            self.cleanup_old_training_data()
        
        self._save_stability_data()
    
    def cleanup_old_training_data(self):
        """Delete older training data when model is stable"""
        if not self.stability_data["model_stable"]:
            return
        
        print("🧹 Cleaning up old training data...")
        deleted_count = 0
        
        # Clean up old screenshots (keep only recent ones)
        if self.screenshots_dir.exists():
            screenshots = sorted(
                self.screenshots_dir.glob("*.png"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            # Keep only the most recent screenshots
            if len(screenshots) > self.max_screenshots_per_workflow * 2:
                old_screenshots = screenshots[self.max_screenshots_per_workflow * 2:]
                for screenshot in old_screenshots:
                    try:
                        screenshot.unlink()
                        deleted_count += 1
                    except Exception as e:
                        print(f"Error deleting screenshot {screenshot}: {e}")
        
        # Clean up screenshots older than max age
        cutoff_time = time.time() - (self.max_screenshot_age_days * 24 * 60 * 60)
        if self.screenshots_dir.exists():
            for screenshot in self.screenshots_dir.glob("*.png"):
                try:
                    if screenshot.stat().st_mtime < cutoff_time:
                        screenshot.unlink()
                        deleted_count += 1
                except Exception as e:
                    print(f"Error deleting old screenshot {screenshot}: {e}")
        
        print(f"✅ Cleaned up {deleted_count} old screenshots")
        self.stability_data["last_cleanup"] = datetime.now().isoformat()
        self._save_stability_data()
    
    def cleanup_old_recordings(self):
        """Clean up old audio/video recordings"""
        if not self.recordings_dir.exists():
            return
        
        cutoff_time = time.time() - (self.max_recording_age_days * 24 * 60 * 60)
        deleted_count = 0
        
        for recording in self.recordings_dir.glob("*"):
            try:
                if recording.stat().st_mtime < cutoff_time:
                    recording.unlink()
                    deleted_count += 1
            except Exception as e:
                print(f"Error deleting old recording {recording}: {e}")
        
        if deleted_count > 0:
            print(f"✅ Cleaned up {deleted_count} old recordings")
    
    def optimize_storage(self):
        """Optimize storage by compressing and cleaning up"""
        total_size_mb = self._get_directory_size_mb(self.screenshots_dir)
        total_size_mb += self._get_directory_size_mb(self.recordings_dir)
        
        if total_size_mb > self.max_storage_mb:
            print(f"⚠️  Storage usage ({total_size_mb:.1f}MB) exceeds limit ({self.max_storage_mb}MB)")
            
            # Delete oldest files first
            self._cleanup_by_age(self.screenshots_dir, days=self.max_screenshot_age_days // 2)
            self._cleanup_by_age(self.recordings_dir, days=self.max_recording_age_days // 2)
            
            # If still too large, be more aggressive
            new_size_mb = self._get_directory_size_mb(self.screenshots_dir) + self._get_directory_size_mb(self.recordings_dir)
            if new_size_mb > self.max_storage_mb:
                print(f"⚠️  Still over limit, cleaning up more aggressively...")
                self._cleanup_by_age(self.screenshots_dir, days=7)  # Keep only last week
                self._cleanup_by_age(self.recordings_dir, days=30)  # Keep only last month
    
    def _cleanup_by_age(self, directory: Path, days: int):
        """Delete files older than specified days"""
        if not directory.exists():
            return
        
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        deleted_count = 0
        
        for file in directory.glob("*"):
            try:
                if file.stat().st_mtime < cutoff_time:
                    file.unlink()
                    deleted_count += 1
            except Exception as e:
                print(f"Error deleting {file}: {e}")
        
        if deleted_count > 0:
            print(f"   Deleted {deleted_count} files older than {days} days from {directory.name}")
    
    def _get_directory_size_mb(self, directory: Path) -> float:
        """Get total size of directory in MB"""
        if not directory.exists():
            return 0.0
        
        total_bytes = 0
        for file in directory.rglob("*"):
            try:
                if file.is_file():
                    total_bytes += file.stat().st_size
            except:
                pass
        
        return total_bytes / (1024 * 1024)
    
    def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        return {
            "screenshots_mb": round(self._get_directory_size_mb(self.screenshots_dir), 2),
            "recordings_mb": round(self._get_directory_size_mb(self.recordings_dir), 2),
            "transcripts_mb": round(self._get_directory_size_mb(self.transcripts_dir), 2),
            "total_mb": round(
                self._get_directory_size_mb(self.screenshots_dir) +
                self._get_directory_size_mb(self.recordings_dir) +
                self._get_directory_size_mb(self.transcripts_dir),
                2
            ),
            "screenshot_count": len(list(self.screenshots_dir.glob("*.png"))) if self.screenshots_dir.exists() else 0,
            "recording_count": len(list(self.recordings_dir.glob("*"))) if self.recordings_dir.exists() else 0,
            "model_stable": self.stability_data["model_stable"],
            "successful_workflows": self.stability_data["successful_workflows"]
        }
    
    def save_transcript(self, workflow_id: int, transcript_data: Dict):
        """Save transcript for a workflow"""
        transcript_file = self.transcripts_dir / f"workflow_{workflow_id}_transcript.json"
        try:
            with open(transcript_file, 'w') as f:
                json.dump(transcript_data, f, indent=2)
        except Exception as e:
            print(f"Error saving transcript: {e}")
    
    def get_transcript(self, workflow_id: int) -> Optional[Dict]:
        """Get transcript for a workflow"""
        transcript_file = self.transcripts_dir / f"workflow_{workflow_id}_transcript.json"
        if transcript_file.exists():
            try:
                with open(transcript_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading transcript: {e}")
        return None
    
    def cleanup_workflow_data(self, workflow_id: int, keep_screenshots: bool = True):
        """Clean up data associated with a specific workflow"""
        # This can be called when a workflow is deleted
        # For now, we'll keep screenshots as they might be referenced by other workflows
        if not keep_screenshots:
            # This would require tracking which screenshots belong to which workflow
            pass
        
        # Clean up transcript
        transcript_file = self.transcripts_dir / f"workflow_{workflow_id}_transcript.json"
        if transcript_file.exists():
            try:
                transcript_file.unlink()
            except Exception as e:
                print(f"Error deleting transcript: {e}")


# Global instance
_data_manager = None

def get_data_manager(data_dir=None) -> DataManager:
    """Get or create global data manager instance
    
    Args:
        data_dir: Optional path to data directory. If None, uses project root/data or app data dir for packaged apps
    """
    global _data_manager
    if _data_manager is None:
        if data_dir is None:
            import os
            # Check if this is a packaged app (same logic as main.py)
            if os.environ.get('APP_PACKAGED') == '1' or Path(__file__).parent.parent.parent.name == 'Resources':
                # Packaged app - use app support directory
                if os.name == 'darwin':  # macOS
                    data_dir = Path.home() / "Library" / "Application Support" / "AGI Assistant" / "data"
                elif os.name == 'nt':  # Windows
                    data_dir = Path(os.environ.get('APPDATA', Path.home())) / "AGI Assistant" / "data"
                else:  # Linux
                    data_dir = Path.home() / ".local" / "share" / "AGI Assistant" / "data"
            else:
                # Development mode - use project root
                project_root = Path(__file__).parent.parent.parent
                data_dir = project_root / "data"
        _data_manager = DataManager(data_dir=str(data_dir))
    return _data_manager

