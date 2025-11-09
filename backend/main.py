from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import asynccontextmanager
import os
from pathlib import Path

from models.database import Base, Workflow
from capture.screen_recorder import ScreenRecorder
from capture.audio_recorder import AudioRecorder
from capture.action_tracker import ActionTracker
from capture.app_tracker import AppTracker
from processing.workflow_analyzer import WorkflowAnalyzer
from automation.executor import WorkflowExecutor
from automation.safety import get_safety_manager
from utils.data_manager import get_data_manager

# Get project root directory (parent of backend folder)
# For packaged apps, use app user data directory; for development, use project root
if os.environ.get('APP_PACKAGED') == '1' or Path(__file__).parent.parent.name == 'Resources':
    # Packaged app - use macOS app support directory
    # macOS: ~/Library/Application Support/AGI Assistant/data
    # Windows: %APPDATA%\AGI Assistant\data
    # Linux: ~/.local/share/AGI Assistant/data
    if os.name == 'darwin':  # macOS
        DATA_DIR = Path.home() / "Library" / "Application Support" / "AGI Assistant" / "data"
    elif os.name == 'nt':  # Windows
        DATA_DIR = Path(os.environ.get('APPDATA', Path.home())) / "AGI Assistant" / "data"
    else:  # Linux
        DATA_DIR = Path.home() / ".local" / "share" / "AGI Assistant" / "data"
else:
    # Development mode - use project root
    PROJECT_ROOT = Path(__file__).parent.parent
    DATA_DIR = PROJECT_ROOT / "data"

# Create necessary directories in project root (create parent directories if needed)
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "screenshots").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "recordings").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "transcripts").mkdir(parents=True, exist_ok=True)

# Database setup - use absolute path
DATABASE_PATH = DATA_DIR / "workflows.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.absolute()}"
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,  # Increased from 1 to handle concurrent requests
    max_overflow=10  # Allow overflow connections when pool is exhausted
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Global instances
screen_recorder = None
audio_recorder = None
action_tracker = None
app_tracker = None
workflow_analyzer = None
workflow_executor = None
data_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - initialize only lightweight components immediately
    # Heavy initialization (models, OCR) will be lazy-loaded when needed
    global screen_recorder, audio_recorder, action_tracker, app_tracker, workflow_analyzer, workflow_executor, data_manager
    
    print("🚀 Starting backend server...")
    
    # Initialize lightweight components first
    data_manager = get_data_manager()
    screen_recorder = ScreenRecorder()
    audio_recorder = AudioRecorder(recordings_dir=DATA_DIR / "recordings")
    app_tracker = AppTracker()
    
    # Initialize action tracker (lightweight)
    action_tracker = ActionTracker(app_tracker=app_tracker)
    
    # Initialize workflow executor (lightweight)
    workflow_executor = WorkflowExecutor()
    
    # Defer heavy initialization (WorkflowAnalyzer loads models/OCR) to background
    workflow_analyzer = None
    
    # Start server immediately - don't wait for heavy initialization
    print("✅ Server ready - accepting requests")
    
    # Run heavy initialization and cleanup in background
    import asyncio
    async def initialize_heavy_components():
        # Small delay to let server start responding first
        await asyncio.sleep(0.5)
        print("🔧 Initializing heavy components in background...")
        try:
            global workflow_analyzer
            workflow_analyzer = WorkflowAnalyzer()
            print("✅ Heavy components initialized")
        except Exception as e:
            print(f"⚠️  Error initializing heavy components (non-critical): {e}")
            # Create a minimal analyzer that will work without models
            workflow_analyzer = WorkflowAnalyzer()
    
    async def run_cleanup():
        # Wait a bit longer for server to be fully ready
        await asyncio.sleep(2)
        print("🧹 Running background cleanup...")
        try:
            data_manager.cleanup_old_recordings()
            data_manager.optimize_storage()
            print("✅ Background cleanup completed")
        except Exception as e:
            print(f"⚠️  Cleanup error (non-critical): {e}")
    
    # Start background tasks
    asyncio.create_task(initialize_heavy_components())
    asyncio.create_task(run_cleanup())
    
    # Server starts accepting requests now
    yield
    # Shutdown
    if screen_recorder and screen_recorder.is_recording:
        screen_recorder.stop()
    if audio_recorder and audio_recorder.is_recording:
        audio_recorder.stop()
    if action_tracker and action_tracker.is_tracking:
        action_tracker.stop()
    if app_tracker and app_tracker.is_tracking:
        app_tracker.stop()


app = FastAPI(title="AGI Assistant API", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files - use absolute paths
app.mount("/screenshots", StaticFiles(directory=str(DATA_DIR / "screenshots")), name="screenshots")
app.mount("/recordings", StaticFiles(directory=str(DATA_DIR / "recordings")), name="recordings")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
async def root():
    return {"message": "AGI Assistant API", "status": "running"}


@app.get("/health")
async def health():
    """Simple health check endpoint that responds immediately"""
    return {"status": "ok", "message": "Backend is running"}


@app.get("/api/workflows")
async def get_workflows(db: Session = Depends(get_db)):
    """Get all workflows"""
    workflows = db.query(Workflow).order_by(Workflow.created_at.desc()).all()
    result = []
    for w in workflows:
        steps = w.get_steps()
        print(f"   📋 Workflow {w.id} ({w.name}): {len(steps)} steps")
        if len(steps) == 0 and w.steps_json:
            print(f"   ⚠️  Warning: Workflow {w.id} has steps_json but get_steps() returned empty list")
            print(f"   📄 steps_json length: {len(w.steps_json) if w.steps_json else 0} chars")
        result.append({
            "id": w.id,
            "name": w.name,
            "description": w.description,
            "steps": steps,
            "created_at": w.created_at.isoformat(),
        })
    return result


@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    """Get a specific workflow"""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "steps": workflow.get_steps(),
        "created_at": workflow.created_at.isoformat(),
    }


@app.delete("/api/workflows/{workflow_id}")
async def delete_workflow(workflow_id: int, db: Session = Depends(get_db)):
    """Delete a workflow"""
    global data_manager
    try:
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")
        
        workflow_name = workflow.name
        workflow_id_val = workflow.id
        
        # Clean up associated data first
        if data_manager:
            try:
                data_manager.cleanup_workflow_data(workflow_id_val, keep_screenshots=True)
                print(f"🗑️  Cleaned up data for workflow {workflow_id_val}")
            except Exception as e:
                print(f"⚠️  Error cleaning up workflow data: {e}")
        
        # Delete from database
        db.delete(workflow)
        db.commit()
        
        print(f"✅ Deleted workflow {workflow_id_val}: {workflow_name}")
        return {"success": True, "message": f"Workflow '{workflow_name}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting workflow {workflow_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting workflow: {str(e)}")


@app.post("/api/recording/start")
async def start_recording(background_tasks: BackgroundTasks):
    """Start recording screen and audio"""
    global screen_recorder, audio_recorder, action_tracker, app_tracker
    
    try:
        print("🎬 START RECORDING requested")
        
        # Check if already recording
        if screen_recorder.is_recording:
            print("⚠️  Already recording!")
            return {"success": False, "message": "Already recording"}
        
        # Start screen recording
        screen_recorder.start()
        print(f"✅ Screen recorder started (is_recording={screen_recorder.is_recording})")
        
        # Start audio recording
        audio_recorder.start()
        print(f"✅ Audio recorder started")
        
        # Start action tracking
        action_tracker.start()
        print(f"✅ Action tracker started (is_tracking={action_tracker.is_tracking})")
        
        # Start app tracking
        app_tracker.start()
        print(f"✅ App tracker started")
        
        return {"success": True, "message": "Recording started", "is_recording": True}
    except Exception as e:
        print(f"❌ Error starting recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recording/stop")
async def stop_recording(background_tasks: BackgroundTasks):
    """Stop recording and process the workflow - optimized for fast response"""
    global screen_recorder, audio_recorder, action_tracker, app_tracker, workflow_analyzer
    
    try:
        print("⏹️ STOP RECORDING requested")
        
        # Always try to stop all recorders, even if one thinks it's not recording
        # This handles race conditions and state mismatches
        was_recording = False
        if screen_recorder and screen_recorder.is_recording:
            was_recording = True
        elif action_tracker and action_tracker.is_tracking:
            was_recording = True
        
        if not was_recording:
            print("⚠️  No active recording detected, but stopping anyway to ensure clean state")
        
        # Stop recordings - do this quickly to make button responsive
        print("⏹️  Stopping all recorders...")
        
        # Stop action tracker first (most critical - captures user actions)
        # Check status before stopping
        if action_tracker:
            # Get current actions count using get_actions() method
            current_actions = action_tracker.get_actions()
            print(f"   📊 Action tracker status before stop: is_tracking={action_tracker.is_tracking}, actions={len(current_actions)}")
        
        print("   Stopping action tracker...")
        actions = []
        try:
            if action_tracker:
                # The stop() method will handle marking is_tracking = False at the right time
                # This ensures we capture all valid actions before stopping
                actions = action_tracker.stop()
                
                # Filter out CLICKS that happened in the last 0.1 seconds (very recent, likely the stop button click)
                # DON'T filter moves - they're valid and should be kept
                # This is a safety measure in case the stop button click was already captured
                # NOTE: We already prevent stop button click from being recorded by setting is_tracking=False
                # This is just an extra safety net
                if actions:
                    import time as time_module
                    current_time = time_module.time()
                    filtered_actions = []
                    filtered_count = 0
                    
                    for action in actions:
                        action_type = action.get("type", "unknown")
                        
                        # Only filter CLICKS that are VERY recent (last 0.1 seconds, not 0.2)
                        # This is more conservative to avoid filtering valid clicks
                        # Keep all moves, scrolls, types, hotkeys, etc.
                        if action_type == "click":
                            action_time = action.get("timestamp", 0)
                            if isinstance(action_time, str):
                                # Convert ISO timestamp
                                from datetime import datetime
                                try:
                                    action_time = datetime.fromisoformat(action_time.replace('Z', '+00:00')).timestamp()
                                except:
                                    action_time = current_time
                            
                            # Only filter clicks that happened in the last 0.1 seconds (very recent)
                            time_since_action = current_time - action_time
                            if time_since_action > 0.1:
                                filtered_actions.append(action)
                            else:
                                filtered_count += 1
                                print(f"   🚫 Filtered out very recent click action (likely stop button, {time_since_action:.3f}s ago)")
                        else:
                            # Keep all non-click actions (moves, scrolls, types, etc.)
                            filtered_actions.append(action)
                    
                    if filtered_count > 0:
                        print(f"   ⚠️  Filtered {filtered_count} very recent click action(s) (likely stop button)")
                        actions = filtered_actions
                
                print(f"   ✅ Action tracker: {len(actions)} actions captured (after filtering)")
            else:
                print("   ⚠️  Action tracker not initialized")
        except Exception as e:
            print(f"   ⚠️  Error stopping action tracker: {e}")
            import traceback
            traceback.print_exc()
        
        # Stop app tracker (instant)
        print("   Stopping app tracker...")
        app_changes = []
        try:
            if app_tracker:
                app_changes = app_tracker.stop()
                print(f"   ✅ App tracker: {len(app_changes)} app changes captured")
            else:
                print("   ⚠️  App tracker not initialized")
        except Exception as e:
            print(f"   ⚠️  Error stopping app tracker: {e}")
            import traceback
            traceback.print_exc()
        
        # IMPORTANT: Keep screenshots running a bit longer to capture final state
        # Wait a moment to let screenshots capture one more frame after actions stop
        print("   ⏳ Allowing screenshots to capture final state...")
        import time as time_module
        time_module.sleep(1.0)  # Reduced to 1.0 second (screenshot interval is 1s)
        
        # Stop screen recorder LAST (after actions have stopped, capture final screenshots)
        print("   Stopping screen recorder...")
        screenshots = []
        try:
            if screen_recorder:
                # Ensure is_recording is set to False before stopping (prevents hangs)
                screen_recorder.is_recording = False
                screenshots = screen_recorder.stop()
                # Force set to False again in case stop() didn't update it
                screen_recorder.is_recording = False
                print(f"   ✅ Screen recorder: {len(screenshots)} screenshots captured")
                
                # Verify screenshots exist
                if screenshots:
                    existing = [s for s in screenshots if os.path.exists(s)]
                    if len(existing) < len(screenshots):
                        print(f"   ⚠️  WARNING: Only {len(existing)}/{len(screenshots)} screenshot files exist on disk!")
                    else:
                        print(f"   ✅ All {len(screenshots)} screenshot files verified on disk")
            else:
                print("   ⚠️  Screen recorder not initialized")
        except Exception as e:
            print(f"   ❌ ERROR stopping screen recorder: {e}")
            import traceback
            traceback.print_exc()
            # Force set to False even on error
            if screen_recorder:
                screen_recorder.is_recording = False
            screenshots = []  # Return empty list on error
        
        # Stop audio recorder (saves audio file - can take time, but we'll get files later)
        print("   Stopping audio recorder...")
        transcripts = []
        try:
            if audio_recorder:
                transcripts = audio_recorder.stop()  # This saves the audio file
                # Force set to False in case stop() didn't update it
                audio_recorder.is_recording = False
                print(f"   ✅ Audio recorder: {len(transcripts)} transcripts captured")
            else:
                print("   ⚠️  Audio recorder not initialized")
        except Exception as e:
            print(f"   ⚠️  Error stopping audio recorder: {e}")
            import traceback
            traceback.print_exc()
            # Force set to False even on error
            if audio_recorder:
                audio_recorder.is_recording = False
        
        # Try to get audio files immediately (non-blocking - don't wait if they're not ready)
        audio_files = []
        try:
            if audio_recorder:
                audio_files = audio_recorder.get_audio_files()
        except Exception as e:
            print(f"   ⚠️  Error getting audio files: {e}")
        
        # Don't wait for audio files - they'll be retrieved in background task if needed
        if not audio_files:
            print("   ⏳ Audio files may still be saving (will be retrieved in background task)")
        
        print(f"\n✅ Recording stopped: {len(screenshots)} screenshots, {len(actions)} actions, {len(app_changes)} app changes, {len(audio_files)} audio files")
        if actions:
            print(f"   📊 Action breakdown:")
            action_types = {}
            for action in actions:
                action_type = action.get("type", "unknown")
                action_types[action_type] = action_types.get(action_type, 0) + 1
            for action_type, count in action_types.items():
                print(f"      - {action_type}: {count}")
            
            # Warn if no mouse actions were captured
            has_mouse_actions = action_types.get('click', 0) > 0 or action_types.get('scroll', 0) > 0 or action_types.get('move', 0) > 0
            if not has_mouse_actions:
                print(f"\n   ⚠️  WARNING: No mouse actions (click, scroll, or move) captured!")
                print(f"   ⚠️  The workflow will only have wait steps - mouse will NOT move during execution.")
                print(f"   ⚠️  Make sure you click/scroll/move during recording (not just the stop button).")
        else:
            print(f"\n   ⚠️  WARNING: No actions captured at all!")
            print(f"   ⚠️  The workflow will only have screenshot-based wait steps.")
            print(f"   ⚠️  Make sure you interact with the screen during recording.")
        
        if audio_files:
            print(f"   📁 Audio files: {audio_files}")
        else:
            print(f"   ⚠️  No audio files captured (audio may not be available or recording failed)")
        
        # CRITICAL: Always return immediately - don't wait for background tasks
        # This ensures the stop button is responsive
        print(f"   ✅ All recorders stopped - returning response immediately")
        
        # Always return success and is_recording=False to ensure UI updates
        # Only create workflow if we have data (actions are most important, screenshots are secondary)
        if actions or screenshots:
            # Analyze and create workflow in background (non-blocking)
            print(f"   📋 Scheduling workflow creation in background task...")
            print(f"   📊 Data summary: {len(screenshots)} screenshots, {len(actions)} actions, {len(app_changes)} app changes")
            try:
                background_tasks.add_task(
                    create_workflow_from_recording,
                    screenshots,
                    transcripts,
                    actions,
                    app_changes,
                    audio_files
                )
                print(f"   ✅ Background task scheduled successfully")
            except Exception as task_error:
                print(f"   ❌ ERROR scheduling background task: {task_error}")
                import traceback
                traceback.print_exc()
            
            # Return immediately - don't wait for background processing
            return {"success": True, "message": "Recording stopped, processing workflow...", "is_recording": False}
        else:
            print("⚠️  No data captured during recording")
            return {"success": True, "message": "Recording stopped (no data captured)", "is_recording": False}
            
    except Exception as e:
        print(f"❌ Error stopping recording: {e}")
        import traceback
        traceback.print_exc()
        # Force stop all recorders even on error
        try:
            if screen_recorder:
                screen_recorder.is_recording = False
            if audio_recorder:
                audio_recorder.is_recording = False
            if action_tracker:
                action_tracker.is_tracking = False
        except:
            pass
        return {"success": False, "message": f"Error stopping: {str(e)}", "is_recording": False}


@app.get("/api/recording/status")
async def get_recording_status():
    """Get current recording status"""
    global screen_recorder, audio_recorder
    
    status = {
        "is_recording": screen_recorder.is_recording if screen_recorder else False,
        "transcript": audio_recorder.get_transcripts() if audio_recorder else [],
        "latest_screenshot": None,
    }
    
    if screen_recorder and screen_recorder.screenshots:
        latest = screen_recorder.screenshots[-1]
        status["latest_screenshot"] = f"/screenshots/{os.path.basename(latest)}"
    
    return status


@app.post("/api/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: int, db: Session = Depends(get_db)):
    """Execute a workflow with real-time progress"""
    global workflow_executor
    
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    steps = workflow.get_steps()
    
    # Get safety manager
    safety = get_safety_manager()
    safety.reset()
    
    # Confirm execution
    if not safety.confirm_execution(workflow.name, len(steps)):
        raise HTTPException(status_code=403, detail="Execution not confirmed")
    
    async def progress_generator():
        """Generator that yields execution progress"""
        for i, step in enumerate(steps):
            # Check if stop was requested
            if safety.check_should_stop():
                yield f"data: {{'stopped': true, 'step': {i}}}\n\n"
                break
            
            # Send progress update
            yield f"data: {{'step': {i}, 'total': {len(steps)}}}\n\n"
            
            # Validate step
            if not safety.validate_step(step):
                yield f"data: {{'error': 'Step validation failed', 'step': {i}}}\n\n"
                break
            
            # Execute the step with retry and continue_on_error support
            try:
                continue_on_error = step.get("continue_on_error", False)
                success = workflow_executor.execute_step(step, continue_on_error=continue_on_error)
                safety.log_execution(step, True)
            except Exception as e:
                safety.log_execution(step, False, str(e))
                # Check if we should continue on error
                if step.get("continue_on_error", False):
                    yield f"data: {{'warning': 'Step failed but continuing: {str(e)}', 'step': {i}}}\n\n"
                    continue
                else:
                    yield f"data: {{'error': '{str(e)}'}}\n\n"
                    break
        
        yield f"data: {{'completed': true}}\n\n"
    
    return StreamingResponse(
        progress_generator(),
        media_type="text/event-stream"
    )


def ensure_workflow_analyzer():
    """Ensure workflow_analyzer is initialized (lazy initialization)"""
    global workflow_analyzer
    if workflow_analyzer is None:
        print("⚠️  WorkflowAnalyzer not yet initialized, initializing now...")
        try:
            workflow_analyzer = WorkflowAnalyzer()
            print("✅ WorkflowAnalyzer initialized")
        except Exception as e:
            print(f"⚠️  Error initializing WorkflowAnalyzer: {e}")
            # Create a minimal analyzer that will work without models
            workflow_analyzer = WorkflowAnalyzer()
    return workflow_analyzer


async def create_workflow_from_recording(screenshots, transcripts, actions, app_changes=[], audio_files=[]):
    """Background task to create workflow from recording - uses independent modules"""
    global workflow_analyzer, data_manager, audio_recorder
    
    # Import independent modules
    from processing.step_converter import StepConverter
    from utils.workflow_saver import WorkflowSaver
    
    step_converter = StepConverter()
    workflow_saver = WorkflowSaver()
    
    db = None  # Will be created if needed for additional operations
    try:
        # If audio files weren't ready when stop was called, try to get them now
        if not audio_files and audio_recorder:
            import time
            time.sleep(0.2)  # Give a bit more time for audio to finish saving
            audio_files = audio_recorder.get_audio_files()
            if audio_files:
                print(f"   📁 Retrieved {len(audio_files)} audio file(s) in background task")
        
        print(f"\n🔄 Processing recording: {len(screenshots)} screenshots, {len(transcripts)} transcripts, {len(actions)} actions, {len(app_changes)} app changes")
        
        # Log action breakdown with detailed info
        if actions:
            action_types = {}
            for action in actions:
                action_type = action.get("type", "unknown")
                action_types[action_type] = action_types.get(action_type, 0) + 1
            print(f"   📊 Input actions breakdown:")
            for action_type, count in action_types.items():
                print(f"      - {action_type}: {count}")
            
            # Log sample actions to verify they have the expected fields
            print(f"   📋 Sample actions (first 3):")
            for i, action in enumerate(actions[:3]):
                action_type = action.get("type", "unknown")
                app_name = action.get("app_name", "N/A")
                has_spreadsheet = "spreadsheet_context" in action
                has_clipboard = "clipboard_content" in action
                print(f"      [{i+1}] {action_type} | app: {app_name} | spreadsheet: {has_spreadsheet} | clipboard: {has_clipboard}")
        else:
            print(f"   ⚠️  WARNING: No actions captured! This workflow will use screenshots only.")
        
        # STEP 1: Convert actions to steps using independent converter
        print(f"   🔍 Converting actions to steps...")
        try:
            steps = step_converter.convert_actions_to_steps(actions, screenshots, app_changes)
            print(f"   ✅ Step conversion completed: {len(steps)} steps")
            
            # CRITICAL: Verify conversion
            if len(steps) != len(actions):
                print(f"   ⚠️  WARNING: {len(actions)} actions but only {len(steps)} steps created!")
                print(f"   ⚠️  Missing {len(actions) - len(steps)} steps!")
            else:
                print(f"   ✅ All {len(actions)} actions successfully converted to steps")
        except Exception as e:
            print(f"❌ CRITICAL ERROR during step conversion: {e}")
            import traceback
            traceback.print_exc()
            steps = []  # Continue with empty steps
        
        # STEP 2: Create workflow data structure
        import time as time_module
        workflow_data = {
            "name": f"Workflow {time_module.strftime('%Y-%m-%d %H:%M')}",
            "description": f"Workflow with {len(steps)} steps",
            "steps": steps
        }
        
        # Log step breakdown
        if steps:
            step_types = {}
            for step in steps:
                step_action = step.get("action", "unknown")
                step_types[step_action] = step_types.get(step_action, 0) + 1
            print(f"   📊 Output steps breakdown ({len(steps)} total):")
            for step_action, count in step_types.items():
                print(f"      - {step_action}: {count}")
        
        # STEP 3: Save workflow using independent saver (manages its own DB session)
        print(f"   💾 Saving workflow to database...")
        success, workflow_id, error = workflow_saver.save_workflow(workflow_data, steps)
        
        if not success:
            raise Exception(f"Failed to save workflow: {error}")
        
        if not workflow_id:
            raise Exception("Workflow saved but no workflow_id returned")
        
        # Create session for additional operations (transcripts, etc.)
        db = SessionLocal()
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        
        if not workflow:
            raise Exception(f"Workflow {workflow_id} not found after saving")
        
        # Save transcripts and audio files to data manager
        if transcripts or audio_files:
            transcript_data = {
                "workflow_id": workflow.id,
                "transcripts": transcripts if transcripts else [],
                "audio_files": audio_files,
                "created_at": workflow.created_at.isoformat(),
            }
            data_manager.save_transcript(workflow.id, transcript_data)
        
        # Record successful workflow creation
        data_manager.record_workflow_success()
        
        # Periodic cleanup
        if data_manager.stability_data["successful_workflows"] % 10 == 0:
            data_manager.optimize_storage()
        
        print(f"💾 Created workflow ID {workflow.id}: {workflow.name} with {len(steps)} steps")
        print(f"✅✅✅ WORKFLOW SAVED SUCCESSFULLY ✅✅✅")
    except Exception as e:
        import traceback
        print(f"❌❌❌ CRITICAL ERROR creating workflow: {e} ❌❌❌")
        print(f"❌ Full traceback:")
        traceback.print_exc()
        if db:
            try:
                db.rollback()
                print(f"   ✅ Database rolled back")
            except Exception as rollback_error:
                print(f"   ⚠️  Error during rollback: {rollback_error}")
    finally:
        if db:
            try:
                db.close()
                print(f"   ✅ Database connection closed")
            except Exception as close_error:
                print(f"   ⚠️  Error closing database: {close_error}")


@app.get("/api/storage/stats")
async def get_storage_stats():
    """Get storage statistics"""
    global data_manager
    if not data_manager:
        return {"error": "Data manager not initialized"}
    return data_manager.get_storage_stats()


@app.post("/api/storage/cleanup")
async def cleanup_storage(background_tasks: BackgroundTasks):
    """Manually trigger storage cleanup"""
    global data_manager
    if not data_manager:
        raise HTTPException(status_code=500, detail="Data manager not initialized")
    
    # Run cleanup in background
    background_tasks.add_task(data_manager.cleanup_old_training_data)
    background_tasks.add_task(data_manager.cleanup_old_recordings)
    background_tasks.add_task(data_manager.optimize_storage)
    
    return {"success": True, "message": "Cleanup started in background"}


@app.get("/api/workflows/{workflow_id}/transcript")
async def get_workflow_transcript(workflow_id: int):
    """Get transcript for a workflow"""
    global data_manager
    if not data_manager:
        raise HTTPException(status_code=500, detail="Data manager not initialized")
    
    transcript = data_manager.get_transcript(workflow_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    return transcript


class FindTextRequest(BaseModel):
    text: str
    timeout: float = 5.0


@app.post("/api/automation/find-text")
async def find_text_on_screen(request: FindTextRequest):
    """Find text on screen using OCR"""
    from automation.element_finder import get_element_finder
    
    search_text = request.text
    timeout = request.timeout
    
    # Validation is handled by Pydantic model
    
    element_finder = get_element_finder()
    result = element_finder.find_text(search_text, timeout=timeout)
    
    return {
        "found": result["found"],
        "center": result["center"],
        "bbox": result["bbox"],
        "text": result["text"],
        "confidence": result["confidence"]
    }


@app.get("/api/workflows/{workflow_id}/audio")
async def get_workflow_audio(workflow_id: int):
    """Get audio files and transcripts for a workflow"""
    global data_manager
    if not data_manager:
        raise HTTPException(status_code=500, detail="Data manager not initialized")
    
    transcript_data = data_manager.get_transcript(workflow_id)
    if not transcript_data:
        return {
            "audio_files": [],
            "transcripts": [],
            "has_audio": False
        }
    
    # Extract audio files and convert to URLs
    audio_files = transcript_data.get("audio_files", [])
    audio_urls = []
    
    recordings_dir = DATA_DIR / "recordings"
    
    for audio_file in audio_files:
        if isinstance(audio_file, str):
            # Convert file path to URL
            audio_path = Path(audio_file)
            filename = audio_path.name
            
            # Verify file exists (check both original path and recordings directory)
            file_exists = False
            actual_path = None
            
            if audio_path.exists():
                # File exists at original path
                file_exists = True
                actual_path = audio_path
            elif (recordings_dir / filename).exists():
                # File exists in recordings directory (might have been moved)
                file_exists = True
                actual_path = recordings_dir / filename
            else:
                # File doesn't exist - log warning but still include it
                print(f"   ⚠️  Audio file not found: {audio_file} or {recordings_dir / filename}")
            
            if file_exists or True:  # Include even if not found (might be in different location)
                audio_urls.append({
                    "filename": filename,
                    "url": f"/recordings/{filename}",
                    "path": str(actual_path) if actual_path else audio_file,
                    "exists": file_exists
                })
    
    return {
        "audio_files": audio_urls,
        "transcripts": transcript_data.get("transcripts", []),
        "has_audio": len(audio_urls) > 0,
        "workflow_id": workflow_id
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

