import base64
import json
import requests
from PIL import Image
from pynput import mouse, keyboard
import threading
import time
import sys
import os

# Import local model manager and OCR
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models.model_manager import get_model_manager
from processing.ocr_engine import get_ocr_engine
from capture.app_tracker import describe_app_action


class WorkflowAnalyzer:
    def __init__(self):
        self.use_local_model = True  # Use local model instead of Ollama
        self.model_manager = None
        self.actions = []
        self.mouse_listener = None
        self.keyboard_listener = None
        
        # Initialize local model
        try:
            self.model_manager = get_model_manager()
            print("✅ Using local AI model (no Ollama required)")
        except Exception as e:
            print(f"⚠️  Could not initialize local model: {e}")
            print("Workflows will use basic analysis")
        
        # Initialize OCR engine (ENABLED for detailed descriptions)
        self.ocr_engine = None
        try:
            self.ocr_engine = get_ocr_engine()
            print("✅ OCR engine initialized for detailed screenshot analysis")
        except Exception as e:
            print(f"⚠️  Could not initialize OCR: {e}")
            self.ocr_engine = None
        
    async def analyze(self, screenshots, transcripts, actions=None, app_changes=None):
        """Analyze screenshots, transcripts, actions, and app changes to create a workflow"""
        
        steps = []
        
        # If we have transcripts, use them to understand intent
        intent = " ".join([t["text"] for t in transcripts]) if transcripts else "User workflow"
        
        # Build app context map (timestamp -> full app info)
        app_context = {}
        app_changes_list = []
        if app_changes:
            for change in app_changes:
                ts = change.get('timestamp', 0)
                app_info = {
                    'name': change.get('to_app', 'Unknown'),
                    'bundle_id': change.get('bundle_id', None),
                    'from_app': change.get('from_app', None),
                    'url': change.get('url', None),
                    'is_browser': change.get('is_browser', False),
                    'timestamp': ts
                }
                app_context[ts] = app_info['name']  # For backward compatibility
                app_changes_list.append({
                    'timestamp': ts,
                    'app_info': app_info
                })
        
        # Extract text from screenshots using OCR (ENABLED for detailed analysis)
        screenshot_texts = []
        screenshot_ocr_data = {}
        screenshot_ocr_regions = {}  # Store OCR regions for cell detection
        recording_screen_size = None
        if self.ocr_engine and screenshots:
            print(f"🔍 Analyzing {len(screenshots)} screenshots with OCR for detailed descriptions...")
            for i, screenshot_path in enumerate(screenshots):
                try:
                    if recording_screen_size is None:
                        try:
                            with Image.open(screenshot_path) as im:
                                recording_screen_size = im.size  # (width, height)
                                print(f"   🖥️  Recording screen size detected: {recording_screen_size[0]}x{recording_screen_size[1]}")
                        except Exception as img_e:
                            print(f"   ⚠️  Could not read screenshot size: {img_e}")
                    ocr_result = self.ocr_engine.extract_text(screenshot_path, detail_level=1)
                    if ocr_result.get("text"):
                        screenshot_texts.append(ocr_result["text"])
                        screenshot_ocr_data[i] = ocr_result["text"]
                        screenshot_ocr_regions[i] = ocr_result.get("regions", [])  # Store regions for cell detection
                        # Detect app names from OCR
                        text_lower = ocr_result["text"].lower()
                        if i < 3:  # Log first few
                            print(f"   Screenshot {i+1}: Found {len(ocr_result['text'])} chars of text, {len(ocr_result.get('regions', []))} text regions")
                except Exception as e:
                    print(f"   OCR error on screenshot {i}: {e}")
                    import traceback
                    traceback.print_exc()
        
        # Combine all context
        all_context = intent
        if screenshot_texts:
            all_context += " | Screen text: " + " | ".join(screenshot_texts[:3])
        
        # Build a map of actions by timestamp for efficient matching
        actions_by_timestamp = {}
        if actions and len(actions) > 0:
            for action in actions:
                ts = action.get("timestamp", 0)
                if isinstance(ts, str):
                    from datetime import datetime
                    try:
                        ts = datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
                    except:
                        ts = 0
                actions_by_timestamp[ts] = action
        
        # If we have tracked actions, convert them to steps
        if actions and len(actions) > 0:
            print(f"📝 Converting {len(actions)} tracked actions to workflow steps...")
            action_type_counts = {}
            for action in actions:
                action_type = action.get("type", "unknown")
                action_type_counts[action_type] = action_type_counts.get(action_type, 0) + 1
            print(f"   📊 Input action breakdown: {action_type_counts}")
            
            # CRITICAL: Warn if we have very few or no mouse actions
            mouse_actions = action_type_counts.get('move', 0) + action_type_counts.get('click', 0) + action_type_counts.get('scroll', 0)
            if mouse_actions == 0:
                print(f"   ⚠️  WARNING: No mouse actions (move/click/scroll) in input actions!")
                print(f"   ⚠️  This means mouse tracking may not be working during recording")
            elif mouse_actions < 3:
                print(f"   ⚠️  WARNING: Very few mouse actions ({mouse_actions}) compared to total ({len(actions)})")
            
            for i, action in enumerate(actions):
                step = self._convert_action_to_step(
                    action, screenshots, i, all_context, app_context, app_changes_list,
                    screenshot_ocr_regions=screenshot_ocr_regions,
                    total_actions=len(actions)
                )
                # Attach recording screen size for coordinate scaling at execution time
                if recording_screen_size:
                    step["screen_w"], step["screen_h"] = recording_screen_size[0], recording_screen_size[1]
                steps.append(step)
                if i < 5 or i == len(actions) - 1:  # Log first 5 and last one
                    print(f"   Step {i+1}/{len(actions)}: {step.get('action')} - {step.get('description', 'N/A')[:60]}")
                elif i == 5:
                    print(f"   ... (converting {len(actions) - 5} more actions)")
        
        # Add explicit app activation steps when apps change (will be sorted by timestamp)
        if app_changes_list:
            print(f"📱 Adding {len(app_changes_list)} app activation steps...")
            for app_change in app_changes_list:
                app_info = app_change['app_info']
                # Compute open delay as time until the first subsequent action in the same app
                open_delay_seconds = None
                if actions:
                    try:
                        next_same_app_action_ts = None
                        for a in actions:
                            ats = a.get("timestamp", 0)
                            if isinstance(ats, str):
                                from datetime import datetime
                                try:
                                    ats = datetime.fromisoformat(ats.replace('Z', '+00:00')).timestamp()
                                except:
                                    ats = 0
                            if ats > app_change['timestamp'] and (
                                a.get("app_name") == app_info['name'] or not a.get("app_name")
                            ):
                                next_same_app_action_ts = ats
                                break
                        if next_same_app_action_ts is not None:
                            open_delay_seconds = round(max(0.0, next_same_app_action_ts - app_change['timestamp']), 2)
                    except Exception:
                        open_delay_seconds = None
                app_step = {
                    "action": "app_activate",
                    "description": f"Opened/Activated: {app_info['name']}",
                    "app_name": app_info['name'],
                    "app_bundle_id": app_info.get('bundle_id'),
                    "app_url": app_info.get('url'),
                    "is_browser": app_info.get('is_browser', False),
                    "from_app": app_info.get('from_app'),
                    "timestamp": app_change['timestamp'],
                    "app_info": app_info,  # Full app information
                    "open_delay_seconds": open_delay_seconds
                }
                if app_info.get('url'):
                    app_step["description"] += f" ({app_info['url']})"
                steps.append(app_step)
                print(f"   📱 App: {app_info['name']} (bundle: {app_info.get('bundle_id', 'N/A')})")
        
        # ALWAYS create steps from screenshots - this ensures we capture all activity
        # If we have significantly more screenshots than actions, create screenshot steps
        # This handles cases where actions weren't captured but screenshots were
        if screenshots:
            num_action_steps = len([s for s in steps if s.get('action') not in ['app_activate', 'screenshot']])
            num_screenshots = len(screenshots)
            
            # If we have many screenshots but few action steps, create screenshot steps
            # This ensures we don't lose information when actions aren't fully captured
            # Create screenshot steps if:
            # 1. No action steps at all, OR
            # 2. We have at least 3x more screenshots than action steps (very few actions captured), OR
            # 3. We have 5+ screenshots but only 1-2 action steps (clear mismatch)
            should_create_screenshot_steps = (
                num_action_steps == 0 or 
                num_screenshots >= num_action_steps * 3 or 
                (num_screenshots >= 5 and num_action_steps <= 2)
            )
            
            if should_create_screenshot_steps:
                print(f"📸 Creating steps from {num_screenshots} screenshots (have {num_action_steps} action steps)...")
                screenshot_steps_by_path = {}
                
                # Limit to creating screenshot steps for every 3rd screenshot to avoid too many wait steps
                # This creates steps at key moments without overwhelming the workflow
                screenshot_interval = 3 if num_screenshots > 10 else 1
                
                last_index = len(screenshots) - 1
                for i, screenshot_path in enumerate(screenshots):
                    # Only process every Nth screenshot to avoid creating too many wait steps
                    if i % screenshot_interval != 0 and i != last_index:
                        continue
                    
                    # Check if this screenshot is already associated with an action step
                    # Handle both Path objects and strings
                    if isinstance(screenshot_path, (str, bytes)):
                        screenshot_filename = str(screenshot_path).split('/')[-1]
                    else:
                        screenshot_filename = screenshot_path.name
                    already_has_step = any(
                        s.get('screenshot', '').endswith(screenshot_filename) 
                        for s in steps 
                        if s.get('screenshot')
                    )
                    
                    # Only create screenshot step if it doesn't already have an action step
                    if not already_has_step:
                        # Generate detailed description from OCR text
                        description = f"Step {i+1}"
                        ocr_text = screenshot_ocr_data.get(i, "")
                        
                        if ocr_text:
                            # Clean OCR text - remove very short words, special chars that look like OCR errors
                            import re
                            # Split into words and filter out single/double character words that are likely OCR errors
                            words = ocr_text.split()
                            cleaned_words = []
                            for word in words:
                                # Keep words that are at least 3 chars, or are common short words
                                if len(word) >= 3 or word.lower() in ['in', 'on', 'at', 'to', 'of', 'is', 'it', 'a', 'an', 'the']:
                                    # Remove characters that are likely OCR errors (too many special chars)
                                    if re.match(r'^[a-zA-Z0-9\s.,!?;:\-]{2,}$', word) or len(word) <= 2:
                                        cleaned_words.append(word)
                            
                            cleaned_text = " ".join(cleaned_words[:20])  # Limit to first 20 words
                            
                            # Detect what's happening from OCR text
                            text_lower = cleaned_text.lower()
                            
                            # Detect app openings
                            if "notes" in text_lower and i == 0:
                                description = "Opened Notes app"
                            elif "chrome" in text_lower or "google" in text_lower:
                                description = "Using Google Chrome"
                            elif "settings" in text_lower or "system preferences" in text_lower:
                                description = "Opened System Settings"
                            elif "finder" in text_lower:
                                description = "Using Finder"
                            elif "mail" in text_lower:
                                description = "Using Mail app"
                            elif "safari" in text_lower:
                                description = "Using Safari"
                            elif "spotify" in text_lower:
                                description = "Using Spotify"
                            elif "slack" in text_lower:
                                description = "Using Slack"
                            elif "discord" in text_lower:
                                description = "Using Discord"
                            elif "terminal" in text_lower:
                                description = "Using Terminal"
                            elif "code" in text_lower or "cursor" in text_lower or "electron" in text_lower:
                                description = "Using Code Editor"
                            else:
                                # Extract first meaningful words (first 3-5 words)
                                if cleaned_words:
                                    first_words = " ".join(cleaned_words[:5])
                                    description = f"Screen shows: {first_words}..."
                                else:
                                    description = f"Screenshot {i+1}"
                        else:
                            description = f"Screenshot {i+1}"
                        
                        # Estimate timestamp based on screenshot index (screenshots are taken every 2 seconds)
                        screenshot_timestamp = time.time() - (len(screenshots) - i) * 2.0
                        
                        screenshot_step = {
                            "action": "wait",  # Change to "wait" so executor handles it properly
                            "description": description,
                            "screenshot": f"/screenshots/{screenshot_filename}",
                            "timestamp": screenshot_timestamp,
                            "duration": 0.5,  # Short wait for screenshot steps (just to mark time passing)
                            "continue_on_error": True,  # Don't fail workflow if screenshot step fails
                            # Don't include raw OCR text in steps - it's too noisy and makes JSON look bad
                            # OCR is only used for generating descriptions
                        }
                        if recording_screen_size:
                            screenshot_step["screen_w"], screenshot_step["screen_h"] = recording_screen_size[0], recording_screen_size[1]
                        
                        screenshot_steps_by_path[screenshot_path] = screenshot_step
                
                # Add screenshot steps (only those not already covered by actions)
                steps.extend(screenshot_steps_by_path.values())
                print(f"   ✅ Added {len(screenshot_steps_by_path)} screenshot-based steps")
        
        # Sort all steps by timestamp to maintain chronological order
        if steps:
            steps.sort(key=lambda s: s.get('timestamp', 0))
            print(f"✅ Total {len(steps)} steps created (sorted by timestamp)")

            # Merge adjacent typing steps to avoid fragmented text like "chr" + "om"
            steps = self._merge_adjacent_typing_steps(steps)
            
            # Merge consecutive move steps into path segments to reduce step count
            # BUT: Keep at least some moves to ensure mouse movement is visible
            steps_before_merge = len(steps)
            steps = self._merge_consecutive_moves(steps)
            steps_after_merge = len(steps)
            
            # Warn if we merged away ALL moves
            move_steps = [s for s in steps if s.get('action') == 'move']
            if steps_before_merge > steps_after_merge and len(move_steps) == 0:
                print(f"⚠️  WARNING: All move steps were merged away! Had {steps_before_merge} steps, now {steps_after_merge}")
                print(f"⚠️  This means mouse movement will NOT be visible during execution")
        
        # Try to use local model for better analysis
        try:
            print(f"🤖 Generating workflow name and description...")
            workflow_name = await self._generate_workflow_name(all_context, len(steps))
            workflow_description = await self._generate_description(all_context, screenshots)
            
            # Enhanced step analysis - skip for now to save time
            # enhanced_steps = await self._analyze_steps_with_llm(steps, transcripts)
            # if enhanced_steps:
            #     steps = enhanced_steps
            
            print(f"✅ Generated: {workflow_name}")
                
        except Exception as e:
            import traceback
            print(f"⚠️  Error using LLM for analysis: {e}")
            print(traceback.format_exc())
            workflow_name = f"Workflow {time.strftime('%Y-%m-%d %H:%M')}"
            workflow_description = all_context[:100] if all_context else "Recorded workflow"
        
        return {
            "name": workflow_name,
            "description": workflow_description,
            "steps": steps,
        }

    def _merge_adjacent_typing_steps(self, steps):
        """Merge consecutive 'type' steps that are close in time and context.

        Rules:
        - Merge only if both steps are 'type', same app_name (or both None), and time delta <= 2s
        - Do not merge across non-type actions (click/hotkey/scroll/etc.)
        - Preserve spaces exactly as recorded
        - Carry forward metadata (text_length recalculated)
        """
        if not steps:
            return steps
        merged = []
        buffer = None

        def flush_buffer():
            nonlocal buffer
            if buffer is not None:
                # Update derived fields
                if isinstance(buffer.get("text"), str):
                    buffer["text_length"] = len(buffer["text"])  # executor ignores, but informative
                    # Update description if present and was generic
                    if buffer.get("description") and buffer["description"].startswith("Type"):
                        preview = buffer["text"][:30]
                        buffer["description"] = f"Type: '{preview}{'...' if len(buffer['text'])>30 else ''}'"
                merged.append(buffer)
                buffer = None

        for step in steps:
            if step.get("action") == "type" and isinstance(step.get("text"), str):
                if buffer is None:
                    buffer = dict(step)
                else:
                    # Check merge eligibility
                    same_app = (buffer.get("app_name") == step.get("app_name"))
                    t1 = buffer.get("timestamp", 0) or 0
                    t2 = step.get("timestamp", 0) or 0
                    close_in_time = (abs(t2 - t1) <= 3.0)
                    if same_app and close_in_time:
                        # Merge text
                        buffer_text = buffer.get("text", "")
                        step_text = step.get("text", "")
                        buffer["text"] = f"{buffer_text}{step_text}"
                        # Expand timestamp to the later step (end)
                        buffer["timestamp"] = max(t1, t2)
                        # Carry over screenshot if missing
                        if not buffer.get("screenshot") and step.get("screenshot"):
                            buffer["screenshot"] = step.get("screenshot")
                        continue
                    else:
                        flush_buffer()
                        buffer = dict(step)
            else:
                # Non-type action breaks the chain
                flush_buffer()
                merged.append(step)

        flush_buffer()
        if len(merged) != len(steps):
            print(f"✏️  Merged typing steps: {len(steps)} -> {len(merged)}")
        return merged
    
    def _merge_consecutive_moves(self, steps):
        """Merge consecutive 'move' steps into path segments to reduce step count.
        
        Rules:
        - Merge consecutive move steps that are within 0.5 seconds of each other
        - Only keep start and end points of each path segment
        - BUT: Always keep at least one move per segment to ensure mouse movement is visible
        - This dramatically reduces step count while preserving the path
        """
        if not steps:
            return steps
        
        merged = []
        move_buffer = []
        
        def flush_move_buffer():
            nonlocal move_buffer
            if len(move_buffer) > 0:
                # Keep only the first and last move in the sequence
                if len(move_buffer) > 1:
                    # Keep first move (start of path)
                    merged.append(move_buffer[0])
                    # Keep last move (end of path) - this represents the destination
                    merged.append(move_buffer[-1])
                    if len(move_buffer) > 2:
                        print(f"   📍 Merged {len(move_buffer)} consecutive moves into start/end points (kept 2)")
                else:
                    # Single move, keep it
                    merged.append(move_buffer[0])
                move_buffer = []
        
        for step in steps:
            action = step.get("action", "").lower()
            
            if action == "move":
                if not move_buffer:
                    # Start new buffer
                    move_buffer.append(step)
                else:
                    # Check if this move is consecutive (within 0.5s of last move)
                    last_timestamp = move_buffer[-1].get("timestamp", 0)
                    current_timestamp = step.get("timestamp", 0)
                    
                    if current_timestamp - last_timestamp <= 0.5:
                        # Consecutive move, add to buffer
                        move_buffer.append(step)
                    else:
                        # Gap in moves, flush buffer and start new one
                        flush_move_buffer()
                        move_buffer.append(step)
            else:
                # Non-move action breaks the chain
                flush_move_buffer()
                merged.append(step)
        
        # Flush any remaining moves
        flush_move_buffer()
        
        # Count moves before and after
        moves_before = len([s for s in steps if s.get("action", "").lower() == "move"])
        moves_after = len([s for s in merged if s.get("action", "").lower() == "move"])
        
        if len(merged) != len(steps):
            print(f"🖱️  Merged move steps: {len(steps)} -> {len(merged)} (reduced by {len(steps) - len(merged)} steps)")
            print(f"   📊 Move actions: {moves_before} -> {moves_after}")
            
            # CRITICAL: If we removed ALL moves, warn the user
            if moves_before > 0 and moves_after == 0:
                print(f"   ⚠️  WARNING: All {moves_before} move actions were merged away!")
                print(f"   ⚠️  Mouse movement will NOT be visible during execution!")
                print(f"   ⚠️  Consider reducing move merging or keeping more move steps")
        
        return merged
    
    async def _generate_workflow_name(self, intent, num_steps):
        """Generate a workflow name using local LLM"""
        # For now, use simple naming to speed up workflow creation
        # AI model download and first inference takes too long
        timestamp = time.strftime('%Y-%m-%d %H:%M')
        if intent and intent != "User workflow":
            # Extract first few words from intent
            words = intent.split()[:5]
            name = " ".join(words)
            if len(name) > 50:
                name = name[:50] + "..."
            return name
        return f"Workflow {timestamp}"
        
        # Disabled for speed - uncomment to use AI
        # if not self.model_manager:
        #     return f"Workflow with {num_steps} steps"
        # 
        # prompt = f"Generate a short workflow name (max 5 words) for: {intent}\nWorkflow name:"
        # 
        # try:
        #     name = self.model_manager.generate(prompt, max_length=50, temperature=0.7)
        #     name = name.strip().split('\n')[0].strip()
        #     if len(name) > 50:
        #         name = name[:50].strip()
        #     return name if name else f"Workflow with {num_steps} steps"
        # except Exception as e:
        #     print(f"Error generating name: {e}")
        #     return f"Workflow with {num_steps} steps"
    
    async def _generate_description(self, intent, screenshots):
        """Generate workflow description using local LLM"""
        # For now, use simple description to speed up workflow creation
        if intent and intent != "User workflow":
            desc = intent[:200]
            return desc if desc else "Automated workflow"
        return f"Recorded workflow with {len(screenshots)} screenshots"
        
        # Disabled for speed - uncomment to use AI
        # if not self.model_manager:
        #     return intent[:200] if intent else "Automated workflow"
        # 
        # prompt = f"Generate a brief one-sentence description for this workflow: {intent}\nDescription:"
        # 
        # try:
        #     description = self.model_manager.generate(prompt, max_length=100, temperature=0.7)
        #     description = description.strip().split('\n')[0].strip()
        #     if len(description) > 200:
        #         description = description[:200].strip()
        #     return description if description else intent[:200]
        # except Exception as e:
        #     print(f"Error generating description: {e}")
        #     return intent[:200] if intent else "Automated workflow"
    
    async def _analyze_steps_with_llm(self, steps, transcripts):
        """Use local LLM to enhance step descriptions"""
        if not self.model_manager:
            return steps
        
        # Combine transcript context
        context = " ".join([t["text"] for t in transcripts]) if transcripts else ""
        
        enhanced_steps = []
        for i, step in enumerate(steps):
            # For local model, we'll use simpler prompts and fallback to original step
            try:
                action_type = step.get("action", "other")
                
                if context:
                    prompt = f"Context: {context}\nDescribe this action in one sentence: {action_type}\nDescription:"
                    
                    description = self.model_manager.generate(prompt, max_length=80, temperature=0.7)
                    description = description.strip().split('\n')[0].strip()
                    
                    if description and len(description) > 10:
                        step["description"] = description[:100]
                
                enhanced_steps.append(step)
                
            except Exception as e:
                print(f"Error analyzing step {i}: {e}")
                enhanced_steps.append(step)
        
        return enhanced_steps if enhanced_steps else steps
    
    def _convert_action_to_step(self, action, screenshots, index, intent, app_context=None, app_changes_list=None, screenshot_ocr_regions=None, total_actions=None):
        """Convert a tracked action to a workflow step with app context and OCR enhancement"""
        action_type = action.get("type", "other")
        # Handle both ISO timestamp strings and Unix timestamps
        timestamp = action.get("timestamp", 0)
        if isinstance(timestamp, str):
            # Convert ISO string to Unix timestamp
            from datetime import datetime
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()
            except:
                timestamp = 0
        
        # Get app context from action itself (most accurate - captured at time of action)
        current_app_name = action.get("app_name")
        current_app_bundle_id = action.get("app_bundle_id")
        spreadsheet_context = action.get("spreadsheet_context")
        
        # Find the app that was active at this time (with full details) - fallback if not in action
        current_app_info = None
        if not current_app_name and app_context and app_changes_list:
            # Find the closest app change before this action
            closest_change = None
            closest_ts = None
            for change in app_changes_list:
                if change['timestamp'] <= timestamp:
                    if closest_ts is None or change['timestamp'] > closest_ts:
                        closest_ts = change['timestamp']
                        closest_change = change
            
            if closest_change:
                current_app_info = closest_change['app_info']
                current_app_name = current_app_info['name']
                current_app_bundle_id = current_app_info.get('bundle_id')
        
        # Fallback to simple app_context if app_changes_list not available
        if not current_app_name and app_context:
            closest_ts = max([ts for ts in app_context.keys() if ts <= timestamp], default=None)
            if closest_ts:
                current_app_name = app_context[closest_ts]
        
        # If we have app info from app_changes_list, use it
        if not current_app_info and app_changes_list:
            for change in app_changes_list:
                if change['timestamp'] <= timestamp:
                    current_app_info = change['app_info']
                    break
        
        # Find closest screenshot to this action (try to match by timestamp)
        screenshot_path = None
        screenshot_index = None
        if screenshots:
            # CRITICAL: Ensure every step gets a screenshot
            # Strategy: Map action index to screenshot index, ensuring all screenshots are used
            if len(screenshots) > 0:
                # Calculate screenshot index based on action index
                # Use total_actions if provided, otherwise fall back to simple index mapping
                if total_actions and total_actions > 0:
                    # If we have more screenshots than actions, distribute evenly
                    if len(screenshots) >= total_actions:
                        # More screenshots than actions - map each action to a unique screenshot
                        screenshot_index = min(index, len(screenshots) - 1)
                    else:
                        # Fewer screenshots than actions - reuse screenshots with modulo
                        screenshot_index = index % len(screenshots)
                else:
                    # Fallback: simple mapping
                    screenshot_index = min(index, len(screenshots) - 1)
                
                # Ensure we never go out of bounds
                screenshot_index = min(screenshot_index, len(screenshots) - 1)
                screenshot_path = screenshots[screenshot_index]
                
                # Log screenshot assignment for debugging (first few and last)
                if index < 3 or (total_actions and index == total_actions - 1):
                    print(f"   📸 Assigned screenshot {screenshot_index+1}/{len(screenshots)} to action {index+1}/{total_actions if total_actions else '?'}")
            
            # If we have spreadsheet context but no cell detected, try OCR on the screenshot
            if spreadsheet_context and spreadsheet_context.get('is_spreadsheet') and not spreadsheet_context.get('cell'):
                if action_type in ["click", "type"]:
                    x = action.get("x", 0)
                    y = action.get("y", 0)
                    # Try to detect cell from screenshot using OCR
                    if screenshot_ocr_regions and screenshot_index in screenshot_ocr_regions:
                        cell_info = self._detect_cell_from_ocr_regions(
                            x, y, screenshot_ocr_regions[screenshot_index], current_app_name
                        )
                        if cell_info:
                            spreadsheet_context = cell_info
                            print(f"   📊 Detected cell {cell_info.get('cell')} from OCR")
        
        step = {
            "action": action_type,
            "timestamp": timestamp,
            "app": current_app_name,  # App name for backward compatibility
            "app_name": current_app_name,  # Explicit app name (from action or app_changes)
            "app_bundle_id": current_app_bundle_id or (current_app_info.get('bundle_id') if current_app_info else None),
            "app_url": current_app_info.get('url') if current_app_info else None,  # URL if browser
            "app_info": current_app_info if current_app_info else None,  # Full app information
            "screenshot": f"/screenshots/{screenshot_path.name if hasattr(screenshot_path, 'name') else str(screenshot_path).split('/')[-1]}" if screenshot_path else None,
        }
        
        # Add spreadsheet context if available
        if spreadsheet_context:
            step["spreadsheet_context"] = spreadsheet_context
            if spreadsheet_context.get('cell'):
                step["cell"] = spreadsheet_context.get('cell')  # e.g., "A1"
                step["row"] = spreadsheet_context.get('row')
                step["column"] = spreadsheet_context.get('column')
        
        # Add clipboard content for copy/paste operations
        clipboard_content = action.get("clipboard_content")
        clipboard_length = action.get("clipboard_length")
        operation = action.get("operation")  # "copy" or "paste"
        if operation:
            step["operation"] = operation
            if clipboard_content:
                step["clipboard_content"] = clipboard_content
                step["clipboard_length"] = clipboard_length or len(clipboard_content)
        
        # Try to extract URL from typed text if it looks like a URL
        if action_type == "type":
            text = action.get("text", "")
            if text and ("http://" in text or "https://" in text or "www." in text):
                # Extract URL from typed text
                import re
                url_match = re.search(r'https?://[^\s]+|www\.[^\s]+', text)
                if url_match:
                    step["url"] = url_match.group(0)
                    step["app_url"] = step["url"]  # Also set app_url
                    print(f"   🌐 Detected URL: {step['url']}")
        
        # Generate smart descriptions based on app and action
        if action_type == "click":
            x = int(action.get("x", 0))
            y = int(action.get("y", 0))
            button = action.get("button", "left")
            clicks = action.get("clicks", 1)  # Get clicks count (1 for single, 2 for double)
            
            # Normalize button name
            button_normalized = button.lower()
            if 'right' in button_normalized:
                button_normalized = 'right'
            elif 'middle' in button_normalized:
                button_normalized = 'middle'
            else:
                button_normalized = 'left'
            
            step.update({
                "x": x,
                "y": y,
                "button": button_normalized,
                "clicks": clicks,  # Include clicks count in step
            })
            
            # Handle Shift+click selections
            if action.get('shift_pressed'):
                step['shift_pressed'] = True
                if action.get('is_selection_start'):
                    step['is_selection_start'] = True
                    step['selection_end_x'] = action.get('selection_end_x')
                    step['selection_end_y'] = action.get('selection_end_y')
                    step["description"] = f"Shift+click selection from ({x}, {y}) to ({step.get('selection_end_x')}, {step.get('selection_end_y')}) in {current_app_name or 'application'}"
                else:
                    step["description"] = f"Shift+click at ({x}, {y}) in {current_app_name or 'application'}"

            # Use OCR to attach a nearby anchor text for smarter replay (find_by_text)
            try:
                if screenshot_ocr_regions and screenshot_index in screenshot_ocr_regions:
                    regions = screenshot_ocr_regions[screenshot_index]
                    nearest = None
                    for region in regions:
                        text = (region.get('text') or '').strip()
                        bbox = region.get('bbox') or {}
                        if not text or not bbox:
                            continue
                        # Region center
                        cx = bbox.get('x', 0) + bbox.get('width', 0) / 2
                        cy = bbox.get('y', 0) + bbox.get('height', 0) / 2
                        dist = ((cx - x) ** 2 + (cy - y) ** 2) ** 0.5
                        # Prefer short meaningful texts within radius
                        if dist <= 120 and 2 <= len(text) <= 40:
                            score = dist + max(0, len(text) - 20) * 2
                            if not nearest or score < nearest['score']:
                                nearest = { 'text': text, 'score': score }
                    if nearest:
                        step["find_by_text"] = nearest['text'][:50]
            except Exception as e:
                # Non-fatal: continue without OCR anchor
                pass
            
            # Generate description based on click type and context
            click_type = "double click" if clicks == 2 else f"{button_normalized} click"
            
            # Enhanced description with spreadsheet cell info
            if spreadsheet_context and spreadsheet_context.get('cell'):
                cell = spreadsheet_context.get('cell')
                if clicks == 2:
                    step["description"] = f"Double click on cell {cell} in {current_app_name or 'spreadsheet'}"
                elif button_normalized == 'right':
                    step["description"] = f"Right click on cell {cell} in {current_app_name or 'spreadsheet'}"
                else:
                    step["description"] = f"Click on cell {cell} in {current_app_name or 'spreadsheet'}"
            elif current_app_name:
                if clicks == 2:
                    step["description"] = f"Double click in {current_app_name}"
                elif button_normalized == 'right':
                    step["description"] = f"Right click in {current_app_name}"
                elif button_normalized == 'middle':
                    step["description"] = f"Middle click in {current_app_name}"
                else:
                    step["description"] = describe_app_action(current_app_name, "click")
            else:
                if clicks == 2:
                    step["description"] = f"Double click at ({x}, {y})"
                else:
                    step["description"] = f"{button_normalized.capitalize()} click at ({x}, {y})"
                
        elif action_type == "type":
            text = action.get("text", "")
            step.update({
                "text": text,
                "text_length": len(text) if isinstance(text, str) else 0,
            })
            
            # Enhanced description with spreadsheet cell info
            if spreadsheet_context and spreadsheet_context.get('cell'):
                cell = spreadsheet_context.get('cell')
                step["description"] = f"Type '{text[:30]}' in cell {cell} of {current_app_name or 'spreadsheet'}"
            elif current_app_name:
                step["description"] = describe_app_action(current_app_name, "type", text[:30])
            else:
                step["description"] = f"Type: '{text[:50]}'"
                
        elif action_type == "hotkey":
            keys = action.get("keys", [])
            step.update({
                "keys": keys,
            })
            
            # Enhanced description for copy/paste/cut operations
            if operation == "copy":
                if clipboard_content:
                    preview = clipboard_content[:30].replace('\n', ' ')
                    step["description"] = f"Copy to clipboard: '{preview}...' ({clipboard_length} chars) in {current_app_name or 'application'}"
                else:
                    step["description"] = f"Copy to clipboard in {current_app_name or 'application'}"
            elif operation == "paste":
                if clipboard_content:
                    preview = clipboard_content[:30].replace('\n', ' ')
                    step["description"] = f"Paste from clipboard: '{preview}...' ({clipboard_length} chars) in {current_app_name or 'application'}"
                else:
                    step["description"] = f"Paste from clipboard in {current_app_name or 'application'}"
            elif operation == "cut":
                if clipboard_content:
                    preview = clipboard_content[:30].replace('\n', ' ')
                    step["description"] = f"Cut to clipboard: '{preview}...' ({clipboard_length} chars) in {current_app_name or 'application'}"
                else:
                    step["description"] = f"Cut to clipboard in {current_app_name or 'application'}"
            elif current_app_name:
                step["description"] = describe_app_action(current_app_name, "hotkey", '+'.join(keys))
            else:
                step["description"] = f"Press {'+'.join(keys)}"
                
        elif action_type == "scroll":
            step.update({
                "x": int(action.get("x", 0)),
                "y": int(action.get("y", 0)),
                "dx": action.get("dx", 0),
                "dy": action.get("dy", 0),
                "amount": action.get("dy", 0) * 100,  # Convert to scroll amount
            })
            
            if current_app_name:
                step["description"] = f"Scroll in {current_app_name}"
            else:
                step["description"] = f"Scroll"
                
        elif action_type == "move":
            x = int(action.get("x", 0))
            y = int(action.get("y", 0))
            step.update({
                "x": x,
                "y": y,
            })
            
            # Always include coordinates in description for debugging
            if current_app_name:
                step["description"] = f"Move mouse to ({x}, {y}) in {current_app_name}"
            else:
                step["description"] = f"Move mouse to ({x}, {y})"
            
            print(f"   🖱️  Converted move action to step: ({x}, {y})")
        else:
            step["description"] = "Unknown action"
        
        return step
    
    def _detect_cell_from_ocr_regions(self, x, y, ocr_regions, app_name):
        """
        Detect spreadsheet cell position from OCR regions
        
        Args:
            x, y: Click coordinates
            ocr_regions: List of OCR regions with text and bbox
            app_name: Name of the app
            
        Returns:
            dict with cell info or None
        """
        if not ocr_regions:
            return None
        
        # Column headers (A-Z)
        column_headers = [chr(i) for i in range(ord('A'), ord('Z') + 1)]
        # Row numbers (1-99)
        row_numbers = [str(i) for i in range(1, 100)]
        
        detected_columns = []
        detected_rows = []
        
        for region in ocr_regions:
            text = region.get('text', '').strip().upper()
            bbox = region.get('bbox', {})
            
            if not text or not bbox:
                continue
            
            # Check for column headers (A, B, C, ...) - usually above the cell
            if text in column_headers and bbox.get('y', 0) < y:
                detected_columns.append({
                    'text': text,
                    'bbox': bbox,
                    'distance': abs((bbox.get('x', 0) + bbox.get('width', 0) / 2) - x)
                })
            
            # Check for row numbers (1, 2, 3, ...) - usually to the left of the cell
            if text.isdigit() and text in row_numbers and bbox.get('x', 0) < x:
                try:
                    row_num = int(text)
                    detected_rows.append({
                        'text': text,
                        'row': row_num,
                        'bbox': bbox,
                        'distance': abs((bbox.get('y', 0) + bbox.get('height', 0) / 2) - y)
                    })
                except ValueError:
                    pass
        
        # Sort by proximity to click position
        detected_columns.sort(key=lambda col: col['distance'])
        detected_rows.sort(key=lambda row: row['distance'])
        
        column = detected_columns[0]['text'] if detected_columns else None
        row = detected_rows[0]['row'] if detected_rows else None
        
        if column and row:
            cell_info = {
                'column': column,
                'row': row,
                'cell': f"{column}{row}",
                'detected': True,
                'app_name': app_name,
                'is_spreadsheet': True
            }
            return cell_info
        
        return None
    
    def _image_to_base64(self, image_path):
        """Convert image to base64 for API calls"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

