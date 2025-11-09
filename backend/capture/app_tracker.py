"""
Application Tracker - Detects which app is active/opened during recording
"""

import time
import threading
from AppKit import NSWorkspace

class AppTracker:
    """Track active applications during recording"""
    
    def __init__(self):
        self.is_tracking = False
        self.tracking_thread = None
        self.app_changes = []
        self.current_app = None
    
    def start(self):
        """Start tracking active applications"""
        if self.is_tracking:
            return
        
        self.is_tracking = True
        self.app_changes = []
        self.current_app = self._get_active_app()
        
        # Record the initial app as an app change
        if self.current_app:
            initial_change = {
                'type': 'app_change',
                'from_app': None,
                'to_app': self.current_app['name'],
                'bundle_id': self.current_app.get('bundle_id'),
                'timestamp': self.current_app['timestamp'],
            }
            self.app_changes.append(initial_change)
            print(f"📱 Initial app: {self.current_app['name']}")
        
        self.tracking_thread = threading.Thread(target=self._track_apps, daemon=True)
        self.tracking_thread.start()
        
        print("Application tracking started")
    
    def stop(self):
        """Stop tracking and return app changes"""
        if not self.is_tracking:
            return []
        
        self.is_tracking = False
        
        print(f"Application tracking stopped. Detected {len(self.app_changes)} app changes")
        return self.app_changes.copy()
    
    def _get_active_app(self):
        """Get currently active application with URL if it's a browser"""
        try:
            workspace = NSWorkspace.sharedWorkspace()
            active_app = workspace.frontmostApplication()
            
            app_info = {
                'name': active_app.localizedName(),
                'bundle_id': active_app.bundleIdentifier(),
                'timestamp': time.time(),
                'url': None
            }
            
            # Try to get URL for browsers
            try:
                bundle_id = app_info['bundle_id']
                if bundle_id:
                    # Check if it's a browser
                    if 'chrome' in bundle_id.lower() or 'safari' in bundle_id.lower() or 'firefox' in bundle_id.lower():
                        # Try to get URL from browser (this is limited on macOS)
                        # We'll extract URLs from OCR later if needed
                        app_info['is_browser'] = True
            except:
                pass
            
            return app_info
        except Exception as e:
            print(f"Error getting active app: {e}")
            return None
    
    def _track_apps(self):
        """Background thread to track app changes"""
        while self.is_tracking:
            try:
                current = self._get_active_app()
                
                if current and (not self.current_app or current['name'] != self.current_app['name']):
                    # App changed!
                    change = {
                        'type': 'app_change',
                        'from_app': self.current_app['name'] if self.current_app else None,
                        'to_app': current['name'],
                        'bundle_id': current.get('bundle_id'),
                        'url': current.get('url'),
                        'is_browser': current.get('is_browser', False),
                        'timestamp': current['timestamp'],
                    }
                    
                    self.app_changes.append(change)
                    print(f"📱 App changed: {change['from_app']} → {change['to_app']} (bundle: {change.get('bundle_id', 'N/A')})")
                    
                    self.current_app = current
                
                time.sleep(0.5)  # Check every 500ms
                
            except Exception as e:
                print(f"Error in app tracking: {e}")
                time.sleep(1)
    
    def get_current_app(self):
        """Get the currently active app"""
        return self._get_active_app()


# Helper function to generate app-based descriptions
def describe_app_action(app_name, action_type, details=None):
    """Generate human-readable descriptions based on app and action"""
    
    app_name_lower = app_name.lower() if app_name else ""
    
    # Common app patterns
    if 'settings' in app_name_lower or 'preferences' in app_name_lower:
        if action_type == 'click':
            return f"Click in System Settings"
        elif action_type == 'type':
            return f"Search in Settings: '{details}'"
        return f"Interact with System Settings"
    
    elif 'chrome' in app_name_lower or 'safari' in app_name_lower or 'firefox' in app_name_lower:
        browser = 'Chrome' if 'chrome' in app_name_lower else ('Safari' if 'safari' in app_name_lower else 'Firefox')
        if action_type == 'type':
            return f"Type in {browser}: '{details}'"
        elif action_type == 'click':
            return f"Click in {browser}"
        return f"Navigate in {browser}"
    
    elif 'finder' in app_name_lower:
        if action_type == 'click':
            return "Click in Finder"
        elif action_type == 'type':
            return f"Search in Finder: '{details}'"
        return "Navigate files in Finder"
    
    elif 'notes' in app_name_lower or 'textedit' in app_name_lower:
        editor = 'Notes' if 'notes' in app_name_lower else 'TextEdit'
        if action_type == 'type':
            return f"Type in {editor}: '{details}'"
        elif action_type == 'click':
            return f"Click in {editor}"
        return f"Edit text in {editor}"
    
    elif 'mail' in app_name_lower:
        if action_type == 'type':
            return f"Type in Mail: '{details}'"
        elif action_type == 'click':
            return "Click in Mail"
        return "Interact with Mail"
    
    elif 'spotify' in app_name_lower or 'music' in app_name_lower:
        app = 'Spotify' if 'spotify' in app_name_lower else 'Music'
        if action_type == 'click':
            return f"Control {app} playback"
        return f"Interact with {app}"
    
    elif 'terminal' in app_name_lower or 'iterm' in app_name_lower:
        terminal = 'Terminal' if 'terminal' in app_name_lower else 'iTerm'
        if action_type == 'type':
            return f"Run command in {terminal}: '{details}'"
        return f"Use {terminal}"
    
    elif 'slack' in app_name_lower or 'discord' in app_name_lower or 'teams' in app_name_lower:
        chat_app = app_name.split()[0] if app_name else "Chat"
        if action_type == 'type':
            return f"Send message in {chat_app}: '{details}'"
        elif action_type == 'click':
            return f"Click in {chat_app}"
        return f"Use {chat_app}"
    
    elif 'code' in app_name_lower or 'cursor' in app_name_lower or 'vscode' in app_name_lower:
        editor = 'Cursor' if 'cursor' in app_name_lower else ('VS Code' if 'vscode' in app_name_lower else 'Code')
        if action_type == 'type':
            return f"Code in {editor}: '{details}'"
        elif action_type == 'click':
            return f"Navigate in {editor}"
        return f"Use {editor}"
    
    # Generic fallback
    else:
        if action_type == 'click':
            return f"Click in {app_name}"
        elif action_type == 'type':
            return f"Type in {app_name}: '{details}'"
        elif action_type == 'hotkey':
            return f"Use keyboard shortcut in {app_name}"
        return f"Interact with {app_name}"

