const { app, BrowserWindow, ipcMain, desktopCapturer, globalShortcut } = require('electron');
const path = require('path');
const { mouse, left, right, up, down, keyboard, Key, Button, screen } = require('@nut-tree-fork/nut-js');
const { exec, spawn } = require('child_process');
const axios = require('axios');
const fs = require('fs');

let mainWindow;
let executionLogs = [];
let isExecutionCancelled = false;
let backendProcess = null;

// Backend API configuration
const BACKEND_URL = 'http://localhost:8000';
const API_TIMEOUT = 30000; // 30 seconds

// Helper function to add execution log (moved before apiCall)
function addLog(message) {
  const timestamp = new Date().toISOString();
  const log = `[${timestamp}] ${message}`;
  executionLogs.push(log);
  console.log(log);
  
  // Send log to renderer if window exists
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('execution-log', log);
  }
  
  return log;
}

// Helper: Check if backend API is available
async function checkBackendHealth() {
  try {
    // Use the lightweight health endpoint for faster startup detection
    const response = await axios.get(`${BACKEND_URL}/health`, { 
      timeout: 3000, // 3 second timeout (reduced from 5s for faster checks)
      validateStatus: () => true, // Accept any status code (200, 404, 500, etc.)
      // Add headers to ensure request goes through
      headers: {
        'Accept': 'application/json',
      },
      // Don't throw on network errors - we'll handle them
      maxRedirects: 0,
    });
    // If we get any response with a status code, the backend is up and running
    if (response && response.status !== undefined) {
      return true;
    }
    return false;
  } catch (error) {
    // Check if it's a network error vs other error
    if (error.code === 'ECONNREFUSED' || error.code === 'ETIMEDOUT' || error.message?.includes('timeout')) {
      // Backend is not reachable
      return false;
    }
    // For other errors (like 404, 500, etc.), the backend IS running, just had an error
    // Check if we got a response object
    if (error.response && error.response.status !== undefined) {
      return true; // Backend responded, even if with an error status
    }
    // Unknown error - assume backend is not reachable
    return false;
  }
}

// Helper: Make API call with retry logic
async function apiCall(url, options = {}, maxRetries = 3) {
  const { timeout = API_TIMEOUT, ...axiosOptions } = options;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    if (isExecutionCancelled) throw new Error('Cancelled');
    
    try {
      const response = await axios({
        url,
        timeout,
        ...axiosOptions,
        validateStatus: () => true, // Don't throw on HTTP errors
      });
      
      if (response.status >= 200 && response.status < 300) {
        return response;
      } else if (response.status >= 500 && attempt < maxRetries) {
        // Server error, retry
        const delay = Math.min(1000 * Math.pow(2, attempt), 5000);
        addLog(`   ⚠️  API error ${response.status}, retrying in ${delay}ms...`);
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      } else {
        throw new Error(`API returned status ${response.status}`);
      }
    } catch (error) {
      if (isExecutionCancelled) throw new Error('Cancelled');
      
      if (attempt < maxRetries && (error.code === 'ECONNREFUSED' || error.code === 'ETIMEDOUT' || error.message.includes('timeout'))) {
        const delay = Math.min(1000 * Math.pow(2, attempt), 5000);
        addLog(`   ⚠️  API connection failed (${error.message}), retrying in ${delay}ms...`);
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }
      
      throw error;
    }
  }
  
  throw new Error('API call failed after all retries');
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 650,
    minWidth: 800,
    minHeight: 500,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // Load the app
  if (process.env.NODE_ENV === 'development' || !app.isPackaged) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
    // Enable devtools for debugging backend startup issues
    // TODO: Remove or make conditional in production
    mainWindow.webContents.openDevTools();
  }
  
  // Log all console output to help debug
  mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
    console.log(`[Renderer ${level}] ${message}`);
  });
}

// Check if Python is available
async function checkPythonAvailable(pythonPath = 'python3') {
  return new Promise((resolve) => {
    exec(`${pythonPath} --version`, (error) => {
      resolve(!error);
    });
  });
}

// Find Python executable
async function findPython() {
  const candidates = ['python3', 'python'];
  for (const candidate of candidates) {
    if (await checkPythonAvailable(candidate)) {
      return candidate;
    }
  }
  return null;
}

// Check if Python dependencies are installed (using venv if available)
async function checkPythonDependencies(pythonPath) {
  return new Promise((resolve) => {
    // Use a timeout to avoid hanging
    const timeout = setTimeout(() => {
      console.log('   ⏱️  Dependency check timed out (assuming not installed)');
      resolve(false);
    }, 10000);
    
    // Try venv Python first if it exists
    const venvPath = getVenvPath();
    const venvPython = getVenvPython(venvPath);
    const pythonToCheck = fs.existsSync(venvPython) ? venvPython : pythonPath;
    
    if (fs.existsSync(venvPython)) {
      console.log(`   Checking dependencies in virtual environment...`);
    }
    
    // Test import with the Python that will run the backend
    const checkCmd = `${pythonToCheck} -u -c "import fastapi, uvicorn, sqlalchemy, pydantic, sqlalchemy.orm; print('OK')"`;
    
    exec(checkCmd, { timeout: 8000 }, (error, stdout, stderr) => {
      clearTimeout(timeout);
      if (error) {
        console.log(`   ❌ Dependencies check failed: ${error.message}`);
        if (stderr) {
          console.log(`   Error output: ${stderr.trim()}`);
        }
        resolve(false);
      } else {
        console.log(`   ✅ Dependencies are installed`);
        resolve(true);
      }
    });
  });
}

// Create or get virtual environment path
function getVenvPath() {
  // In packaged app, check for bundled venv first
  if (app.isPackaged) {
    const bundledVenvPath = path.join(process.resourcesPath || app.getAppPath(), 'venv');
    if (fs.existsSync(bundledVenvPath)) {
      const venvPython = getVenvPython(bundledVenvPath);
      if (fs.existsSync(venvPython)) {
        console.log(`📦 Using bundled virtual environment: ${bundledVenvPath}`);
        return bundledVenvPath;
      }
    }
  }
  
  // Fallback to userData venv (for development or if bundled venv not found)
  const userDataDir = app.getPath('userData');
  return path.join(userDataDir, 'venv');
}

// Get Python executable from virtual environment
function getVenvPython(venvPath) {
  if (process.platform === 'win32') {
    return path.join(venvPath, 'Scripts', 'python.exe');
  } else {
    return path.join(venvPath, 'bin', 'python');
  }
}

// Install Python dependencies using a virtual environment
async function installPythonDependencies(pythonPath, requirementsPath) {
  return new Promise((resolve, reject) => {
    console.log('📦 Installing Python dependencies...');

    // Build environment with common macOS paths to find Homebrew
    const env = { ...process.env };
    const extraPaths = ['/opt/homebrew/bin', '/usr/local/bin'];
    const pathSep = process.platform === 'win32' ? ';' : ':';
    env.PATH = `${extraPaths.join(pathSep)}${pathSep}${env.PATH || ''}`;

    // Helper to run a command and stream logs with timeout
    const run = (cmd, args, timeoutMs = 300000, customEnv = null) =>
      new Promise((res, rej) => {
        const p = spawn(cmd, args, { 
          stdio: ['ignore', 'pipe', 'pipe'], 
          env: customEnv || env
        });
        
        let stdout = '';
        let stderr = '';
        let timeoutId = null;
        
        // Set timeout
        if (timeoutMs > 0) {
          timeoutId = setTimeout(() => {
            p.kill('SIGTERM');
            rej(new Error(`Command timed out after ${timeoutMs}ms`));
          }, timeoutMs);
        }
        
        p.stdout.on('data', d => {
          const text = d.toString();
          stdout += text;
          console.log(`[pip] ${text.trim()}`);
        });
        
        p.stderr.on('data', d => {
          const text = d.toString();
          stderr += text;
          // Some packages output to stderr even on success (like pip)
          if (!text.includes('WARNING') && !text.includes('DEPRECATION')) {
            console.error(`[pip error] ${text.trim()}`);
          }
        });
        
        p.on('close', code => {
          if (timeoutId) clearTimeout(timeoutId);
          if (code === 0) {
            res({ code, stdout, stderr });
          } else {
            rej(new Error(`${cmd} ${args.join(' ')} exited with code ${code}\n${stderr}`));
          }
        });
        
        p.on('error', err => {
          if (timeoutId) clearTimeout(timeoutId);
          rej(new Error(`Failed to spawn ${cmd}: ${err.message}`));
        });
      });

    (async () => {
      try {
        const venvPath = getVenvPath();
        const venvPython = getVenvPython(venvPath);
        const venvBinDir = path.dirname(venvPython);
        const venvExists = fs.existsSync(venvPython);
        
        console.log(`   Using Python: ${pythonPath}`);
        console.log(`   Requirements file: ${requirementsPath}`);
        console.log(`   Virtual environment: ${venvPath}`);
        console.log(`   Venv exists: ${venvExists}`);
        
        // Create virtual environment if it doesn't exist
        if (!venvExists) {
          console.log('   Creating virtual environment...');
          console.log('   ⏳ This may take a minute...');
          try {
            await run(pythonPath, ['-m', 'venv', venvPath], 120000); // 2 min timeout
            console.log('   ✅ Virtual environment created');
            
            // Ensure 'python' symlink exists in venv (some systems only have python3)
            const venvPythonLink = path.join(venvBinDir, 'python');
            if (!fs.existsSync(venvPythonLink) && fs.existsSync(venvPython)) {
              try {
                // Create symlink: python -> python3 (or the actual python executable)
                const pythonName = path.basename(venvPython);
                if (pythonName !== 'python') {
                  fs.symlinkSync(pythonName, venvPythonLink);
                  console.log(`   ✅ Created python symlink -> ${pythonName}`);
                }
              } catch (e) {
                console.log(`   ⚠️  Could not create python symlink: ${e.message}`);
              }
            }
          } catch (e) {
            console.error(`   ❌ Failed to create virtual environment: ${e.message}`);
            reject(new Error(`Failed to create virtual environment: ${e.message}`));
            return;
          }
        } else {
          console.log('   ✅ Virtual environment already exists');
        }
        
        // Verify venv Python exists
        if (!fs.existsSync(venvPython)) {
          reject(new Error(`Virtual environment Python not found at: ${venvPython}`));
          return;
        }
        
        // Build environment with venv's bin directory in PATH
        const venvEnv = { ...env };
        const pathSep = process.platform === 'win32' ? ';' : ':';
        venvEnv.PATH = `${venvBinDir}${pathSep}${venvEnv.PATH || ''}`;
        venvEnv.PYTHON = venvPython; // Some build tools look for PYTHON env var
        
        // Show Python and pip versions
        try { 
          const pyVersion = await run(venvPython, ['--version'], 30000, venvEnv);
          console.log(`   ${pyVersion.stdout.trim()}`);
        } catch (e) {
          console.error(`   ⚠️  Could not get Python version: ${e.message}`);
        }
        
        try { 
          const pipVersion = await run(venvPython, ['-m', 'pip', '--version'], 30000, venvEnv);
          console.log(`   ${pipVersion.stdout.trim()}`);
        } catch (e) {
          console.log(`   ⚠️  pip not found in venv, will install it...`);
        }

        // Upgrade pip/setuptools/wheel in venv
        console.log('   Upgrading pip, setuptools, and wheel in virtual environment...');
        try { 
          await run(venvPython, ['-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel'], 120000, venvEnv); // 2 min timeout
          console.log('   ✅ pip upgraded');
        } catch (e) {
          console.log(`   ⚠️  pip upgrade failed, continuing anyway: ${e.message}`);
        }

        // Install dependencies in virtual environment
        // Use --prefer-binary to avoid building from source when possible
        console.log('   Installing dependencies from requirements.txt...');
        console.log('   ⏳ This may take 2-5 minutes on first launch. Please wait...');
        console.log(`   Using: ${venvPython} -m pip install --prefer-binary -r ${requirementsPath}`);
        
        try {
          await run(venvPython, ['-m', 'pip', 'install', '--prefer-binary', '-r', requirementsPath], 600000, venvEnv); // 10 minute timeout
          console.log('✅ Python dependencies installed successfully in virtual environment');
          resolve(true);
          return;
        } catch (e1) {
          console.error(`❌ Installation with --prefer-binary failed: ${e1.message}`);
          console.log('   Trying without --prefer-binary (may take longer)...');
          
          // Fallback: try without --prefer-binary
          try {
            await run(venvPython, ['-m', 'pip', 'install', '-r', requirementsPath], 600000, venvEnv);
            console.log('✅ Python dependencies installed successfully in virtual environment');
            resolve(true);
            return;
          } catch (e2) {
            console.error(`❌ Installation failed: ${e2.message}`);
            reject(new Error(`Failed to install dependencies in virtual environment: ${e2.message}`));
          }
        }
      } catch (err) {
        console.error('❌ Failed to install dependencies:', err.message);
        reject(err);
      }
    })();
  });
}

// Start backend server automatically
async function startBackendServer() {
  // Check if backend is already running
  const isRunning = await checkBackendHealth();
  if (isRunning) {
    console.log('✅ Backend server is already running');
    return { success: true };
  }

  console.log('🚀 Starting backend server...');
  
  // Determine paths based on whether app is packaged
  let projectRoot;
  let pythonPath;
  let backendPath;
  let requirementsPath;
  
  if (app.isPackaged) {
    // In packaged app, backend should be in Resources
    // macOS: app.asar -> resources -> backend
    projectRoot = process.resourcesPath || app.getAppPath();
    console.log('📦 Packaged app detected');
    console.log('   Resources path:', process.resourcesPath);
    console.log('   App path:', app.getAppPath());
    console.log('   Project root:', projectRoot);
    
    backendPath = path.join(projectRoot, 'backend', 'main.py');
    requirementsPath = path.join(projectRoot, 'backend', 'requirements.txt');
    
    console.log('   Backend path:', backendPath);
    console.log('   Backend exists:', fs.existsSync(backendPath));
    
    // Fallback: try to find backend relative to app bundle
    if (!fs.existsSync(backendPath)) {
      console.log('   ⚠️  Backend not found in resources, trying fallback paths...');
      // Try different possible locations
      const fallbackPaths = [
        path.join(app.getAppPath(), '..', '..', '..', 'backend', 'main.py'),
        path.join(app.getAppPath(), '..', 'Resources', 'backend', 'main.py'),
        path.join(process.resourcesPath, 'backend', 'main.py'),
      ];
      
      for (const fallback of fallbackPaths) {
        console.log(`   Trying: ${fallback}`);
        if (fs.existsSync(fallback)) {
          backendPath = fallback;
          requirementsPath = path.join(path.dirname(fallback), 'requirements.txt');
          console.log(`   ✅ Found backend at: ${backendPath}`);
          break;
        }
      }
    }
    
    // Find Python - try system Python first
    pythonPath = await findPython();
    if (!pythonPath) {
      const error = 'Python 3 is not installed. Please install Python from python.org';
      console.error(`❌ ${error}`);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('backend-error', {
          message: 'Python Not Found',
          details: error,
          suggestion: 'Please install Python 3.9+ from https://www.python.org/downloads/\n\nAfter installing, restart the app.',
          requiresPython: true
        });
      }
      return { success: false, error, requiresPython: true };
    }
    
    console.log(`✅ Found Python: ${pythonPath}`);
    
    // Check for bundled venv first
    const bundledVenvPath = path.join(process.resourcesPath || app.getAppPath(), 'venv');
    const bundledVenvPython = getVenvPython(bundledVenvPath);
    const hasBundledVenv = app.isPackaged && fs.existsSync(bundledVenvPath) && fs.existsSync(bundledVenvPython);
    
    let depsInstalled = false;
    
    // If we have a bundled venv, skip all dependency checks and installation
    // Assume it's ready to use since it was bundled with the app
    if (hasBundledVenv) {
      console.log('📦 Bundled virtual environment detected');
      console.log('✅ Using bundled venv directly - skipping dependency checks and installation');
      depsInstalled = true; // Mark as installed so we skip the installation process
    } else {
      // No bundled venv - check userData venv or system Python
      console.log('🔍 Checking Python dependencies...');
      console.log(`   Using Python: ${pythonPath}`);
      
      // Check if we have a marker file indicating dependencies were installed
      const userDataDir = app.getPath('userData');
      const depsMarkerFile = path.join(userDataDir, '.deps_installed');
      const depsMarkerExists = fs.existsSync(depsMarkerFile);
      
      if (depsMarkerExists) {
        // Check if dependencies are actually installed (marker might be outdated)
        depsInstalled = await checkPythonDependencies(pythonPath);
        console.log(`   Dependencies installed: ${depsInstalled}`);
        if (!depsInstalled) {
          console.log('   ⚠️  Marker file exists but dependencies not found - will reinstall');
          // Remove marker so we reinstall
          try {
            fs.unlinkSync(depsMarkerFile);
          } catch (e) {}
        }
      } else {
        console.log('   First launch detected - will install dependencies');
        depsInstalled = false;
      }
    }
    
    if (!depsInstalled) {
      console.log('📦 Python dependencies not found, installing automatically...');
      
      // Send status to UI if available
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('backend-status', {
          message: 'Installing Python dependencies...',
          status: 'installing'
        });
      }
      
      // Check if requirements.txt exists
      if (!fs.existsSync(requirementsPath)) {
        const errorMsg = `requirements.txt not found at: ${requirementsPath}`;
        console.error(`❌ ${errorMsg}`);
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('backend-error', {
            message: 'requirements.txt Not Found',
            details: errorMsg,
            suggestion: 'The app bundle appears to be incomplete. Please reinstall the app.',
            requiresPython: false
          });
        }
        return { success: false, error: errorMsg };
      }
      
      // Use system Python for installation (bundled venv should already have deps)
      const pythonToUseForInstall = pythonPath;
      
      try {
        console.log(`   Installing from: ${requirementsPath}`);
        console.log(`   Using Python: ${pythonToUseForInstall}`);
        await installPythonDependencies(pythonToUseForInstall, requirementsPath);
        
        // Wait a moment for installation to complete
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Re-check dependencies after installation
        console.log('🔍 Verifying installation...');
        depsInstalled = await checkPythonDependencies(pythonToUseForInstall);
        
        if (!depsInstalled) {
          // Try one more time after a longer wait
          console.log('   ⏳ Waiting a bit longer for packages to be available...');
          await new Promise(resolve => setTimeout(resolve, 5000));
          depsInstalled = await checkPythonDependencies(pythonToUseForInstall);
        }
        
        if (depsInstalled) {
          console.log('✅ Python dependencies installed and verified!');
          
          // Create marker file to indicate dependencies are installed
          try {
            const userDataDir = app.getPath('userData');
            const depsMarkerFile = path.join(userDataDir, '.deps_installed');
            fs.writeFileSync(depsMarkerFile, JSON.stringify({
              installed: true,
              timestamp: new Date().toISOString(),
              pythonPath: pythonPath
            }));
            console.log('   ✅ Created dependency marker file');
          } catch (e) {
            console.log(`   ⚠️  Could not create marker file: ${e.message}`);
          }
          
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('backend-status', {
              message: 'Dependencies installed successfully!',
              status: 'ready'
            });
          }
        } else {
          throw new Error('Dependencies installed but verification failed. Please restart the app.');
        }
      } catch (error) {
        const errorMsg = `Failed to install dependencies: ${error.message}`;
        console.error(`❌ ${errorMsg}`);
        console.error('   This may take a few minutes on first launch.');
        console.error('   Please wait and try again, or restart the app.');
        
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('backend-error', {
            message: 'Dependency Installation Failed',
            details: errorMsg,
            suggestion: 'The installation may still be in progress. Please wait a moment and restart the app.\n\nIf issues persist, try running in Terminal:\npip3 install --user -r "' + requirementsPath + '"',
            requiresPython: false
          });
        }
        return { success: false, error: errorMsg };
      }
    } else {
      if (hasBundledVenv) {
        console.log('✅ Using bundled virtual environment - ready to start backend');
      } else {
        console.log('✅ Python dependencies are already installed');
      }
    }
  } else {
    // Development mode
    projectRoot = path.join(__dirname, '..');
    // Try to use venv Python first
    const venvPython = path.join(projectRoot, 'venv', 'bin', 'python');
    if (fs.existsSync(venvPython)) {
      pythonPath = venvPython;
    } else {
      pythonPath = await findPython();
      if (!pythonPath) {
        const error = 'Python 3 is not installed. Please install Python from python.org';
        console.error(`❌ ${error}`);
        return { success: false, error, requiresPython: true };
      }
    }
    backendPath = path.join(projectRoot, 'backend', 'main.py');
    requirementsPath = path.join(projectRoot, 'requirements.txt');
  }

  // Check if backend file exists
  if (!fs.existsSync(backendPath)) {
    const error = `Backend file not found at: ${backendPath}`;
    console.error(`❌ ${error}`);
    console.error('   The backend server needs to be accessible for recording to work.');
    console.error('   Please ensure the backend is running or include it in the app bundle.');
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend-error', {
        message: 'Backend Not Found',
        details: error,
        suggestion: 'The app bundle appears to be incomplete. Please reinstall the app.',
        requiresPython: false
      });
    }
    return { success: false, error };
  }

  // Change to backend directory and start server
  const backendDir = path.dirname(backendPath);
  
  // Use venv Python if available, otherwise use system Python
  const venvPath = getVenvPath();
  const venvPython = getVenvPython(venvPath);
  const pythonToUse = fs.existsSync(venvPython) ? venvPython : pythonPath;
  
  console.log(`📂 Starting backend from: ${backendDir}`);
  console.log(`🐍 Using Python: ${pythonToUse}`);
  if (fs.existsSync(venvPython)) {
    console.log(`   (Using virtual environment: ${venvPath})`);
  }
  
  // Set environment variables for backend
  const env = { ...process.env };
  env.PYTHONPATH = backendDir;
  if (process.env.PYTHONPATH) {
    env.PYTHONPATH = process.platform === 'win32' 
      ? `${backendDir};${process.env.PYTHONPATH}`
      : `${backendDir}:${process.env.PYTHONPATH}`;
  }
  // Mark as packaged app so backend uses proper data directory
  if (app.isPackaged) {
    env.APP_PACKAGED = '1';
  }
  
  // Start backend server
  console.log('🚀 Spawning backend process...');
  console.log(`   Command: ${pythonToUse} main.py`);
  console.log(`   Working directory: ${backendDir}`);
  console.log(`   Environment: APP_PACKAGED=${env.APP_PACKAGED}, PYTHONPATH=${env.PYTHONPATH}`);
  
  try {
    backendProcess = spawn(pythonToUse, ['main.py'], {
      cwd: backendDir,
      detached: false,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: env
    });
    
    console.log(`✅ Backend process spawned (PID: ${backendProcess.pid})`);
  } catch (spawnError) {
    const errorMsg = `Failed to spawn backend process: ${spawnError.message}`;
    console.error(`❌ ${errorMsg}`);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend-error', {
        message: 'Failed to Start Backend',
        details: errorMsg,
        suggestion: 'Please check that Python is installed and accessible.',
        requiresPython: true
      });
    }
    return { success: false, error: errorMsg };
  }

  // Store backend output for debugging
  let backendOutput = '';
  let backendErrors = '';

  // Log backend output
  backendProcess.stdout.on('data', (data) => {
    const output = data.toString().trim();
    console.log(`[Backend] ${output}`);
    backendOutput += output + '\n';
    // Send to renderer if window exists
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend-log', output);
    }
  });

  backendProcess.stderr.on('data', (data) => {
    const error = data.toString().trim();
    console.error(`[Backend Error] ${error}`);
    backendErrors += error + '\n';
    // Send to renderer if window exists
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend-error-log', error);
    }
  });

  backendProcess.on('error', (error) => {
    const errorMsg = `Failed to start backend server: ${error.message}`;
    console.error(`❌ ${errorMsg}`);
    console.error('   Python path:', pythonPath);
    console.error('   Backend dir:', backendDir);
    console.error('   Backend path exists:', fs.existsSync(backendPath));
    
    // Send error to renderer
    const errorData = {
      message: 'Failed to start backend server',
      details: error.message,
      suggestion: 'Make sure Python 3 is installed and accessible.\n\nTo install Python: https://www.python.org/downloads/',
      requiresPython: true,
      debugInfo: {
        pythonPath,
        backendDir,
        backendPath,
        backendPathExists: fs.existsSync(backendPath)
      }
    };
    
    // Send immediately if window exists, otherwise store for later
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend-error', errorData);
    } else {
      // Store error to send when window is created
      app.backendStartupError = errorData;
    }
  });

  backendProcess.on('exit', (code, signal) => {
    const exitMsg = `Backend server exited with code ${code}${signal ? ` (signal: ${signal})` : ''}`;
    console.log(`⚠️  ${exitMsg}`);
    
    if (code !== 0 && code !== null) {
      console.error('Backend output:', backendOutput);
      console.error('Backend errors:', backendErrors);
      
      const errorData = {
        message: 'Backend server crashed',
        details: exitMsg,
        suggestion: 'Check the console for errors. Common issues:\n- Python dependencies not installed\n- Port 8000 already in use\n- Missing Python modules',
        requiresPython: false,
        debugInfo: {
          exitCode: code,
          signal: signal,
          output: backendOutput,
          errors: backendErrors
        }
      };
      
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('backend-error', errorData);
      } else {
        app.backendStartupError = errorData;
      }
    }
    
    backendProcess = null;
  });

  // Wait for backend to be ready
  console.log('⏳ Waiting for backend to start...');
  console.log('   Checking http://localhost:8000/health every second...');
  
  // Give backend a moment to start
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  let lastError = null;
  let checkCount = 0;
  const MAX_CHECKS = 300; // 5 minutes max, but we'll exit early if backend is ready
  
  // Keep checking until backend is ready or process dies
  while (checkCount < MAX_CHECKS) {
    // Check if process is still running
    if (!backendProcess || backendProcess.killed) {
      const error = 'Backend process died or was killed';
      console.error(`❌ ${error}`);
      console.error('   Last output:', backendOutput);
      console.error('   Last errors:', backendErrors);
      
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('backend-error', {
          message: 'Backend Process Died',
          details: error,
          suggestion: `The backend process exited unexpectedly.\n\nOutput: ${backendOutput}\n\nErrors: ${backendErrors}\n\nPlease check that all Python dependencies are installed.`,
          requiresPython: false,
          debugInfo: {
            output: backendOutput,
            errors: backendErrors
          }
        });
      }
      return { success: false, error };
    }
    
    // Check if backend is responding
    const isRunning = await checkBackendHealth();
    if (isRunning) {
      console.log(`✅ Backend server is ready! (checked ${checkCount} times)`);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('backend-status', {
          message: 'Backend is ready!',
          status: 'ready'
        });
      }
      return { success: true };
    }
    
    // Also try direct health endpoint check
    try {
      const testResponse = await axios.get(`${BACKEND_URL}/health`, { 
        timeout: 2000,
        validateStatus: () => true 
      });
      if (testResponse && testResponse.status !== undefined) {
        console.log(`✅ Backend IS responding (status: ${testResponse.status}) - ready!`);
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('backend-status', {
            message: 'Backend is ready!',
            status: 'ready'
          });
        }
        return { success: true };
      }
    } catch (testError) {
      // Check if error has a response (means backend is running)
      if (testError.response && testError.response.status !== undefined) {
        console.log(`✅ Backend IS responding (error status: ${testError.response.status}) - ready!`);
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('backend-status', {
            message: 'Backend is ready!',
            status: 'ready'
          });
        }
        return { success: true };
      }
    }
    
    // Log progress every 10 seconds
    if (checkCount % 10 === 0 && checkCount > 0) {
      console.log(`⏳ Still waiting for backend... ${checkCount}s elapsed`);
      if (backendErrors && backendErrors.length > 0) {
        console.log(`   Recent errors: ${backendErrors.slice(-200)}`);
      }
    }
    
    checkCount++;
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  
  // Only report error if we've exhausted all checks AND process is still running but not responding
  // This should rarely happen now that backend starts quickly
  if (backendProcess && !backendProcess.killed) {
    console.error(`⚠️  Backend process is running but not responding after ${checkCount} seconds`);
    console.error('   Backend output:', backendOutput);
    console.error('   Backend errors:', backendErrors);
    
    // Don't show error to user - backend might still be initializing
    // Just log it and continue - the app will work once backend is ready
    console.log('   Continuing anyway - backend may still be initializing...');
    return { success: false, error: 'Backend not responding but process is running' };
  }
  
  return { success: false, error: 'Backend process died' };
}

app.whenReady().then(async () => {
  // Create window first so we can show errors
  createWindow();
  
  // Send any startup errors to the window
  if (app.backendStartupError && mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.once('did-finish-load', () => {
      mainWindow.webContents.send('backend-error', app.backendStartupError);
    });
  }
  
  // Log startup info
  console.log('═══════════════════════════════════════');
  console.log('🚀 Starting AGI Assistant...');
  console.log('═══════════════════════════════════════');
  console.log(`Platform: ${process.platform}`);
  console.log(`Packaged: ${app.isPackaged}`);
  console.log(`App path: ${app.getAppPath()}`);
  console.log(`Resources path: ${process.resourcesPath}`);
  console.log('═══════════════════════════════════════');
  
  // Start backend server after window is created
  const result = await startBackendServer();
  
  if (!result.success) {
    console.error('═══════════════════════════════════════');
    console.error('❌ Backend startup failed!');
    console.error('═══════════════════════════════════════');
    console.error('Error:', result.error);
    if (result.requiresPython) {
      console.error('');
      console.error('🔧 SOLUTION: Install Python 3.9+ from https://www.python.org/downloads/');
      console.error('   Then restart the app.');
    }
    console.error('═══════════════════════════════════════');
  } else {
    console.log('═══════════════════════════════════════');
    console.log('✅ Backend started successfully!');
    console.log('═══════════════════════════════════════');
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC handler to check backend status
ipcMain.handle('check-backend-status', async () => {
  const isRunning = await checkBackendHealth();
  return {
    isRunning,
    processRunning: backendProcess !== null
  };
});

// Cleanup backend process on app quit
app.on('before-quit', () => {
  if (backendProcess) {
    console.log('🛑 Stopping backend server...');
    backendProcess.kill();
    backendProcess = null;
  }
});

// Open macOS System Settings → Privacy panes (Accessibility / Input Monitoring / Screen Recording)
ipcMain.handle('open-privacy-pane', async (event, pane) => {
  if (process.platform !== 'darwin') return { success: false, error: 'Only supported on macOS' };

  // Known System Settings deep links
  const map = {
    accessibility: 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility',
    inputMonitoring: 'x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent',
    screenRecording: 'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture',
    automation: 'x-apple.systempreferences:com.apple.preference.security?Privacy_Automation',
    privacyRoot: 'x-apple.systempreferences:com.apple.preference.security'
  };

  const url = map[pane] || map.privacyRoot;

  return new Promise((resolve) => {
    exec(`open "${url}"`, (err) => {
      if (err) {
        // Fallback: open base Privacy settings
        exec(`open "${map.privacyRoot}"`, () => resolve({ success: !err }));
      } else {
        resolve({ success: true });
      }
    });
  });
});

// Quick self-test to verify we can control mouse/keyboard (Accessibility permission)
ipcMain.handle('automation-self-test', async () => {
  try {
    // Mouse move test (small nudge and back)
    let pos, pos2;
    try {
      pos = await mouse.getPosition();
      console.log(`🧪 Test: Current position (${pos.x}, ${pos.y})`);
      
      await mouse.setPosition({ x: pos.x + 1, y: pos.y });
      console.log(`🧪 Test: Moved mouse`);
      
      await new Promise(r => setTimeout(r, 50));
      pos2 = await mouse.getPosition();
      console.log(`🧪 Test: New position (${pos2.x}, ${pos2.y})`);
      
      // Move back
      await mouse.setPosition({ x: pos.x, y: pos.y });
    } catch (e) {
      return { 
        success: false, 
        error: `Mouse control failed: ${e?.message || String(e)}`,
        details: 'Check System Settings > Privacy & Security > Accessibility'
      };
    }
    
    const mouseOk = Math.abs(pos2.x - pos.x) >= 1;
    
    if (!mouseOk) {
      return { 
        success: false, 
        error: 'Mouse position did not change',
        details: 'Check System Settings > Privacy & Security > Accessibility'
      };
    }

    // Keyboard test (press and release a non-destructive key)
    try {
      await keyboard.pressKey(Key.Left);
      await new Promise(r => setTimeout(r, 20));
      await keyboard.releaseKey(Key.Left);
    } catch (e) {
      // Keyboard might fail even if mouse works, but log it
      console.warn('Keyboard test failed:', e?.message);
    }

    return { success: true };
  } catch (e) {
    return { 
      success: false, 
      error: e?.message || String(e),
      details: 'Check System Settings > Privacy & Security > Accessibility'
    };
  }
});

// IPC handlers for screen capture
ipcMain.handle('get-sources', async () => {
  try {
    const sources = await desktopCapturer.getSources({
      types: ['screen', 'window'],
      thumbnailSize: { width: 1920, height: 1080 },
    });
    return sources.map(source => ({
      id: source.id,
      name: source.name,
      thumbnail: source.thumbnail.toDataURL(),
    }));
  } catch (error) {
    console.error('Error getting sources:', error);
    return [];
  }
});

// IPC handler for starting recording
ipcMain.handle('start-recording', async (event, sourceId) => {
  return { success: true, sourceId };
});

// IPC handler for stopping recording
ipcMain.handle('stop-recording', async () => {
  return { success: true };
});

// IPC handler for executing workflow with nut.js
ipcMain.handle('execute-workflow-nutjs', async (event, steps) => {
  executionLogs = []; // Clear previous logs
  isExecutionCancelled = false;
  
  // Save window state and minimize window at start
  let wasMinimized = false;
  let wasVisible = true;
  let windowWasMinimized = false; // Track if we actually minimized it
  
  try {
    if (mainWindow && !mainWindow.isDestroyed()) {
      wasMinimized = mainWindow.isMinimized();
      wasVisible = mainWindow.isVisible();
      if (!wasMinimized) {
        addLog('📱 Minimizing app window...');
        mainWindow.minimize();
        windowWasMinimized = true; // Mark that we minimized it
        // Small delay to ensure minimize completes
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }
  } catch (error) {
    addLog(`⚠️  Failed to minimize window: ${error.message}`);
  }
  
  // Register global ESC cancel while executing
  try {
    try {
      globalShortcut.register('Escape', () => {
        if (!isExecutionCancelled) {
          isExecutionCancelled = true;
          addLog('🛑 Cancel requested (Global ESC)');
        }
      });
    } catch (e) {
      addLog('⚠️  Failed to register global Escape shortcut');
    }

    // Validate steps
    if (!steps || !Array.isArray(steps) || steps.length === 0) {
      addLog(`❌ Invalid steps: ${JSON.stringify(steps)}`);
      return { success: false, error: 'No steps provided or steps is not an array', logs: executionLogs };
    }
    
    addLog(`🚀 Starting workflow execution with ${steps.length} steps`);
    addLog(`📋 Steps array validation: ${steps.length} steps received`);
    
    // Validate each step structure
    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      if (!step || typeof step !== 'object') {
        addLog(`⚠️  Warning: Step ${i + 1} is not a valid object: ${JSON.stringify(step)}`);
      } else {
        const action = (step.action || 'unknown').toLowerCase();
        addLog(`   Step ${i + 1}: ${action} (${step.description || 'no description'})`);
      }
    }
    
    // Log action type breakdown
    const actionTypes = {};
    steps.forEach(step => {
      const action = (step?.action || 'unknown').toLowerCase();
      actionTypes[action] = (actionTypes[action] || 0) + 1;
    });
    addLog(`📊 Action breakdown: ${JSON.stringify(actionTypes)}`);
    addLog(`\n🔵 Beginning step-by-step execution...\n`);
    
    let lastFocusedApp = null;
    addLog(`📋 Processing ${steps.length} total steps`);
    
    for (let i = 0; i < steps.length; i++) {
      // Log loop iteration
      addLog(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
      addLog(`🔄 LOOP ITERATION: ${i + 1}/${steps.length}`);
      addLog(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
      
      if (isExecutionCancelled) {
        addLog('⛔ Execution cancelled by user');
        return { success: false, error: 'Cancelled', logs: executionLogs };
      }
      
      addLog(`\n🔄 Starting step ${i + 1}/${steps.length}...`);
      
      const step = steps[i];
      
      // Log step object
      addLog(`   📦 Step object type: ${typeof step}, isArray: ${Array.isArray(step)}`);
      addLog(`   📦 Step keys: ${step ? Object.keys(step).join(', ') : 'null/undefined'}`);
      
      // Focus app if step has app_name and it changes (skip our own Electron app)
      try {
        const targetAppName = step.app_name;
        if (targetAppName && targetAppName !== 'Electron' && targetAppName !== lastFocusedApp) {
          addLog(`   📱 Focusing app: ${targetAppName}`);
          await focusApp(targetAppName, step.app_bundle_id);
          lastFocusedApp = step.app_name;
          // Wait longer for app to fully activate
          await new Promise(resolve => setTimeout(resolve, 600));
        }
      } catch (error) {
        addLog(`   ⚠️  Failed to focus app: ${error.message}`);
        // Continue execution even if app focus fails
      }
      
      // Validate step
      if (!step || typeof step !== 'object') {
        addLog(`⚠️  Step ${i + 1} is invalid: ${JSON.stringify(step)}`);
        addLog(`   ⏭️  Skipping invalid step and continuing...`);
        addLog(`   ➡️  Continuing to next iteration (i will be ${i + 1})`);
        continue;
      }
      
      const action = (step.action || '').toLowerCase();
      addLog(`   🔍 Extracted action: "${action}" (from step.action: "${step.action}")`);
      
      if (!action || action === 'unknown') {
        addLog(`⚠️  Step ${i + 1} has no valid action, skipping`);
        addLog(`   ⏭️  Skipping step without action and continuing...`);
        addLog(`   ➡️  Continuing to next iteration (i will be ${i + 1})`);
        continue;
      }
      
      addLog(`📍 Step ${i + 1}/${steps.length}: ${action} - ${step.description || 'No description'}`);
      addLog(`   📝 Step details: ${JSON.stringify(step).substring(0, 200)}...`);
      
      // Check if this is a type/backspace step that follows a click step or another type/backspace step
      // (consecutive typing/editing actions should be treated as one continuous session)
      const previousStep = i > 0 ? steps[i - 1] : null;
      const previousAction = previousStep ? (previousStep.action || '').toLowerCase() : null;
      const followsClick = previousAction === 'click';
      const followsType = previousAction === 'type';
      const followsBackspace = previousAction === 'backspace';
      // If it follows a click, type, or backspace, don't re-focus (treat as continuous typing/editing)
      const isContinuousTyping = followsClick || followsType || followsBackspace;
      
      try {
        const maxRetries = step.max_retries || 3;
        const retryDelay = step.retry_delay || 1000; // ms
        const continueOnError = step.continue_on_error || false;
        
        let stepSuccess = false;
        let lastError = null;
        
        // Retry logic with exponential backoff
        for (let attempt = 0; attempt <= maxRetries; attempt++) {
          if (isExecutionCancelled) {
            addLog('⛔ Execution cancelled during retries');
            throw new Error('Cancelled');
          }
          try {
            if (attempt > 0) {
              // Exponential backoff: retryDelay * 2^(attempt-1), max 5 seconds
              const backoffDelay = Math.min(retryDelay * Math.pow(2, attempt - 1), 5000);
              addLog(`   🔄 Retrying step ${i + 1} (attempt ${attempt + 1}/${maxRetries + 1}) after ${backoffDelay}ms...`);
              await new Promise(resolve => setTimeout(resolve, backoffDelay));
            }
            
            switch (action) {
              case 'click':
                addLog(`   🔍 Executing click action...`);
                await executeClickSmart(step);
                // If next step is a type, wait longer to ensure click target is focused
                const nextStep = i < steps.length - 1 ? steps[i + 1] : null;
                if (nextStep && (nextStep.action || '').toLowerCase() === 'type') {
                  addLog(`   ⏳ Click followed by type - waiting longer for input field to be ready...`);
                  await new Promise(resolve => setTimeout(resolve, 500)); // Extra wait for input focus
                }
                break;
              case 'type':
                addLog(`   ⌨️  Executing type action...`);
                addLog(`   📝 Type step details: text="${step.text || '(empty)'}", text_length=${step.text_length || 0}, text_length field=${step.text ? step.text.length : 0}`);
                if (!step.text || step.text.trim() === '') {
                  addLog(`   ⚠️  WARNING: Type step has no text! Step: ${JSON.stringify(step).substring(0, 200)}`);
                }
                try {
                  // Check if next step is also a type (to handle Tab key focus issues)
                  const nextStep = i < steps.length - 1 ? steps[i + 1] : null;
                  const nextIsType = nextStep && (nextStep.action || '').toLowerCase() === 'type';
                  const containsTab = step.text && step.text.includes('\t');
                  
                  // Pass information that this type is part of continuous typing
                  const typeStep = { ...step, _followsClick: followsClick, _followsType: followsType, _followsBackspace: followsBackspace, _isContinuousTyping: isContinuousTyping, _containsTab: containsTab, _nextIsType: nextIsType };
                  await executeType(typeStep);
                  addLog(`   ✅ Type action completed successfully`);
                } catch (typeError) {
                  addLog(`   ❌ Type action failed: ${typeError.message}`);
                  throw typeError;
                }
                break;
              case 'hotkey':
                addLog(`   ⌨️  Executing hotkey action...`);
                await executeHotkey(step);
                break;
              case 'backspace':
                addLog(`   ⌫ Executing backspace action...`);
                // Pass information that this backspace is part of continuous typing/editing
                const backspaceStep = { ...step, _isContinuousTyping: isContinuousTyping };
                await executeBackspace(backspaceStep);
                break;
              case 'scroll':
                addLog(`   📜 Executing scroll action...`);
                await executeScroll(step);
                break;
              case 'move':
                addLog(`   🖱️  Executing move action...`);
                addLog(`   📍 Move step details: x=${step.x}, y=${step.y}, screen_w=${step.screen_w}, screen_h=${step.screen_h}`);
                try {
                  await executeMove(step);
                  addLog(`   ✅ Move action completed successfully`);
                } catch (moveError) {
                  addLog(`   ❌ Move action failed: ${moveError.message}`);
                  throw moveError;
                }
                break;
              case 'wait':
                addLog(`   ⏳ Executing wait action...`);
                await executeWait(step);
                break;
              case 'wait_for_text':
                addLog(`   🔍 Executing wait_for_text action...`);
                await executeWaitForText(step);
                break;
              case 'wait_for_text_disappear':
                addLog(`   🔍 Executing wait_for_text_disappear action...`);
                await executeWaitForTextDisappear(step);
                break;
              case 'screenshot':
                addLog(`   📸 Executing screenshot action (converted to wait)...`);
                await executeWait({ duration: 0.3 });
                break;
              case 'app_activate':
                addLog(`   📱 App activation step - no action needed`);
                await executeWait({ duration: 0.1 });
                break;
              default:
                addLog(`⚠️  Unknown action: ${action} - step details: ${JSON.stringify(step).substring(0, 100)}`);
                await executeWait({ duration: 0.3 });
            }
            
            stepSuccess = true;
            addLog(`✅ Step ${i + 1}/${steps.length} completed successfully`);
            addLog(`   ➡️  Moving to next step...`);
            break; // Success, exit retry loop
            
          } catch (stepError) {
            lastError = stepError;
            addLog(`   ❌ Step ${i + 1} failed (attempt ${attempt + 1}/${maxRetries + 1}): ${stepError.message}`);
            
            if (attempt === maxRetries) {
              // All retries exhausted
              if (continueOnError) {
                addLog(`   ⚠️  Max retries reached, continuing with next step...`);
                stepSuccess = false; // Mark as failed but continue
                break;
              } else {
                addLog(`   ❌ Step ${i + 1} failed after ${maxRetries + 1} attempts, stopping workflow`);
                throw stepError; // Fail the workflow
              }
            }
          }
        }
        
        if (!stepSuccess && !continueOnError) {
          addLog(`❌ Step ${i + 1} did not succeed and continue_on_error is false, stopping workflow`);
          throw lastError || new Error('Step failed');
        }
        
        addLog(`   ✅ Step ${i + 1}/${steps.length} processing complete (success: ${stepSuccess})`);
        
      } catch (stepError) {
        addLog(`   ❌ CAUGHT ERROR in step ${i + 1} catch block: ${stepError.message}`);
        addLog(`   ❌ Error stack: ${stepError.stack || 'No stack trace'}`);
        
        if (step.continue_on_error) {
          addLog(`   ⚠️  Step ${i + 1} failed but continuing due to continue_on_error: ${stepError.message}`);
          addLog(`   ➡️  Continuing to next step...`);
        } else {
          addLog(`❌ Error in step ${i + 1}: ${stepError.message}`);
          addLog(`   ❌ Stopping workflow execution`);
          addLog(`   ❌ This will cause the outer catch to return error`);
          throw stepError;
        }
      }
      
      addLog(`   📍 Completed step ${i + 1}/${steps.length}, ${steps.length - i - 1} steps remaining`);
      addLog(`   ✅ Loop will continue to next iteration (i = ${i}, next will be ${i + 1})\n`);
    }
    
    addLog(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
    addLog(`🎉 LOOP COMPLETED! All ${steps.length} steps processed.`);
    addLog(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
    addLog(`🎉 Workflow execution completed successfully! All ${steps.length} steps processed.`);
    return { success: true, logs: executionLogs };
    
  } catch (error) {
    addLog(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
    addLog(`❌ OUTER CATCH BLOCK: Workflow execution failed`);
    addLog(`❌ Error message: ${error.message}`);
    addLog(`❌ Error stack: ${error.stack || 'No stack trace'}`);
    addLog(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
    return { success: false, error: error.message, logs: executionLogs };
  } finally {
    addLog(`\n🔧 FINALLY BLOCK: Cleaning up global shortcuts...`);
    try { globalShortcut.unregister('Escape'); } catch {}
    try { globalShortcut.unregisterAll(); } catch {}
    addLog(`✅ Cleanup complete`);
    
    // Restore window after execution completes
    try {
      if (mainWindow && !mainWindow.isDestroyed() && windowWasMinimized) {
        addLog('📱 Restoring app window...');
        if (wasMinimized) {
          // Was minimized before we started, keep it minimized
          if (!mainWindow.isMinimized()) {
            mainWindow.minimize();
          }
        } else {
          // Was visible before, restore and show
          if (mainWindow.isMinimized()) {
            mainWindow.restore();
          }
          if (!mainWindow.isVisible()) {
            mainWindow.show();
          }
          // Bring to front
          mainWindow.focus();
        }
        addLog('✅ Window restored');
      }
    } catch (error) {
      addLog(`⚠️  Failed to restore window: ${error.message}`);
    }
  }
});

// IPC handler to cancel current execution
ipcMain.handle('cancel-execution', async () => {
  isExecutionCancelled = true;
  addLog('🛑 Cancel requested');
  
  // Restore window if execution was cancelled
  try {
    if (mainWindow && !mainWindow.isDestroyed()) {
      if (mainWindow.isMinimized()) {
        mainWindow.restore();
        mainWindow.show();
        mainWindow.focus();
      }
    }
  } catch (error) {
    // Ignore errors during cancel
  }
  
  return { success: true };
});

// Helper: focus application on macOS by name with retry
async function focusApp(appName, bundleId) {
  if (process.platform !== 'darwin' || !appName) return;
  
  const maxRetries = 3;
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    if (isExecutionCancelled) return;
    
    try {
      const tryByBundle = bundleId ? `osascript -e 'tell application id "${bundleId}" to activate'` : null;
      const tryByName = `osascript -e 'tell application "${appName}" to activate'`;
      const tryOpen = `open -a "${appName}"`;

      const cmds = [tryByBundle, tryByName, tryOpen].filter(Boolean);
      
      for (const cmd of cmds) {
        if (isExecutionCancelled) return;
        
        try {
          await new Promise((resolve, reject) => {
            exec(cmd, { timeout: 5000 }, (err) => {
              if (err) reject(err);
              else resolve();
            });
          });
          
          // Verify app is actually focused by waiting a bit longer
          // This ensures the app is fully activated and ready for input
          await new Promise(resolve => setTimeout(resolve, 500));
          addLog(`   📱 Focused app: ${appName}`);
          return;
        } catch (err) {
          // Try next command
          continue;
        }
      }
      
      // If all commands failed, wait and retry
      if (attempt < maxRetries - 1) {
        await new Promise(resolve => setTimeout(resolve, 500 * (attempt + 1)));
      }
    } catch (error) {
      if (attempt === maxRetries - 1) {
        addLog(`   ⚠️  Could not focus app: ${appName} (${error.message})`);
      }
    }
  }
}

// Helper: scale coordinates from recording screen to current screen
function scalePointIfNeeded(step, x, y) {
  try {
    const current = screen?.screen?.getPrimaryScreen ? screen.screen.getPrimaryScreen() : null;
    const currentSize = current?.size ? current.size : null;
    const recW = parseInt(step?.screen_w || 0);
    const recH = parseInt(step?.screen_h || 0);
    if (currentSize && recW > 0 && recH > 0) {
      const scaleX = currentSize.width / recW;
      const scaleY = currentSize.height / recH;
      const sx = Math.round(x * scaleX);
      const sy = Math.round(y * scaleY);
      return { x: sx, y: sy };
    }
  } catch {}
  return { x, y };
}

// Execute click action with improved reliability
async function executeClick(step) {
  const rawX = parseInt(step.x || 0);
  const rawY = parseInt(step.y || 0);
  const { x, y } = scalePointIfNeeded(step, rawX, rawY);
  const button = step.button || 'left';
  const clicks = step.clicks || 1;
  const shiftPressed = step.shift_pressed || false;
  const isSelectionStart = step.is_selection_start || false;
  const selectionEndX = step.selection_end_x;
  const selectionEndY = step.selection_end_y;

  // Validate coordinates
  if (x === 0 && y === 0) {
    throw new Error('Invalid coordinates (0, 0)');
  }

  if (isNaN(x) || isNaN(y)) {
    throw new Error(`Invalid coordinates (NaN): x=${x}, y=${y}`);
  }

  // Handle Shift+click selections
  if (shiftPressed && isSelectionStart && selectionEndX !== undefined && selectionEndY !== undefined) {
    const { x: endX, y: endY } = scalePointIfNeeded(step, parseInt(selectionEndX), parseInt(selectionEndY));
    addLog(`   📋 Shift+click selection from (${x}, ${y}) to (${endX}, ${endY})...`);
    
    // First click at start position
    await executeMove({ x, y, screen_w: step.screen_w, screen_h: step.screen_h });
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Press Shift
    await keyboard.pressKey(Key.LeftShift);
    await new Promise(resolve => setTimeout(resolve, 50));
    
    // Click at start position
    const mouseButton = button === 'right' ? Button.RIGHT : button === 'middle' ? Button.MIDDLE : Button.LEFT;
    await mouse.click(mouseButton);
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Move to end position while Shift is held
    await executeMove({ x: endX, y: endY, screen_w: step.screen_w, screen_h: step.screen_h });
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Click at end position (completing the selection)
    await mouse.click(mouseButton);
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Release Shift
    await keyboard.releaseKey(Key.LeftShift);
    
    addLog(`   ✅ Shift+click selection completed`);
    await new Promise(resolve => setTimeout(resolve, 200));
    return;
  }

  addLog(`   🖱️  Moving to (${x}, ${y})...`);
  
  try {
    // Get current mouse position for debugging
    let currentPos;
    try {
      currentPos = await mouse.getPosition();
      addLog(`   📍 Current mouse position: (${currentPos.x}, ${currentPos.y})`);
    } catch (err) {
      addLog(`   ❌ Cannot get mouse position: ${err.message}`);
      addLog(`   ⚠️  Check Accessibility permissions in System Settings`);
      throw new Error(`Mouse access denied: ${err.message}`);
    }
    
    // Move to position with smooth animation and retry logic
    if (isExecutionCancelled) throw new Error('Cancelled');
    
    const maxMoveRetries = 3;
    let moveSuccess = false;
    
    // Calculate distance for smooth movement
    const distance = Math.sqrt(Math.pow(currentPos.x - x, 2) + Math.pow(currentPos.y - y, 2));
    const steps = Math.max(Math.floor(distance / 10), 5); // At least 5 steps, more for longer distances
    const duration = Math.min(distance / 500, 0.5); // Max 500ms, scales with distance
    
    addLog(`   📏 Moving ${Math.round(distance)}px over ${Math.round(duration * 1000)}ms (${steps} steps)...`);
    
    for (let moveAttempt = 0; moveAttempt < maxMoveRetries; moveAttempt++) {
      if (isExecutionCancelled) throw new Error('Cancelled');
      
      try {
        // Use smooth movement for better reliability on macOS
        if (distance > 50 && steps > 5) {
          // Smooth animation for longer distances
          const stepDelay = duration / steps;
          for (let step = 1; step <= steps; step++) {
            if (isExecutionCancelled) throw new Error('Cancelled');
            const progress = step / steps;
            const easeProgress = progress * (2 - progress); // Ease-out
            const stepX = Math.round(currentPos.x + (x - currentPos.x) * easeProgress);
            const stepY = Math.round(currentPos.y + (y - currentPos.y) * easeProgress);
            
            await mouse.setPosition({ x: stepX, y: stepY });
            await new Promise(resolve => setTimeout(resolve, stepDelay * 1000));
          }
        } else {
          // Direct movement for short distances
          await mouse.setPosition({ x, y });
        }
        
        // Wait for position to stabilize
        await new Promise(resolve => setTimeout(resolve, 200));
        
        // Verify position was set correctly
        let newPos;
        try {
          newPos = await mouse.getPosition();
        } catch (err) {
          throw new Error(`Cannot verify mouse position: ${err.message}`);
        }
        
        const offsetX = Math.abs(newPos.x - x);
        const offsetY = Math.abs(newPos.y - y);
        
        // Allow up to 10 pixels offset (some systems have DPI scaling or rounding)
        if (offsetX <= 10 && offsetY <= 10) {
          moveSuccess = true;
          addLog(`   ✅ Mouse moved to (${newPos.x}, ${newPos.y}) - verified (offset: ${Math.round(offsetX)}, ${Math.round(offsetY)})`);
          break;
        } else {
          if (moveAttempt < maxMoveRetries - 1) {
            addLog(`   ⚠️  Position off by (${Math.round(offsetX)}, ${Math.round(offsetY)}), retrying move...`);
            await new Promise(resolve => setTimeout(resolve, 150));
            // Update currentPos for next attempt
            currentPos = newPos;
          } else {
            // Last attempt, log but continue if reasonably close
            if (offsetX <= 20 && offsetY <= 20) {
              addLog(`   ⚠️  Position off by (${Math.round(offsetX)}, ${Math.round(offsetY)}), but continuing (within tolerance)...`);
              moveSuccess = true;
            } else {
              addLog(`   ❌ Position off by (${Math.round(offsetX)}, ${Math.round(offsetY)}), exceeds tolerance`);
            }
          }
        }
      } catch (err) {
        if (moveAttempt === maxMoveRetries - 1) {
          addLog(`   ❌ Cannot move mouse after ${maxMoveRetries} attempts: ${err.message}`);
          addLog(`   ⚠️  Check Accessibility permissions in System Settings`);
          throw new Error(`Mouse control denied: ${err.message}`);
        }
        await new Promise(resolve => setTimeout(resolve, 150));
      }
    }
    
    if (!moveSuccess) {
      throw new Error('Failed to move mouse to target position');
    }
    
    if (isExecutionCancelled) throw new Error('Cancelled');
    
    // Reduced wait before clicking (mouse is already at position from movement)
    await new Promise(resolve => setTimeout(resolve, 100));
    
    addLog(`   👆 Clicking ${button} button ${clicks} time(s)...`);
    
    const mouseButton = button === 'right' ? Button.RIGHT : button === 'middle' ? Button.MIDDLE : Button.LEFT;
    
    try {
      // For double clicks, use optimized trackpad-style timing
      if (clicks === 2) {
        // First click
        if (isExecutionCancelled) throw new Error('Cancelled');
        try {
          if (typeof mouse.pressButton === 'function' && typeof mouse.releaseButton === 'function') {
            await mouse.pressButton(mouseButton);
            await new Promise(resolve => setTimeout(resolve, 20)); // Fast press/release
            await mouse.releaseButton(mouseButton);
          } else {
            await mouse.click(mouseButton);
          }
        } catch (clickErr) {
          try {
            await mouse.click(mouseButton);
          } catch (fallbackErr) {
            throw clickErr;
          }
        }
        
        // Very short delay between clicks for double tap
        await new Promise(resolve => setTimeout(resolve, 30));
        
        // Second click
        if (isExecutionCancelled) throw new Error('Cancelled');
        try {
          if (typeof mouse.pressButton === 'function' && typeof mouse.releaseButton === 'function') {
            await mouse.pressButton(mouseButton);
            await new Promise(resolve => setTimeout(resolve, 20));
            await mouse.releaseButton(mouseButton);
          } else {
            await mouse.click(mouseButton);
          }
        } catch (clickErr) {
          try {
            await mouse.click(mouseButton);
          } catch (fallbackErr) {
            throw clickErr;
          }
        }
      } else {
        // Single click or triple+
        for (let i = 0; i < clicks; i++) {
          if (isExecutionCancelled) throw new Error('Cancelled');
          
          try {
            if (typeof mouse.pressButton === 'function' && typeof mouse.releaseButton === 'function') {
              await mouse.pressButton(mouseButton);
              await new Promise(resolve => setTimeout(resolve, 30)); // Reduced from 50ms
              await mouse.releaseButton(mouseButton);
            } else {
              await mouse.click(mouseButton);
            }
          } catch (clickErr) {
            try {
              await mouse.click(mouseButton);
            } catch (fallbackErr) {
              throw clickErr;
            }
          }
          
          if (i < clicks - 1) {
            await new Promise(resolve => setTimeout(resolve, 100)); // Reduced from 150ms
          }
        }
      }
    } catch (err) {
      addLog(`   ❌ Cannot click mouse: ${err.message}`);
      addLog(`   ⚠️  Check Accessibility permissions in System Settings`);
      throw new Error(`Mouse click denied: ${err.message}`);
    }
    
    addLog(`   ✅ Clicked at (${x}, ${y})`);
    
    // Reduced wait after click (faster execution)
    await new Promise(resolve => setTimeout(resolve, 200)); // Reduced from 400ms
  } catch (error) {
    addLog(`   ❌ Error clicking: ${error.message}`);
    throw error;
  }
}

// Execute click smart: try OCR text if available, then coordinates fallback
async function executeClickSmart(step) {
  const hasText = !!step.find_by_text;
  const rawX = parseInt(step.x || 0);
  const rawY = parseInt(step.y || 0);
  const hasCoordinates = !isNaN(rawX) && !isNaN(rawY) && (rawX !== 0 || rawY !== 0);
  
  // If we have coordinates, skip OCR to avoid delays - use coordinates directly
  // OCR is only useful when we don't have coordinates
  if (hasCoordinates) {
    addLog(`   🖱️  Using coordinates directly (skipping OCR for speed)...`);
    await executeClick(step);
    return;
  }
  
  // Only try OCR if we don't have coordinates
  if (hasText && !hasCoordinates) {
    addLog(`   🔍 No coordinates available, trying OCR...`);
    try {
      const fastStep = { ...step, timeout: 1.0 }; // 1 second timeout for OCR-only
      await executeClickText(fastStep);
      return;
    } catch (e) {
      addLog(`   ❌ OCR failed: ${e.message}`);
      throw e;
    }
  }
  
  // If only text, try OCR with normal timeout
  if (hasText) {
    try {
      await executeClickText(step);
      return;
    } catch (e) {
      addLog(`   ❌ OCR click failed: ${e.message}`);
      throw e;
    }
  }
  
  // If only coordinates, use them
  if (hasCoordinates) {
    await executeClick(step);
    return;
  }
  
  // No valid target
  throw new Error('No valid click target (neither text nor coordinates)');
}

// Execute type action with improved reliability
async function executeType(step) {
  // Extract text from step - check multiple possible fields
  const text = step.text || step.text_content || step.typed_text || '';
  
  if (!text || (typeof text === 'string' && text.trim() === '')) {
    addLog(`   ⚠️  No text to type in step`);
    addLog(`   📋 Step keys: ${Object.keys(step).join(', ')}`);
    addLog(`   📋 Full step (first 500 chars): ${JSON.stringify(step).substring(0, 500)}`);
    return;
  }
  
  // Ensure text is a string
  const textToType = typeof text === 'string' ? text : String(text);
  
  addLog(`   ⌨️  Typing: "${textToType.substring(0, 50)}${textToType.length > 50 ? '...' : ''}" (${textToType.length} chars)`);
  if (isExecutionCancelled) throw new Error('Cancelled');
  
  try {
    // Check if this type step is part of continuous typing (follows click, type, or backspace)
    const followsClick = step._followsClick || false;
    const followsType = step._followsType || false;
    const followsBackspace = step._followsBackspace || false;
    const isContinuousTyping = step._isContinuousTyping || false;
    const containsTab = step._containsTab || false;
    const nextIsType = step._nextIsType || false;
    
    // Ensure the app is focused before typing (if app info is available)
    const targetAppName = step.app_name;
    const targetBundleId = step.app_bundle_id;
    
    // Helper function to ensure app is focused
    const ensureAppFocused = async () => {
      if (targetAppName || targetBundleId) {
        await focusApp(targetAppName, targetBundleId);
        // focusApp already waits 500ms, but add a small extra delay for input readiness
        await new Promise(resolve => setTimeout(resolve, 200));
      }
    };
    
    // If this type is part of continuous typing (follows click or another type),
    // the input field should already be focused, so don't re-focus the app
    if (isContinuousTyping) {
      if (followsClick) {
        addLog(`   📝 Type follows click - input field should already be focused`);
        addLog(`   ⏳ Waiting for input field to be ready for typing...`);
        // Wait longer to ensure the clicked input field is fully focused and ready
        await new Promise(resolve => setTimeout(resolve, 600));
      } else if (followsType) {
        addLog(`   📝 Type follows another type - continuing typing in same input field`);
        // Just a small wait to ensure input is still ready (don't re-focus)
        await new Promise(resolve => setTimeout(resolve, 100));
      } else if (followsBackspace) {
        addLog(`   📝 Type follows backspace - continuing typing in same input field`);
        // Just a small wait to ensure input is still ready (don't re-focus)
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    } else {
      // Focus app before starting to type (normal case - standalone type action)
      await ensureAppFocused();
    }
    
    // Special handling for Tab key: if text contains Tab and next step is type,
    // we need to prevent focus from shifting by re-focusing after Tab
    if (containsTab && nextIsType) {
      addLog(`   ⚠️  Text contains Tab and next step is type - will re-focus after Tab to prevent focus shift`);
      
      // Split text by Tab characters
      const parts = textToType.split('\t');
      
      for (let partIndex = 0; partIndex < parts.length; partIndex++) {
        if (isExecutionCancelled) throw new Error('Cancelled');
        
        const part = parts[partIndex];
        
        // Type the text part (if not empty)
        if (part.length > 0) {
          if (part.length > 100) {
            // For long parts, type in chunks
            const chunkSize = 50;
            for (let i = 0; i < part.length; i += chunkSize) {
              if (isExecutionCancelled) throw new Error('Cancelled');
              const chunk = part.substring(i, i + chunkSize);
              addLog(`   ⌨️  Typing chunk: "${chunk.substring(0, 20)}..."`);
              await keyboard.type(chunk);
              await new Promise(resolve => setTimeout(resolve, 50));
            }
          } else {
            await keyboard.type(part);
          }
        }
        
        // If this is not the last part, type Tab and re-focus
        if (partIndex < parts.length - 1) {
          addLog(`   ⌨️  Typing Tab key...`);
          await keyboard.pressKey(Key.Tab);
          await new Promise(resolve => setTimeout(resolve, 50));
          await keyboard.releaseKey(Key.Tab);
          await new Promise(resolve => setTimeout(resolve, 100));
          
          // Re-focus the app to prevent focus from shifting away
          addLog(`   🔄 Re-focusing app after Tab to prevent focus shift...`);
          await ensureAppFocused();
          await new Promise(resolve => setTimeout(resolve, 200)); // Extra wait for input field to be ready
        }
      }
    } else {
      // Normal typing without special Tab handling
      // Type with small delay between characters for reliability
      // For longer text, type in chunks and re-focus between chunks (unless following a click)
      if (textToType.length > 100) {
        const chunkSize = 50;
        for (let i = 0; i < textToType.length; i += chunkSize) {
          if (isExecutionCancelled) throw new Error('Cancelled');
          
          // Only re-focus if NOT part of continuous typing (continuous typing should keep input focused)
          if (!isContinuousTyping) {
            await ensureAppFocused();
          } else {
            // Just a small wait to ensure input is still ready (don't re-focus)
            await new Promise(resolve => setTimeout(resolve, 100));
          }
          
          const chunk = textToType.substring(i, i + chunkSize);
          addLog(`   ⌨️  Typing chunk ${Math.floor(i/chunkSize) + 1}: "${chunk.substring(0, 20)}..."`);
          await keyboard.type(chunk);
          await new Promise(resolve => setTimeout(resolve, 100)); // Slightly longer delay between chunks
        }
      } else {
        // For shorter text, only ensure focus if NOT part of continuous typing
        if (!isContinuousTyping) {
          await ensureAppFocused();
        }
        await keyboard.type(textToType);
      }
    }
    
    addLog(`   ✅ Typed ${textToType.length} characters successfully`);
    
    // Wait for text to be processed
    await new Promise(resolve => setTimeout(resolve, 300));
  } catch (error) {
    addLog(`   ❌ Keyboard error: ${error.message}`);
    addLog(`   ⚠️  Check Accessibility permissions in System Settings`);
    addLog(`   📋 Error details: ${error.stack || 'No stack trace'}`);
    throw error;
  }
}

// Execute backspace action
async function executeBackspace(step) {
  addLog(`   ⌫ Pressing Backspace...`);
  if (isExecutionCancelled) throw new Error('Cancelled');
  
  try {
    // Check if this backspace is part of continuous typing/editing
    const isContinuousTyping = step._isContinuousTyping || false;
    
    // Only re-focus app if NOT part of continuous typing (continuous typing should keep input focused)
    if (!isContinuousTyping) {
      // Ensure the app is focused before pressing backspace (if app info is available)
      if (step.app_name || step.app_bundle_id) {
        await focusApp(step.app_name, step.app_bundle_id);
        await new Promise(resolve => setTimeout(resolve, 200)); // Wait for app to focus
      }
    } else {
      addLog(`   📝 Backspace follows typing - input field should already be focused`);
      // Just a small wait to ensure input is still ready (don't re-focus)
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    // Press backspace key
    await keyboard.pressKey(Key.Backspace);
    await new Promise(resolve => setTimeout(resolve, 20));
    await keyboard.releaseKey(Key.Backspace);
    
    addLog(`   ✅ Backspace pressed`);
    
    // Wait a moment for the backspace to take effect
    await new Promise(resolve => setTimeout(resolve, 100));
  } catch (error) {
    addLog(`   ❌ Backspace error: ${error.message}`);
    addLog(`   ⚠️  Check Accessibility permissions in System Settings`);
    throw error;
  }
}

// Execute hotkey action - supports dynamic key sequences from keylogger
async function executeHotkey(step) {
  // Use dynamic key_sequence if available (keylogger-style), otherwise fall back to keys array
  const keySequence = step.key_sequence || [];
  const keys = step.keys || [];
  
  if (keySequence.length === 0 && keys.length === 0) {
    addLog(`   ⚠️  No keys to press`);
    return;
  }
  
  // Map common key names to nut.js Key enum (cross-platform)
  // On macOS: cmd = Command key, on Windows: cmd/win = Windows key
  const keyMap = {
    'cmd': Key.LeftSuper,
    'command': Key.LeftSuper,
    'win': Key.LeftSuper,      // Windows key alias (Windows)
    'windows': Key.LeftSuper,  // Windows key alias (Windows)
    'super': Key.LeftSuper,     // Super key alias (Linux)
    'ctrl': Key.LeftControl,
    'control': Key.LeftControl,
    'alt': Key.LeftAlt,
    'option': Key.LeftAlt,
    'shift': Key.LeftShift,
    'enter': Key.Enter,
    'return': Key.Enter,
    'space': Key.Space,
    'tab': Key.Tab,
    'escape': Key.Escape,
    'esc': Key.Escape,
    'backspace': Key.Backspace,
    'delete': Key.Delete,
    'up': Key.Up,
    'down': Key.Down,
    'left': Key.Left,
    'right': Key.Right,
    'home': Key.Home,
    'end': Key.End,
    'pageup': Key.PageUp,
    'pagedown': Key.PageDown,
    'f1': Key.F1,
    'f2': Key.F2,
    'f3': Key.F3,
    'f4': Key.F4,
    'f5': Key.F5,
    'f6': Key.F6,
    'f7': Key.F7,
    'f8': Key.F8,
    'f9': Key.F9,
    'f10': Key.F10,
    'f11': Key.F11,
    'f12': Key.F12,
  };
  
  // If we have key_sequence (dynamic keylogger data), use it for accurate replay
  if (keySequence.length > 0) {
    addLog(`   ⌨️  Replaying key sequence: ${keySequence.length} keys (dynamic keylogger capture)`);
    
    try {
      // Replay keys in the exact order they were pressed
      const pressedKeys = new Map(); // Track which keys are currently pressed
      
      for (const keyInfo of keySequence) {
        if (isExecutionCancelled) throw new Error('Cancelled');
        
        const keyType = keyInfo.type; // 'char', 'key', or 'unknown'
        const keyValue = keyInfo.value;
        
        // Convert to nut.js Key enum
        let nutKey = null;
        if (keyType === 'char') {
          // Character key - try to find in Key enum first
          try {
            nutKey = Key[keyValue.toUpperCase()];
          } catch {
            // Not in enum, use type() method
            nutKey = keyValue;
          }
        } else if (keyType === 'key') {
          // Special key - use keyMap
          nutKey = keyMap[keyValue.toLowerCase()];
        }
        
        if (nutKey) {
          // Press the key
          if (typeof nutKey === 'string') {
            // Character key - use type()
            await keyboard.type(nutKey);
          } else {
            // Special key - use pressKey
            await keyboard.pressKey(nutKey);
            pressedKeys.set(keyValue, nutKey);
          }
          await new Promise(resolve => setTimeout(resolve, 20)); // Small delay between keys
        }
      }
      
      // Release all pressed keys
      for (const nutKey of pressedKeys.values()) {
        await keyboard.releaseKey(nutKey);
      }
      
      addLog(`   ✅ Key sequence replayed successfully`);
      await new Promise(resolve => setTimeout(resolve, 300));
      return;
    } catch (error) {
      addLog(`   ⚠️  Error replaying key sequence, falling back to keys array: ${error.message}`);
      // Fall through to use keys array as fallback
    }
  }
  
  // Fallback to original keys array method (backward compatibility)
  addLog(`   ⌨️  Pressing: ${keys.join(' + ')}`);
  
  // Separate modifiers from regular keys
  const modifiers = [];
  const regularKeys = [];
  
  for (const k of keys) {
    const lower = k.toLowerCase();
    // Cross-platform modifier detection
    if (lower === 'cmd' || lower === 'command' || lower === 'win' || lower === 'windows' || lower === 'super' ||
        lower === 'ctrl' || lower === 'control' || 
        lower === 'alt' || lower === 'option' || lower === 'shift') {
      modifiers.push(keyMap[lower]);
    } else {
      // Regular key or special key
      if (keyMap[lower]) {
        regularKeys.push(keyMap[lower]);
      } else if (k.length === 1) {
        // Single character - use type() method for single chars
        // For key combinations, we'll use the character directly
        try {
          // Try to find in Key enum first
          const keyEnum = Key[k.toUpperCase()];
          if (keyEnum !== undefined) {
            regularKeys.push(keyEnum);
          } else {
            // For single characters in combinations, we can use type() or Key enum
            // nut.js handles single chars differently - use type for single chars
            regularKeys.push(k);
          }
        } catch {
          // If not found, use character directly
          regularKeys.push(k);
        }
      } else {
        // Try to find in Key enum
        try {
          regularKeys.push(Key[k]);
        } catch {
          addLog(`   ⚠️  Unknown key: ${k}`);
        }
      }
    }
  }
  
  // Press all keys together
  if (modifiers.length > 0 || regularKeys.length > 0) {
    // Handle single character with modifiers (e.g., cmd+c, ctrl+v)
    if (modifiers.length > 0 && regularKeys.length === 1 && typeof regularKeys[0] === 'string') {
      const char = regularKeys[0].toUpperCase();
      addLog(`   ⌨️  Pressing combination: ${keys.join('+')} (modifier + character)`);
      
      // For character keys with modifiers (like cmd+c, cmd+v), we need to use the character key directly
      // nut.js Key enum doesn't have all character keys, so we'll use a different approach
      const charLower = regularKeys[0].toLowerCase();
      
      // Press modifiers first
      if (isExecutionCancelled) throw new Error('Cancelled');
      await keyboard.pressKey(...modifiers);
      await new Promise(resolve => setTimeout(resolve, 30));
      
      // For character keys with modifiers (cmd+c, cmd+v), nut.js Key enum doesn't have character keys
      // We need to use the keyboard API to press the character key while modifiers are held
      // nut.js supports this by using the character directly in pressKey when modifiers are held
      if (isExecutionCancelled) throw new Error('Cancelled');
      
      // Use keyboard.pressKey with modifiers and character together
      // nut.js will handle the character key press correctly when modifiers are already pressed
      // We'll use the character as a string, which nut.js should handle
      try {
        // Press the character key while modifiers are held
        // nut.js keyboard API should handle character keys when used with pressKey
        await keyboard.pressKey(charLower);
        await new Promise(resolve => setTimeout(resolve, 30));
        await keyboard.releaseKey(charLower);
      } catch (err) {
        // If that doesn't work, try using type() as fallback (though it may not work with modifiers)
        addLog(`   ⚠️  Direct key press failed, trying alternative: ${err.message}`);
        // Note: type() won't work with modifiers held, but it's a fallback
        await keyboard.type(charLower);
      }
      
      // Release modifiers
      await new Promise(resolve => setTimeout(resolve, 30));
      await keyboard.releaseKey(...modifiers);
    } else {
      // For other combinations (modifiers + special keys, or just special keys)
      const allKeys = [];
      
      // Add modifiers
      allKeys.push(...modifiers);
      
      // Add regular keys (filter out strings, convert to Key enum)
      for (const k of regularKeys) {
        if (typeof k !== 'string') {
          allKeys.push(k);
        } else {
          // Try to convert string to Key enum
          try {
            const keyEnum = Key[k.toUpperCase()];
            if (keyEnum !== undefined) {
              allKeys.push(keyEnum);
            }
          } catch {
            // Skip if can't convert
          }
        }
      }
      
      if (allKeys.length > 0) {
        addLog(`   ⌨️  Pressing combination: ${keys.join('+')} (${allKeys.length} keys)`);
        
        // Press all keys simultaneously
        if (isExecutionCancelled) throw new Error('Cancelled');
        await keyboard.pressKey(...allKeys);
        await new Promise(resolve => setTimeout(resolve, 50));
        // Release all keys
        await keyboard.releaseKey(...allKeys);
      }
    }
  }
  
  await new Promise(resolve => setTimeout(resolve, 300));
}

// Execute click by finding text (OCR-based) with improved reliability
async function executeClickText(step) {
  const searchText = step.find_by_text || step.text;
  const button = step.button || 'left';
  const timeout = Math.min((step.timeout || 3000) * 1000, 5000); // Convert to ms, max 5s (reduced from 10s)
  const retries = step.retries || 3;
  
  if (!searchText || searchText.trim() === '') {
    throw new Error('No text specified for find_by_text');
  }
  
  addLog(`   🔍 Finding and clicking text: '${searchText}' (timeout: ${timeout/1000}s)...`);
  
  // Check if backend is available
  const backendAvailable = await checkBackendHealth();
  if (!backendAvailable) {
    addLog(`   ⚠️  Backend API not available, cannot perform OCR search`);
    throw new Error('Backend API not available - make sure the Python backend server is running');
  }
  
  try {
    if (isExecutionCancelled) throw new Error('Cancelled');
    
    // Use axios with proper timeout and retry logic
    const response = await apiCall(
      `${BACKEND_URL}/api/automation/find-text`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        data: { 
          text: searchText, 
          timeout: timeout / 1000 // Backend expects seconds
        },
        timeout: timeout + 1000 // Add buffer for network (reduced from 2000)
      },
      1 // Max 1 retry for API calls (reduced from 2 to fail faster)
    );
    
    const result = response.data;
    
    if (result && result.found) {
      const { center } = result;
      
      if (!center || !Array.isArray(center) || center.length < 2) {
        throw new Error('Invalid center coordinates from OCR');
      }
      
      const [x, y] = center;
      
      if (isNaN(x) || isNaN(y) || x < 0 || y < 0) {
        throw new Error(`Invalid coordinates from OCR: (${x}, ${y})`);
      }
      
      addLog(`   ✅ Found '${searchText}' at (${Math.round(x)}, ${Math.round(y)})`);
      
      if (isExecutionCancelled) throw new Error('Cancelled');
      
      // Use the improved click function with proper coordinates
      const clickStep = {
        ...step,
        x: Math.round(x),
        y: Math.round(y),
        button: button,
        clicks: step.clicks || 1
      };
      
      // Execute click using the reliable click function
      await executeClick(clickStep);
      addLog(`   👆 Clicked '${searchText}'`);
    } else {
      throw new Error(`Text '${searchText}' not found on screen`);
    }
  } catch (error) {
    if (error.message === 'Cancelled') {
      throw error;
    }
    addLog(`   ❌ OCR search failed: ${error.message}`);
    throw error;
  }
}

// Execute wait for text to appear with improved reliability
async function executeWaitForText(step) {
  const searchText = step.text || step.wait_for_text;
  const timeout = (step.timeout || 10) * 1000; // Convert to ms
  const checkInterval = Math.max((step.check_interval || 0.5) * 1000, 500); // Min 500ms
  
  if (!searchText || searchText.trim() === '') {
    throw new Error('No text specified for wait_for_text');
  }
  
  addLog(`   ⏳ Waiting for text '${searchText}' to appear (timeout: ${timeout/1000}s)...`);
  
  // Check if backend is available
  const backendAvailable = await checkBackendHealth();
  if (!backendAvailable) {
    addLog(`   ⚠️  Backend API not available, cannot wait for text`);
    throw new Error('Backend API not available - make sure the Python backend server is running');
  }
  
  const startTime = Date.now();
  let lastError = null;
  
  while (Date.now() - startTime < timeout) {
    if (isExecutionCancelled) throw new Error('Cancelled');
    
    try {
      const response = await apiCall(
        `${BACKEND_URL}/api/automation/find-text`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          data: { text: searchText, timeout: 1 },
          timeout: 3000 // 3 second timeout per check
        },
        1 // 1 retry per check
      );
      
      const result = response.data;
      if (result && result.found) {
        addLog(`   ✅ Text '${searchText}' appeared!`);
        return;
      }
      
      lastError = null; // Reset error on successful API call
    } catch (error) {
      lastError = error;
      // Continue checking unless it's a cancellation
      if (error.message === 'Cancelled') {
        throw error;
      }
    }
    
    await new Promise(resolve => setTimeout(resolve, checkInterval));
  }
  
  const errorMsg = lastError 
    ? `Text '${searchText}' did not appear within ${timeout/1000} seconds (last error: ${lastError.message})`
    : `Text '${searchText}' did not appear within ${timeout/1000} seconds`;
  throw new Error(errorMsg);
}

// Execute wait for text to disappear with improved reliability
async function executeWaitForTextDisappear(step) {
  const searchText = step.text || step.wait_for_text_disappear;
  const timeout = (step.timeout || 10) * 1000; // Convert to ms
  const checkInterval = Math.max((step.check_interval || 0.5) * 1000, 500); // Min 500ms
  
  if (!searchText || searchText.trim() === '') {
    throw new Error('No text specified for wait_for_text_disappear');
  }
  
  addLog(`   ⏳ Waiting for text '${searchText}' to disappear (timeout: ${timeout/1000}s)...`);
  
  // Check if backend is available
  const backendAvailable = await checkBackendHealth();
  if (!backendAvailable) {
    addLog(`   ⚠️  Backend API not available, cannot wait for text`);
    throw new Error('Backend API not available - make sure the Python backend server is running');
  }
  
  const startTime = Date.now();
  let lastError = null;
  
  while (Date.now() - startTime < timeout) {
    if (isExecutionCancelled) throw new Error('Cancelled');
    
    try {
      const response = await apiCall(
        `${BACKEND_URL}/api/automation/find-text`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          data: { text: searchText, timeout: 1 },
          timeout: 3000 // 3 second timeout per check
        },
        1 // 1 retry per check
      );
      
      const result = response.data;
      if (result && !result.found) {
        addLog(`   ✅ Text '${searchText}' disappeared!`);
        return;
      }
      
      lastError = null; // Reset error on successful API call
    } catch (error) {
      lastError = error;
      // Continue checking unless it's a cancellation
      if (error.message === 'Cancelled') {
        throw error;
      }
    }
    
    await new Promise(resolve => setTimeout(resolve, checkInterval));
  }
  
  const errorMsg = lastError 
    ? `Text '${searchText}' did not disappear within ${timeout/1000} seconds (last error: ${lastError.message})`
    : `Text '${searchText}' did not disappear within ${timeout/1000} seconds`;
  throw new Error(errorMsg);
}

// Execute scroll action
async function executeScroll(step) {
  const amount = parseInt(step.amount || 0);
  const dy = parseFloat(step.dy || 0);
  const scrollAmount = amount !== 0 ? amount : Math.round(dy * 100);
  
  if (step.x !== undefined && step.y !== undefined) {
    const rawX = parseInt(step.x);
    const rawY = parseInt(step.y);
    const { x, y } = scalePointIfNeeded(step, rawX, rawY);
    addLog(`   🖱️  Moving to (${x}, ${y}) for scroll...`);
    if (isExecutionCancelled) throw new Error('Cancelled');
    
    await mouse.setPosition({ x, y });
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  
  addLog(`   🔄 Scrolling ${scrollAmount} units...`);
  
  // nut.js scroll (positive = up, negative = down)
  const scrollDir = scrollAmount > 0 ? up : down;
  const scrollTimes = Math.abs(Math.round(scrollAmount / 10));
  
  for (let i = 0; i < scrollTimes; i++) {
    if (isExecutionCancelled) throw new Error('Cancelled');
    await mouse.scrollDown(1);
    await new Promise(resolve => setTimeout(resolve, 10));
  }
  
  await new Promise(resolve => setTimeout(resolve, 200));
}

// Execute move action - smoothly move mouse to recorded position
async function executeMove(step) {
  const rawX = parseInt(step.x || 0);
  const rawY = parseInt(step.y || 0);
  const { x, y } = scalePointIfNeeded(step, rawX, rawY);
  
  // Validate coordinates
  if (isNaN(x) || isNaN(y)) {
    throw new Error(`Invalid coordinates (NaN): x=${x}, y=${y}`);
  }
  
  addLog(`   🖱️  Moving to (${x}, ${y})...`);
  
  try {
    // Get current mouse position
    let currentPos;
    try {
      currentPos = await mouse.getPosition();
      addLog(`   📍 Current mouse position: (${currentPos.x}, ${currentPos.y})`);
    } catch (err) {
      addLog(`   ❌ Cannot get mouse position: ${err.message}`);
      addLog(`   ⚠️  Check Accessibility permissions in System Settings`);
      throw new Error(`Mouse access denied: ${err.message}`);
    }
    
    if (isExecutionCancelled) throw new Error('Cancelled');
    
    // Calculate distance for smooth movement
    const distance = Math.sqrt(Math.pow(currentPos.x - x, 2) + Math.pow(currentPos.y - y, 2));
    
    // If distance is very small, just move directly
    if (distance < 5) {
      addLog(`   ✅ Already at target position (distance: ${Math.round(distance)}px)`);
      return;
    }
    
    // Calculate smooth movement parameters
    const steps = Math.max(Math.floor(distance / 5), 3); // At least 3 steps, more for longer distances
    const duration = Math.min(distance / 300, 0.3); // Max 300ms, scales with distance (faster than click movement)
    
    addLog(`   📏 Moving ${Math.round(distance)}px over ${Math.round(duration * 1000)}ms (${steps} steps)...`);
    
    // Smooth animation for movement
    const stepDelay = duration / steps;
    for (let step = 1; step <= steps; step++) {
      if (isExecutionCancelled) throw new Error('Cancelled');
      
      const progress = step / steps;
      const easeProgress = progress * (2 - progress); // Ease-out curve
      const stepX = Math.round(currentPos.x + (x - currentPos.x) * easeProgress);
      const stepY = Math.round(currentPos.y + (y - currentPos.y) * easeProgress);
      
      await mouse.setPosition({ x: stepX, y: stepY });
      await new Promise(resolve => setTimeout(resolve, stepDelay * 1000));
    }
    
    // Verify final position
    try {
      const finalPos = await mouse.getPosition();
      const offsetX = Math.abs(finalPos.x - x);
      const offsetY = Math.abs(finalPos.y - y);
      
      if (offsetX <= 10 && offsetY <= 10) {
        addLog(`   ✅ Mouse moved to (${finalPos.x}, ${finalPos.y}) - verified`);
      } else {
        addLog(`   ⚠️  Mouse position off by (${Math.round(offsetX)}, ${Math.round(offsetY)}), but continuing...`);
      }
    } catch (err) {
      addLog(`   ⚠️  Could not verify final position: ${err.message}`);
    }
    
    // Small delay after movement to allow UI to update
    await new Promise(resolve => setTimeout(resolve, 50));
    
  } catch (error) {
    if (error.message === 'Cancelled') {
      throw error;
    }
    addLog(`   ❌ Error moving mouse: ${error.message}`);
    throw error;
  }
}

// Execute wait action
async function executeWait(step) {
  const duration = parseFloat(step.duration || step.timeout || 1);
  if (isNaN(duration) || duration < 0) {
    addLog(`   ⚠️  Invalid duration: ${step.duration}, using default 1s`);
    await new Promise(resolve => setTimeout(resolve, 1000));
    return;
  }
  addLog(`   ⏳ Waiting ${duration}s...`);
  const waitUntil = Date.now() + duration * 1000;
  while (Date.now() < waitUntil) {
    if (isExecutionCancelled) throw new Error('Cancelled');
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  addLog(`   ✅ Wait completed`);
}

// Get execution logs
ipcMain.handle('get-execution-logs', async () => {
  return executionLogs;
});

// Clear execution logs
ipcMain.handle('clear-execution-logs', async () => {
  executionLogs = [];
  return { success: true };
});


