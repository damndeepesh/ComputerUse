# AGI Assistant - Desktop Automation Platform

An AI-powered desktop assistant that learns from watching your screen, understands your workflows, and automates repetitive tasks locally on your machine.

## 🎯 Features

- 🎥 **Screen Recording**: Captures your desktop activity in real-time
- 🎤 **Audio Transcription**: Records and transcribes voice commands
- 🤖 **AI-Powered Analysis**: Uses local Phi-2 model to understand workflows (no Ollama required!)
- ⚡ **Automation**: Executes learned workflows with one click
- 🔒 **100% Local**: All processing happens on your machine
- 🎨 **Modern UI**: Beautiful Electron-based interface
- 🖱️ **Action Tracking**: Captures clicks, typing, hotkeys, scrolling with precise coordinates
- 🔍 **Visual Element Detection**: Click by text using OCR (works even when UI changes)
- ⏳ **Smart Wait Conditions**: Waits for text/elements to appear/disappear
- 🔄 **Error Handling & Retry**: Automatic retry logic with continue-on-error option

## 🚀 Quick Start

### Prerequisites

1. **Node.js** (v18 or higher) - [Download](https://nodejs.org/)
2. **Python** (3.9 or higher) - [Download](https://www.python.org/downloads/)
3. **macOS/Windows/Linux** with necessary permissions

### Installation

#### Option 1: Using Startup Script (Recommended)

```bash
# Make script executable (macOS/Linux)
chmod +x start.sh

# Run startup script
./start.sh
```

This script will:
- ✅ Check all prerequisites
- ✅ Set up virtual environment if needed
- ✅ Install dependencies if missing
- ✅ Clean up any existing processes
- ✅ Start backend server (port 8000)
- ✅ Start frontend (Vite + Electron)
- ✅ Open Electron app automatically

#### Option 2: Manual Setup

**1. Install Python Dependencies**

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

**Note for macOS users**: If `pyaudio` fails to install:
```bash
brew install portaudio
pip install pyaudio
```

**2. Download AI Models**

```bash
# Download Phi-2 model (~5GB) from Hugging Face
python download_models.py
```

This only needs to be done once. The model will be stored locally in `models/` directory.

**3. Install Node.js Dependencies**

```bash
npm install
```

**4. Start Backend Server**

```bash
source venv/bin/activate  # or venv\Scripts\activate on Windows
cd backend
python main.py
```

The backend will run on `http://localhost:8000`

**5. Start Frontend Application**

In a new terminal:

```bash
npm run dev
```

The Electron app will launch automatically.

### Stopping the Application

```bash
# Using stop script
./stop.sh

# Or manually
pkill -f "python.*main.py"
pkill -f "electron"
pkill -f "vite"
```

## 📖 Usage

### Recording a Workflow

1. Click **"Start Recording"** in the top-right corner
2. Perform your workflow normally:
   - Click on things
   - Type text
   - Speak commands (optional)
   - Navigate windows
3. Click **"Stop"** when finished
4. Wait 5-10 seconds for AI to analyze and create the workflow
5. Your workflow will appear in the left panel

### Executing a Workflow

1. Select a workflow from the left panel
2. Review the steps in the details panel
3. Click **"Execute Workflow"**
4. **IMPORTANT**: The AI will take control!
   - Move mouse to screen corner to abort
   - Or press ESC to stop
5. Watch as the AI automates your task

### Example Workflows

**Simple Text Editor:**
1. Start recording
2. Open TextEdit/Notepad
3. Type "Hello, AGI Assistant!"
4. Stop recording

**Browser Workflow:**
1. Start recording
2. Open browser
3. Type URL in address bar
4. Press Enter
5. Stop recording

## 🔧 Supported Actions

### Basic Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `click` | Click at coordinates | `x`, `y`, `button`, `clicks` |
| `click` (text) | Click by finding text | `find_by_text`, `button`, `timeout`, `retries` |
| `type` | Type text | `text`, `interval` |
| `hotkey` | Press key combination | `keys[]` |
| `scroll` | Scroll mouse | `amount`, `dy`, `x`, `y` |
| `wait` | Fixed delay | `duration` |
| `wait_for_text` | Wait for text to appear | `text`, `timeout`, `check_interval` |
| `wait_for_text_disappear` | Wait for text to disappear | `text`, `timeout`, `check_interval` |

### Advanced Features

**Visual Element Detection:**
```json
{
  "action": "click",
  "find_by_text": "Submit",
  "button": "left",
  "timeout": 5,
  "retries": 3
}
```

**Smart Wait Conditions:**
```json
{
  "action": "wait_for_text",
  "text": "Success",
  "timeout": 10,
  "check_interval": 0.5
}
```

**Error Handling:**
```json
{
  "action": "click",
  "x": 100,
  "y": 200,
  "max_retries": 3,
  "retry_delay": 1.0,
  "continue_on_error": false
}
```

## 🔐 Permissions Required

### macOS Permissions

Your system will prompt you to grant permissions. You need:

1. **Screen Recording**
   - System Settings → Security & Privacy → Privacy → Screen Recording
   - Enable for Terminal (or your IDE)

2. **Microphone Access**
   - System Settings → Security & Privacy → Privacy → Microphone
   - Enable for Terminal (or your IDE)

3. **Accessibility** (for automation)
   - System Settings → Security & Privacy → Privacy → Accessibility
   - Enable for Terminal (or your IDE)

4. **Input Monitoring** (for recording)
   - System Settings → Security & Privacy → Privacy → Input Monitoring
   - Enable for Terminal (or your IDE)

**Quick Settings Links:**
```bash
# Open Accessibility
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"

# Open Input Monitoring
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
```

### Windows Permissions

Windows may prompt you for permissions when you first run the app. Accept all prompts.

## 🏗️ Architecture

### Frontend
- **Electron + React**: Cross-platform desktop application
- **Tailwind CSS**: Modern, responsive UI
- **Real-time Updates**: Live recording preview and execution progress
- **nut-js**: Native automation library for mouse/keyboard control

### Backend
- **FastAPI**: High-performance Python API server
- **SQLite**: Local database for workflow storage
- **PyAutoGUI**: Cross-platform automation library
- **Phi-2**: Local LLM for workflow understanding (no Ollama!)
- **EasyOCR/PyTesseract**: OCR engine for text detection
- **pynput**: Mouse and keyboard event capture

### Project Structure

```
/Automato
├── backend/                    # Python FastAPI server
│   ├── main.py                # API endpoints
│   ├── capture/               # Screen & audio recording
│   │   ├── action_tracker.py  # Mouse/keyboard tracking
│   │   ├── screen_recorder.py # Screenshot capture
│   │   ├── audio_recorder.py  # Audio recording
│   │   └── app_tracker.py      # App/window tracking
│   ├── processing/            # Workflow analysis
│   │   ├── workflow_analyzer.py # AI-powered analysis
│   │   └── ocr_engine.py       # OCR text extraction
│   ├── automation/            # Execution engine
│   │   ├── executor.py        # Workflow execution
│   │   ├── element_finder.py  # Visual element detection
│   │   └── safety.py          # Safety features
│   └── models/                # Database models
├── src/                       # Electron + React app
│   ├── main.js                # Electron main process
│   ├── preload.js             # IPC bridge
│   └── renderer/              # React components
│       ├── App.jsx            # Main app component
│       └── components/       # UI components
├── data/                       # Local data storage
│   ├── screenshots/          # Captured images
│   ├── recordings/           # Audio recordings
│   └── workflows.db           # SQLite database
├── models/                     # AI models
│   └── models--microsoft--phi-2/ # Downloaded Phi-2 model
├── start.sh                    # Startup script
├── stop.sh                     # Stop script
└── requirements.txt           # Python dependencies
```

## 🛡️ Safety Features

- **Failsafe**: Move mouse to screen corner to abort execution
- **Confirmation**: Workflows require confirmation before execution
- **Emergency Stop**: ESC key or Stop button halts execution
- **Local Processing**: No data leaves your machine
- **Error Recovery**: Automatic retry with configurable attempts
- **Continue on Error**: Option to skip failed steps

## 📦 Packaging & Distribution

### Build for Production

```bash
# Build frontend
npm run build

# Package application
npm run package

# Or for specific platform:
npm run package:mac    # macOS
npm run package:win    # Windows
npm run package:linux  # Linux
```

Executables will be in the `release/` directory.

### What Users Need

Users need to install separately:
1. **Python 3.9+** from python.org
2. **Python packages**: `pip install -r requirements.txt`
3. **AI Models**: Run `python download_models.py`

## 🔍 Troubleshooting

### Backend Won't Start

**Error: "Address already in use"**
```bash
# Find and kill process on port 8000
lsof -ti:8000 | xargs kill -9  # macOS/Linux
netstat -ano | findstr :8000   # Windows
```

**Error: "No module named ..."**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend Won't Start

**Error: "Port 5173 is already in use"**
```bash
lsof -ti:5173 | xargs kill -9  # macOS/Linux
```

**Error: "Module not found"**
```bash
rm -rf node_modules package-lock.json
npm install
```

### Recording Issues

**Screen capture not working:**
- Grant screen recording permissions (see Permissions section)
- Restart the application after granting permissions

**Audio not capturing:**
- Grant microphone permissions
- Check system audio settings
- On macOS: `brew install portaudio` if pyaudio fails

**Actions not being tracked:**
- Grant accessibility permissions (macOS)
- Grant input monitoring permissions (macOS)
- Run as administrator (Windows)
- Check console for error messages

### Automation Issues

**Mouse/keyboard control not working:**
- Grant accessibility permissions
- Run with elevated privileges if needed
- Check PyAutoGUI installation: `pip install --upgrade pyautogui`

**Failsafe triggering unexpectedly:**
- Keep mouse away from screen corners during execution
- Adjust delays in executor.py for slower execution

**Text not being captured:**
- Check backend logs for character detection
- Ensure input monitoring permission is granted
- Verify action_tracker is running

**Mouse clicks not going to correct position:**
- Check execution logs for coordinate validation
- Verify screen resolution hasn't changed
- Check if coordinates are being parsed correctly

### Model Download Issues

If model download fails:
```bash
# Try downloading again
python download_models.py

# Check your internet connection
# Check available disk space (need ~5GB)
```

Test the model:
```bash
python backend/test_local_model.py
```

### Performance Issues

**Slow inference:**
- First run is slower as model loads into memory
- CPU: 5-10 seconds per generation (normal)
- GPU: 1-2 seconds per generation (if CUDA available)

**High memory usage:**
- Model loaded: ~3GB RAM
- During inference: ~4-5GB RAM
- Idle: ~500MB RAM

**Large screenshot files:**
- Edit `backend/capture/screen_recorder.py` to adjust quality/resolution
- Clean old screenshots: `rm -rf data/screenshots/*`

## 💡 Best Practices

1. **Keep workflows short**: 5-10 steps work best initially
2. **Use text-based clicks**: More robust than coordinates
3. **Use smart waits**: Wait for loading to finish, not fixed delays
4. **Set appropriate timeouts**: Don't wait too long or too short
5. **Use continue_on_error for optional steps**: Don't fail entire workflow
6. **Set retry counts**: 3 retries is usually enough for transient errors
7. **Test workflows**: Start with simple workflows before complex ones
8. **Save important work**: Always save before running automation

## 🎯 Example Workflow JSON

```json
{
  "name": "Complete Automation Example",
  "steps": [
    {
      "action": "click",
      "find_by_text": "Login",
      "description": "Click Login button",
      "max_retries": 3
    },
    {
      "action": "type",
      "text": "username@example.com"
    },
    {
      "action": "wait_for_text",
      "text": "Password",
      "timeout": 5,
      "description": "Wait for password field to appear"
    },
    {
      "action": "type",
      "text": "mypassword"
    },
    {
      "action": "click",
      "find_by_text": "Submit",
      "max_retries": 3,
      "description": "Click Submit button"
    },
    {
      "action": "wait_for_text_disappear",
      "text": "Loading...",
      "timeout": 10,
      "description": "Wait for loading to finish"
    },
    {
      "action": "wait_for_text",
      "text": "Success",
      "timeout": 5,
      "description": "Wait for success message",
      "continue_on_error": true
    }
  ]
}
```

## 📊 API Endpoints

### Find Text on Screen

```http
POST /api/automation/find-text
Content-Type: application/json

{
  "text": "Submit",
  "timeout": 5
}
```

**Response:**
```json
{
  "found": true,
  "center": [500, 300],
  "bbox": {
    "x": 450,
    "y": 280,
    "width": 100,
    "height": 40
  },
  "text": "Submit",
  "confidence": 0.95
}
```

### Other Endpoints

- `GET /api/workflows` - List all workflows
- `GET /api/workflows/{id}` - Get workflow details
- `POST /api/recording/start` - Start recording
- `POST /api/recording/stop` - Stop recording
- `POST /api/workflows/{id}/execute` - Execute workflow
- `DELETE /api/workflows/{id}` - Delete workflow

Visit `http://localhost:8000/docs` for complete API documentation.

## 🔬 Development

### Enable Debug Mode

Set environment variables:
```bash
export DEBUG=1
export LOG_LEVEL=DEBUG
```

### Watch Logs

**Backend logs:**
```bash
tail -f backend.log
```

**Frontend console:**
- Open DevTools in Electron app (View → Toggle Developer Tools)

### Hot Reload

Both frontend and backend support hot reload:
- Frontend: Automatically reloads on file changes
- Backend: Restart manually after changes

## 📝 Model Information

### Phi-2 Specifications

- **Size:** ~5GB download, ~2.7GB in memory
- **Parameters:** 2.7 billion
- **Speed:** Fast inference on CPU
- **Quality:** Excellent for workflow understanding
- **Provider:** Microsoft Research
- **License:** MIT

### System Requirements

**Minimum:**
- 8GB RAM
- 10GB free disk space
- Modern CPU (Intel Core i5 or equivalent)
- Internet for initial download

**Recommended:**
- 16GB RAM
- 20GB free disk space
- GPU with CUDA support (optional, for faster inference)
- Fast internet connection

### GPU Acceleration (Optional)

If you have an NVIDIA GPU:

```bash
# Install CUDA-enabled PyTorch
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

The model will automatically use GPU if available!

## 🎉 What Makes This Special

✅ **100% Local**: No cloud services, no data leaves your machine  
✅ **No Ollama Required**: Direct model loading from Hugging Face  
✅ **Robust Automation**: Visual element detection, smart waits, error handling  
✅ **Cross-Platform**: Works on macOS, Windows, and Linux  
✅ **Production Ready**: Complete error handling and retry logic  

## 📚 Additional Resources

- **API Documentation**: Visit `http://localhost:8000/docs` when backend is running
- **Logs**: Check `backend.log` and `frontend.log` for detailed information
- **Workflow Storage**: All workflows stored in `data/workflows.db` (SQLite)

## 🤝 Contributing

This is a hackathon project. Feel free to fork and improve!

## 📄 License

MIT License

## 🙏 Acknowledgments

- Built for "The AGI Assistant" Hackathon
- Uses Phi-2 by Microsoft Research
- Powered by Electron, React, FastAPI, and PyTorch
- OCR powered by EasyOCR and PyTesseract

---

**AGI Assistant** - Watch, Learn, Automate 🚀
