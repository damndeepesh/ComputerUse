import threading
import time
import os
import wave
from datetime import datetime
from pathlib import Path

try:
    import speech_recognition as sr
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("⚠️  Audio recording unavailable (install: brew install portaudio && pip install pyaudio)")


class AudioRecorder:
    def __init__(self, recordings_dir=None):
        self.is_recording = False
        self.transcripts = []
        self.audio_files = []
        self.recording_thread = None
        self.recognizer = sr.Recognizer() if AUDIO_AVAILABLE else None
        self.audio_available = AUDIO_AVAILABLE
        
        # Get project root data directory if not specified
        if recordings_dir is None:
            PROJECT_ROOT = Path(__file__).parent.parent.parent
            recordings_dir = PROJECT_ROOT / "data" / "recordings"
        self.recordings_dir = Path(recordings_dir)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        
        # Audio recording parameters
        self.chunk = 1024
        if AUDIO_AVAILABLE:
            self.format = pyaudio.paInt16
        else:
            self.format = None
        self.channels = 1
        self.rate = 44100
        self.frames = []
        self.audio_stream = None
        self.pyaudio_instance = None
        
    def start(self):
        """Start recording and transcribing audio"""
        if not self.audio_available:
            print("⚠️  Audio recording skipped (microphone not available)")
            return
            
        if self.is_recording:
            return
        
        self.is_recording = True
        self.transcripts = []
        self.audio_files = []
        self.frames = []
        
        # IMPORTANT: Start audio stream FIRST, then start recording thread
        # This ensures the stream exists when the thread tries to read from it
        if self.audio_available:
            self._start_audio_recording()
            
            # Only start recording thread if stream was successfully created
            if self.audio_stream and self.pyaudio_instance:
                self.recording_thread = threading.Thread(target=self._record_loop, daemon=True)
                self.recording_thread.start()
                print("🎤 Audio recording started")
            else:
                print("⚠️  Audio stream could not be created, recording thread not started")
                self.is_recording = False
        else:
            print("⚠️  Audio recording skipped (audio not available)")
    
    def _start_audio_recording(self):
        """Start recording audio to file"""
        try:
            print("🎤 Initializing PyAudio...")
            self.pyaudio_instance = pyaudio.PyAudio()
            
            # List available input devices for debugging
            print(f"🎤 Available audio input devices: {self.pyaudio_instance.get_device_count()}")
            
            # Try to get default input device
            try:
                default_device = self.pyaudio_instance.get_default_input_device_info()
                print(f"🎤 Default input device: {default_device['name']}")
            except:
                print("⚠️  Could not get default input device")
            
            print("🎤 Opening audio stream...")
            self.audio_stream = self.pyaudio_instance.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )
            
            # Start the stream
            self.audio_stream.start_stream()
            print("✅ Audio stream started successfully")
            
        except OSError as e:
            print(f"❌ Could not start audio stream (OSError): {e}")
            print("   This usually means:")
            print("   1. Microphone permission not granted")
            print("   2. PortAudio not installed (macOS: brew install portaudio)")
            print("   3. No microphone available")
            self.audio_available = False
            if self.pyaudio_instance:
                try:
                    self.pyaudio_instance.terminate()
                except:
                    pass
                self.pyaudio_instance = None
            self.audio_stream = None
        except Exception as e:
            print(f"❌ Could not start audio stream: {e}")
            import traceback
            traceback.print_exc()
            self.audio_available = False
            if self.pyaudio_instance:
                try:
                    self.pyaudio_instance.terminate()
                except:
                    pass
                self.pyaudio_instance = None
            self.audio_stream = None
    
    def stop(self):
        """Stop recording, save audio file, transcribe, and return transcripts"""
        if not self.is_recording:
            return []
        
        self.is_recording = False
        
        # Wait for recording thread to finish (but not too long - prioritize responsiveness)
        if self.recording_thread and self.recording_thread.is_alive():
            print("⏳ Waiting for audio recording thread to finish...")
            self.recording_thread.join(timeout=0.3)  # Reduced to 0.3s for faster response
            if self.recording_thread.is_alive():
                print("⚠️  Audio thread still running, but continuing to stop...")
        
        # Stop audio stream
        if self.audio_stream:
            try:
                if self.audio_stream.is_active():
                    self.audio_stream.stop_stream()
                self.audio_stream.close()
                print("✅ Audio stream stopped and closed")
            except Exception as e:
                print(f"⚠️  Error stopping audio stream: {e}")
        
        if self.pyaudio_instance:
            try:
                self.pyaudio_instance.terminate()
            except:
                pass
        
        # Save audio file and transcribe
        audio_file_path = None
        if self.frames and len(self.frames) > 0:
            try:
                audio_file_path = self._save_audio_file()
                if audio_file_path and os.path.exists(audio_file_path):
                    self.audio_files.append(audio_file_path)
                    print(f"💾 Audio file saved: {audio_file_path}")
                    # Transcribe the saved audio file
                    self._transcribe_audio_file(audio_file_path)
                else:
                    print(f"⚠️  Audio file was not saved properly")
            except Exception as e:
                print(f"❌ Error saving audio file: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️  No audio frames to save (frames: {len(self.frames) if self.frames else 0})")
        
        print(f"🎤 Audio recording stopped. Saved {len(self.audio_files)} file(s), {len(self.transcripts)} transcript(s)")
        if self.audio_files:
            print(f"   Audio files: {self.audio_files}")
        return self.transcripts.copy()
    
    def _save_audio_file(self) -> str:
        """Save recorded audio frames to WAV file"""
        if not self.frames or len(self.frames) == 0:
            print(f"⚠️  No frames to save")
            return None
        
        if not self.pyaudio_instance:
            print(f"⚠️  PyAudio instance not available")
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"recording_{timestamp}.wav"
            filepath = self.recordings_dir / filename
            
            # Ensure directory exists
            self.recordings_dir.mkdir(parents=True, exist_ok=True)
            
            # Get sample width
            sample_width = self.pyaudio_instance.get_sample_size(self.format)
            if not sample_width:
                sample_width = 2  # Default to 16-bit
            
            wf = wave.open(str(filepath), 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            
            # Verify file was created
            if filepath.exists() and filepath.stat().st_size > 0:
                print(f"💾 Saved audio file: {filename} ({filepath.stat().st_size} bytes)")
                return str(filepath)
            else:
                print(f"⚠️  Audio file was created but is empty or missing")
                return None
        except Exception as e:
            print(f"❌ Error saving audio file: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _transcribe_audio_file(self, audio_file_path: str):
        """Transcribe audio file using speech recognition"""
        if not self.recognizer or not audio_file_path:
            return
        
        try:
            with sr.AudioFile(audio_file_path) as source:
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Read the entire audio file
                audio = self.recognizer.record(source)
                
                # Try to recognize speech
                try:
                    text = self.recognizer.recognize_google(audio)
                    
                    if text:
                        transcript = {
                            "text": text,
                            "timestamp": datetime.now().isoformat(),
                            "audio_file": audio_file_path,
                        }
                        self.transcripts.append(transcript)
                        print(f"📝 Transcribed: {text[:50]}...")
                
                except sr.UnknownValueError:
                    print("⚠️  Could not understand audio")
                except sr.RequestError as e:
                    print(f"⚠️  Could not request transcription results; {e}")
        except Exception as e:
            print(f"❌ Error transcribing audio file: {e}")
    
    def _record_loop(self):
        """Main recording loop - records audio to buffer"""
        if not self.audio_available or not self.audio_stream:
            print("⚠️  Audio recording loop: stream not available")
            return
        
        if not self.audio_stream.is_active():
            print("⚠️  Audio stream is not active")
            return
        
        print("🎤 Recording audio to file...")
        frame_count = 0
        
        while self.is_recording:
            try:
                if self.audio_stream and self.audio_stream.is_active():
                    data = self.audio_stream.read(self.chunk, exception_on_overflow=False)
                    if data:
                        self.frames.append(data)
                        frame_count += 1
                        # Log progress every 100 frames (~2.3 seconds at 44100Hz)
                        if frame_count % 100 == 0:
                            print(f"🎤 Recording... ({frame_count} chunks, ~{frame_count * self.chunk / self.rate:.1f}s)")
                else:
                    print("⚠️  Audio stream became inactive")
                    break
            except Exception as e:
                print(f"❌ Error in audio recording loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.1)
                # Try to continue if stream is still active
                if not self.audio_stream or not self.audio_stream.is_active():
                    break
        
        print(f"🎤 Stopped recording audio ({len(self.frames)} chunks, ~{len(self.frames) * self.chunk / self.rate:.1f}s)")
    
    def get_transcripts(self):
        """Get all transcripts recorded so far"""
        return self.transcripts.copy()
    
    def get_audio_files(self):
        """Get all saved audio file paths"""
        return self.audio_files.copy()


