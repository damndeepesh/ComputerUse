"""
Independent step conversion module
Converts raw actions to workflow steps
DO NOT MODIFY TRACKING OR SAVING FUNCTIONALITY HERE
"""
import time


class StepConverter:
    """Independent step converter - converts actions to workflow steps"""
    
    def __init__(self):
        pass
    
    def convert_actions_to_steps(self, actions, screenshots=None, app_changes_list=None):
        """
        Convert raw actions to workflow steps
        This is the ONLY function that should convert actions to steps
        """
        steps = []
        
        if not actions:
            print("⚠️  No actions to convert to steps")
            return steps
        
        print(f"📝 Converting {len(actions)} actions to workflow steps...")
        
        # Count action types
        action_types = {}
        for action in actions:
            action_type = action.get("type", "unknown")
            action_types[action_type] = action_types.get(action_type, 0) + 1
        print(f"   📊 Input actions: {action_types}")
        
        # Convert each action to a step
        skipped_count = 0
        for i, action in enumerate(actions):
            step = self._convert_action_to_step(action, screenshots, i, len(actions))
            if step:
                steps.append(step)
            else:
                skipped_count += 1
                action_type = action.get("type", "unknown")
                print(f"   ⚠️  Skipped action #{i+1}: type={action_type} (converter returned None)")
        
        if skipped_count > 0:
            print(f"   ⚠️  WARNING: {skipped_count} actions were skipped during conversion!")
        
        # Add app activation steps
        if app_changes_list:
            for app_change in app_changes_list:
                # Handle app_change structure from app_tracker
                # app_changes have: to_app, bundle_id, url, timestamp directly
                to_app = app_change.get('to_app')
                if not to_app:
                    # Skip if no target app
                    continue
                
                app_step = {
                    "action": "app_activate",
                    "description": f"Opened/Activated: {to_app}",
                    "app_name": to_app,
                    "app_bundle_id": app_change.get('bundle_id'),
                    "app_url": app_change.get('url'),
                    "timestamp": app_change.get('timestamp', 0),
                }
                steps.append(app_step)
        
        # Sort by timestamp
        if steps:
            steps.sort(key=lambda s: s.get('timestamp', 0))
        
        # CRITICAL: Verify all actions were converted
        if len(steps) != len(actions):
            print(f"   ⚠️  WARNING: {len(actions)} actions input but {len(steps)} steps output!")
            print(f"   ⚠️  Missing {len(actions) - len(steps)} steps!")
            print(f"   ⚠️  This means some actions were not converted to steps")
        else:
            print(f"✅ Converted {len(actions)} actions to {len(steps)} steps (all converted)")
        
        return steps
    
    def _convert_action_to_step(self, action, screenshots, index, total_actions):
        """Convert a single action to a step - ALWAYS returns a step"""
        action_type = action.get("type")
        
        # CRITICAL: If action_type is missing, log warning but still create a step
        if not action_type:
            print(f"   ⚠️  Action #{index+1} missing type field: {action}")
            action_type = "unknown"
        
        timestamp = action.get("timestamp", 0)
        
        # Handle timestamp conversion
        if isinstance(timestamp, str):
            from datetime import datetime
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()
            except:
                timestamp = 0
        
        # Base step - ALWAYS create a step, even for unknown types
        step = {
            "action": action_type,
            "timestamp": timestamp,
            "app_name": action.get("app_name"),
            "app_bundle_id": action.get("app_bundle_id"),
        }
        
        # Find screenshot for this action
        if screenshots:
            screenshot_index = min(index, len(screenshots) - 1) if total_actions > 0 else 0
            screenshot_path = screenshots[screenshot_index]
            # Handle both Path objects and strings
            if screenshot_path:
                if isinstance(screenshot_path, (str, bytes)):
                    screenshot_filename = str(screenshot_path).split('/')[-1]
                else:
                    # Path object - use .name property
                    screenshot_filename = screenshot_path.name
                step["screenshot"] = f"/screenshots/{screenshot_filename}"
            else:
                step["screenshot"] = None
        
        # Convert based on action type
        if action_type == "move":
            step.update({
                "x": int(action.get("x", 0)),
                "y": int(action.get("y", 0)),
                "description": f"Move mouse to ({action.get('x', 0)}, {action.get('y', 0)})",
            })
        
        elif action_type == "click":
            step.update({
                "x": int(action.get("x", 0)),
                "y": int(action.get("y", 0)),
                "button": action.get("button", "left"),
                "clicks": action.get("clicks", 1),
            })
            
            if action.get('shift_pressed'):
                step['shift_pressed'] = True
                if action.get('is_selection_start'):
                    step['is_selection_start'] = True
                    step['selection_end_x'] = action.get('selection_end_x')
                    step['selection_end_y'] = action.get('selection_end_y')
                    step["description"] = f"Shift+click selection from ({action.get('x', 0)}, {action.get('y', 0)}) to ({action.get('selection_end_x')}, {action.get('selection_end_y')})"
                else:
                    step["description"] = f"Shift+click at ({action.get('x', 0)}, {action.get('y', 0)})"
            else:
                clicks = action.get("clicks", 1)
                if clicks == 2:
                    step["description"] = f"Double click at ({action.get('x', 0)}, {action.get('y', 0)})"
                else:
                    step["description"] = f"Click at ({action.get('x', 0)}, {action.get('y', 0)})"
        
        elif action_type == "scroll":
            step.update({
                "x": int(action.get("x", 0)),
                "y": int(action.get("y", 0)),
                "dx": action.get("dx", 0),
                "dy": action.get("dy", 0),
                "amount": action.get("dy", 0) * 100,
                "description": f"Scroll at ({action.get('x', 0)}, {action.get('y', 0)})",
            })
        
        elif action_type == "type":
            text = action.get("text", "")
            step.update({
                "text": text,
                "text_length": len(text) if isinstance(text, str) else 0,
                "description": f"Type: '{text[:50]}'",
            })
        
        elif action_type == "hotkey":
            keys = action.get("keys", [])
            operation = action.get("operation")
            step.update({
                "keys": keys,
                "key_sequence": action.get("key_sequence", []),
            })
            
            if operation == "copy":
                step["description"] = f"Copy to clipboard"
            elif operation == "paste":
                step["description"] = f"Paste from clipboard"
            elif operation == "cut":
                step["description"] = f"Cut to clipboard"
            else:
                step["description"] = f"Press {'+'.join(keys)}"
        
        elif action_type == "backspace":
            step.update({
                "description": "Press Backspace",
            })
        
        else:
            # Unknown action type - still create step with all available data
            print(f"   ⚠️  Unknown action type: {action_type} - creating generic step")
            step["description"] = f"{action_type} action"
            # Try to preserve any data from the action
            for key in ['x', 'y', 'text', 'keys', 'dx', 'dy']:
                if key in action:
                    step[key] = action[key]
        
        # Add spreadsheet context if available
        if action.get("spreadsheet_context"):
            step["spreadsheet_context"] = action.get("spreadsheet_context")
            if action.get("spreadsheet_context", {}).get('cell'):
                step["cell"] = action.get("spreadsheet_context", {}).get('cell')
        
        # CRITICAL: Always return a step, never None
        if not step.get("action"):
            step["action"] = "unknown"
        if not step.get("description"):
            step["description"] = f"Action at timestamp {step.get('timestamp', 0)}"
        
        return step

