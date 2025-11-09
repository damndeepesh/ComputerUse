import pyautogui
import time
from threading import Event


class SafetyManager:
    """Manages safety features during workflow execution"""
    
    def __init__(self):
        self.should_stop = Event()
        self.is_dry_run = False
        self.excluded_regions = []  # Regions to avoid (e.g., password fields)
        
        # Enable PyAutoGUI failsafe
        pyautogui.FAILSAFE = True
        
    def reset(self):
        """Reset safety manager for new execution"""
        self.should_stop.clear()
        
    def request_stop(self):
        """Request execution to stop"""
        self.should_stop.set()
        print("Safety: Stop requested")
        
    def check_should_stop(self):
        """Check if execution should stop"""
        return self.should_stop.is_set()
    
    def confirm_execution(self, workflow_name, num_steps):
        """
        Confirm with user before execution
        In a real implementation, this would show a dialog
        """
        print(f"\n{'='*50}")
        print(f"WORKFLOW EXECUTION CONFIRMATION")
        print(f"{'='*50}")
        print(f"Workflow: {workflow_name}")
        print(f"Steps: {num_steps}")
        print(f"WARNING: The AI will take control of your mouse and keyboard.")
        print(f"Press ESC or move mouse to screen corner to abort.")
        print(f"{'='*50}\n")
        
        # In production, you'd wait for user confirmation
        # For now, we'll just add a delay
        time.sleep(2)
        return True
    
    def set_dry_run(self, enabled):
        """Enable/disable dry run mode"""
        self.is_dry_run = enabled
        
    def add_excluded_region(self, x, y, width, height):
        """Add a region to avoid during automation"""
        self.excluded_regions.append({
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        })
    
    def is_position_safe(self, x, y):
        """Check if a position is safe to interact with"""
        for region in self.excluded_regions:
            if (region["x"] <= x <= region["x"] + region["width"] and
                region["y"] <= y <= region["y"] + region["height"]):
                print(f"Safety: Position ({x}, {y}) is in excluded region")
                return False
        return True
    
    def validate_step(self, step):
        """Validate a step before execution"""
        # Check for potentially dangerous operations
        if step.get("type") == "type":
            text = step.get("text", "")
            # Check for sensitive patterns (basic example)
            sensitive_keywords = ["password", "credit card", "ssn"]
            if any(kw in text.lower() for kw in sensitive_keywords):
                print(f"Safety: Blocked potentially sensitive input")
                return False
        
        # Check position safety for clicks
        if step.get("type") == "click":
            x, y = step.get("x"), step.get("y")
            if x is not None and y is not None:
                if not self.is_position_safe(x, y):
                    return False
        
        return True
    
    def pre_execution_check(self):
        """Perform pre-execution safety checks"""
        checks = []
        
        # Check screen size
        screen_width, screen_height = pyautogui.size()
        checks.append({
            "name": "Screen Resolution",
            "status": "OK",
            "details": f"{screen_width}x{screen_height}",
        })
        
        # Check failsafe
        checks.append({
            "name": "Failsafe",
            "status": "ENABLED" if pyautogui.FAILSAFE else "DISABLED",
            "details": "Move mouse to corner to abort",
        })
        
        return checks
    
    def log_execution(self, step, success, error=None):
        """Log execution details for debugging"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        status = "SUCCESS" if success else "FAILED"
        
        log_entry = f"[{timestamp}] {status}: {step.get('type', 'unknown')}"
        if not success and error:
            log_entry += f" - Error: {error}"
        
        print(log_entry)
        
        # In production, write to log file
        # with open("data/execution.log", "a") as f:
        #     f.write(log_entry + "\n")


# Global safety manager instance
safety_manager = SafetyManager()


def get_safety_manager():
    """Get the global safety manager instance"""
    return safety_manager


