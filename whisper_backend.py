from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.popup import Popup
from kivy.uix.slider import Slider
from kivy.clock import Clock
import threading
import os
import subprocess
import time
import datetime

class WhisperApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_file = None
        self.last_output_dir = None
        self.is_recording = False
        self.recording_process = None
        self.recording_start_time = None
        self.recording_file_path = None
        self.last_srt_file = None  # Track the most recent SRT file for summarization
    
    def build(self):
        # Main layout - vertical
        main_layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        # Title
        title = Label(
            text='Whisper AI - Transcription with Live Output',
            size_hint=(1, 0.1),
            font_size='18sp',
            bold=True
        )
        main_layout.add_widget(title)
        
        # Button layout - horizontal (now with 4 buttons)
        button_layout = BoxLayout(orientation='horizontal', size_hint=(1, 0.15), spacing=8)
        
        # Record button
        self.record_btn = Button(
            text='🎤 Start Recording',
            background_color=(0.8, 0.2, 0.2, 1),  # Red color
            font_size='13sp'
        )
        self.record_btn.bind(on_press=self.toggle_recording)
        button_layout.add_widget(self.record_btn)
        
        # Transcribe button
        self.transcribe_btn = Button(
            text='📁 Select & Transcribe',
            background_color=(0.3, 0.7, 0.3, 1),  # Green color
            font_size='13sp'
        )
        self.transcribe_btn.bind(on_press=self.show_file_chooser)
        button_layout.add_widget(self.transcribe_btn)
        
        # Summarize button
        self.summarize_btn = Button(
            text='🤖 AI Summary',
            background_color=(0.9, 0.5, 0.1, 1),  # Orange color
            font_size='13sp',
            disabled=True  # Disabled until we have a transcript
        )
        self.summarize_btn.bind(on_press=self.show_summary_options)
        button_layout.add_widget(self.summarize_btn)
        
        # Open folder button
        self.open_dir_btn = Button(
            text='📂 Open Folder',
            background_color=(0.1, 0.6, 0.9, 1),  # Blue color
            font_size='13sp'
        )
        self.open_dir_btn.bind(on_press=self.open_output_directory)
        button_layout.add_widget(self.open_dir_btn)
        
        main_layout.add_widget(button_layout)
        
        # Recording status area
        self.recording_layout = BoxLayout(orientation='horizontal', size_hint=(1, 0.08), spacing=10)
        
        self.recording_status = Label(
            text='Ready to record',
            font_size='14sp',
            size_hint=(0.7, 1)
        )
        self.recording_layout.add_widget(self.recording_status)
        
        self.recording_timer = Label(
            text='00:00',
            font_size='16sp',
            bold=True,
            size_hint=(0.3, 1)
        )
        self.recording_layout.add_widget(self.recording_timer)
        
        main_layout.add_widget(self.recording_layout)
        
        # Terminal output area with scrollview
        scroll = ScrollView(size_hint=(1, 0.57))  # Adjusted for recording area
        self.terminal_output = TextInput(
            text='Whisper Transcription GUI - Ready!\nClick "Select Audio File & Transcribe" to begin.\nSupported formats: MP3, WAV, M4A, OGG\n' + '-' * 50 + '\n',
            multiline=True,
            readonly=True,
            background_color=(0, 0, 0, 1),  # Black background
            foreground_color=(1, 1, 1, 1),  # White text
            font_name='RobotoMono-Regular',  # Monospace font
            font_size='12sp'
        )
        scroll.add_widget(self.terminal_output)
        main_layout.add_widget(scroll)
        
        # Status label
        self.status_label = Label(
            text='Awaiting File Selection...',
            size_hint=(1, 0.1),
            font_size='14sp',
            text_size=(None, None)  # Allow text wrapping
        )
        main_layout.add_widget(self.status_label)
        
        return main_layout
    
    def show_file_chooser(self, instance):
        """Show file chooser popup"""
        # Create file chooser layout
        chooser_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        # File chooser widget
        filechooser = FileChooserIconView(
            filters=['*.mp3', '*.wav', '*.m4a', '*.ogg', '*.MP3', '*.WAV', '*.M4A', '*.OGG'],
            path=os.path.expanduser('~')  # Start in home directory
        )
        chooser_layout.add_widget(filechooser)
        
        # Button layout for popup
        popup_button_layout = BoxLayout(orientation='horizontal', size_hint=(1, 0.1), spacing=10)
        
        # Select button
        select_btn = Button(text='Select File', background_color=(0.3, 0.7, 0.3, 1))
        select_btn.bind(on_press=lambda x: self.select_file(filechooser.selection, popup))
        popup_button_layout.add_widget(select_btn)
        
        # Cancel button
        cancel_btn = Button(text='Cancel', background_color=(0.8, 0.3, 0.3, 1))
        cancel_btn.bind(on_press=lambda x: popup.dismiss())
        popup_button_layout.add_widget(cancel_btn)
        
        chooser_layout.add_widget(popup_button_layout)
        
        # Create and open popup
        popup = Popup(
            title='Select Audio File',
            content=chooser_layout,
            size_hint=(0.9, 0.9),
            auto_dismiss=False
        )
        popup.open()
    
    def select_file(self, selection, popup):
        """Handle file selection"""
        if not selection:
            self.add_terminal_text("No file selected.\n")
            return
        
        self.selected_file = selection[0]
        popup.dismiss()
        
        # Show selected file
        filename = os.path.basename(self.selected_file)
        self.add_terminal_text(f"Selected file: {filename}\n")
        self.add_terminal_text(f"Full path: {self.selected_file}\n")
        
        # Update status
        self.status_label.text = f"File selected: {filename}"
        
        # Start transcription
        self.start_transcription()
    
    def start_transcription(self):
        """Start the actual transcription process"""
        if not self.selected_file:
            self.add_terminal_text("No file selected for transcription.\n")
            return
        
        # Update UI
        self.status_label.text = "Processing... Please wait."
        self.add_terminal_text("Starting transcription...\n")
        self.add_terminal_text("-" * 50 + "\n")
        
        # For now, just simulate the process
        self.simulate_transcription()
    
    def simulate_transcription(self):
        """Real Whisper transcription process"""
        def run_transcription():
            import subprocess
            import sys
            import shutil
            
            try:
                # Check if whisper is available
                if not shutil.which("whisper"):
                    Clock.schedule_once(lambda dt: self.add_terminal_text("❌ Whisper command not found! Please install OpenAI Whisper.\n"), 0)
                    Clock.schedule_once(lambda dt: self.update_status("❌ Whisper not found! Install with: pip install openai-whisper"), 0)
                    return

                output_dir = os.path.dirname(self.selected_file)
                
                # Add debugging info
                Clock.schedule_once(lambda dt: self.add_terminal_text(f"Input file: {self.selected_file}\n"), 0)
                Clock.schedule_once(lambda dt: self.add_terminal_text(f"Output directory: {output_dir}\n"), 0)
                
                # Whisper command (same as your original)
                whisper_cmd = [
                    "whisper", self.selected_file, "--model", "large", "--output_format", "srt",
                    "--output_dir", output_dir, "--device", "cuda", "--verbose", "False"
                ]
                
                Clock.schedule_once(lambda dt: self.add_terminal_text(f"Command: {' '.join(whisper_cmd)}\n"), 0)
                Clock.schedule_once(lambda dt: self.add_terminal_text("-" * 50 + "\n"), 0)

                # Set up environment (same as your original)
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"
                env["PYTHONIOENCODING"] = "utf-8"
                
                if getattr(sys, 'frozen', False):
                    working_dir = os.path.dirname(sys.executable)
                else:
                    working_dir = os.getcwd()

                # Run Whisper process
                process = subprocess.Popen(
                    whisper_cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT,
                    text=True, 
                    bufsize=1, 
                    universal_newlines=True,
                    env=env,
                    cwd=working_dir,
                    shell=False,
                    encoding='utf-8',
                    errors='replace'
                )

                # Read output in real-time (same as your original)
                for line in process.stdout:
                    if line:
                        try:
                            clean_line = line.encode('utf-8', errors='replace').decode('utf-8')
                        except:
                            clean_line = line.replace('\u0101', 'a').replace('\u016b', 'u')
                        
                        Clock.schedule_once(lambda dt, text=clean_line: self.add_terminal_text(text), 0)

                process.wait()

                # Check for SRT file (same logic as your original)
                base_name = os.path.splitext(os.path.basename(self.selected_file))[0]
                srt_file = os.path.join(output_dir, f"{base_name}.srt")
                alternative_srt = os.path.splitext(self.selected_file)[0] + ".srt"
                
                Clock.schedule_once(lambda dt: self.add_terminal_text(f"\nLooking for SRT file at: {srt_file}\n"), 0)
                Clock.schedule_once(lambda dt: self.add_terminal_text(f"Alternative location: {alternative_srt}\n"), 0)

                if os.path.exists(srt_file):
                    Clock.schedule_once(lambda dt: self.update_status(f"✅ Transcription complete! SRT saved:\n{srt_file}"), 0)
                    Clock.schedule_once(lambda dt: self.add_terminal_text(f"✅ SRT file found: {srt_file}\n"), 0)
                    self.last_output_dir = output_dir
                    self.last_srt_file = srt_file  # Store for summarization
                    Clock.schedule_once(lambda dt: self.enable_summary_button(), 0)
                elif os.path.exists(alternative_srt):
                    Clock.schedule_once(lambda dt: self.update_status(f"✅ Transcription complete! SRT saved:\n{alternative_srt}"), 0)
                    Clock.schedule_once(lambda dt: self.add_terminal_text(f"✅ SRT file found: {alternative_srt}\n"), 0)
                    self.last_output_dir = output_dir
                    self.last_srt_file = alternative_srt  # Store for summarization
                    Clock.schedule_once(lambda dt: self.enable_summary_button(), 0)
                else:
                    # List files for debugging
                    Clock.schedule_once(lambda dt: self.add_terminal_text(f"\nFiles in output directory:\n"), 0)
                    try:
                        for file in os.listdir(output_dir):
                            Clock.schedule_once(lambda dt, f=file: self.add_terminal_text(f"  - {f}\n"), 0)
                    except Exception as e:
                        Clock.schedule_once(lambda dt: self.add_terminal_text(f"Error listing files: {e}\n"), 0)
                    
                    Clock.schedule_once(lambda dt: self.update_status("⚠ Transcription finished, but SRT file not found."), 0)
                    Clock.schedule_once(lambda dt: self.add_terminal_text("⚠ SRT file not found in expected locations.\n"), 0)

            except Exception as e:
                error_msg = f"Transcription failed: {str(e)}"
                Clock.schedule_once(lambda dt: self.update_status("❌ Error in transcription!"), 0)
                Clock.schedule_once(lambda dt: self.add_terminal_text(f"\n❌ Error: {error_msg}\n"), 0)
        
        # Run in background thread
        threading.Thread(target=run_transcription, daemon=True).start()
    
    def open_output_directory(self, instance):
        """Handle open directory button press"""
        if hasattr(self, 'last_output_dir') and self.last_output_dir:
            try:
                import platform
                system = platform.system()
                
                if system == "Windows":
                    os.startfile(self.last_output_dir)
                elif system == "Darwin":  # macOS
                    subprocess.run(["open", self.last_output_dir])
                elif system == "Linux":
                    subprocess.run(["xdg-open", self.last_output_dir])
                
                self.add_terminal_text(f"Opened directory: {self.last_output_dir}\n")
            except Exception as e:
                self.add_terminal_text(f"Could not open directory: {e}\n")
        elif self.selected_file:
            output_dir = os.path.dirname(self.selected_file)
            self.add_terminal_text(f"No transcription completed yet. Output would go to: {output_dir}\n")
        else:
            self.add_terminal_text("No file selected yet. Select a file first.\n")
    
    def add_terminal_text(self, text):
        """Add text to terminal output (thread-safe)"""
        Clock.schedule_once(lambda dt: self._add_text_ui(text), 0)
    
    def _add_text_ui(self, text):
        """Actually add text to UI (must run on main thread)"""
        self.terminal_output.text += text
        # Auto-scroll to bottom
        self.terminal_output.cursor = (len(self.terminal_output.text), 0)
    
    def update_status(self, text):
        """Update status label (thread-safe)"""
        self.status_label.text = text
    
    def toggle_recording(self, instance):
        """Start or stop recording"""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
    
    def start_recording(self):
        """Start microphone recording"""
        try:
            # Create recordings directory
            desktop = os.path.expanduser("~/Desktop")
            recordings_dir = os.path.join(desktop, "Audio_Recordings")
            os.makedirs(recordings_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.recording_file_path = os.path.join(recordings_dir, f"recording_{timestamp}.wav")
            
            # Check for ffmpeg (most reliable cross-platform solution)
            import shutil
            if not shutil.which("ffmpeg"):
                self.add_terminal_text("❌ FFmpeg not found! Please install FFmpeg for recording.\n")
                self.add_terminal_text("Download from: https://ffmpeg.org/download.html\n")
                return
            
            # First, try to get available audio devices
            try:
                self.add_terminal_text("🔍 Detecting audio devices...\n")
                device_process = subprocess.run([
                    "ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"
                ], capture_output=True, text=True, timeout=10)
                
                # Parse audio devices from stderr (FFmpeg outputs device list to stderr)
                audio_devices = []
                for line in device_process.stderr.split('\n'):
                    if '"' in line and '(audio)' in line:
                        # Extract device name between quotes
                        start = line.find('"') + 1
                        end = line.find('"', start)
                        if start > 0 and end > start:
                            device_name = line[start:end]
                            audio_devices.append(device_name)
                
                self.add_terminal_text(f"Found {len(audio_devices)} audio device(s)\n")
                for i, device in enumerate(audio_devices):
                    self.add_terminal_text(f"  {i+1}. {device}\n")
                
            except Exception as e:
                self.add_terminal_text(f"Could not detect devices: {e}\n")
                audio_devices = []
            
            # Try different audio input methods in order of preference
            recording_attempts = []
            
            if audio_devices:
                # Use the first detected microphone device
                for device in audio_devices:
                    if 'microphone' in device.lower() or 'mic' in device.lower():
                        recording_attempts.append({
                            'name': f'Detected microphone: {device}',
                            'cmd': [
                                "ffmpeg", "-f", "dshow", "-i", f"audio={device}",
                                "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y",
                                self.recording_file_path
                            ]
                        })
                        break
                
                # If no microphone found, try first audio device
                if not recording_attempts and audio_devices:
                    device = audio_devices[0]
                    recording_attempts.append({
                        'name': f'First audio device: {device}',
                        'cmd': [
                            "ffmpeg", "-f", "dshow", "-i", f"audio={device}",
                            "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y",
                            self.recording_file_path
                        ]
                    })
            
            # Fallback attempts
            recording_attempts.extend([
                {
                    'name': 'Default audio device',
                    'cmd': [
                        "ffmpeg", "-f", "dshow", "-i", "audio=default",
                        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y",
                        self.recording_file_path
                    ]
                },
                {
                    'name': 'System audio mapper',
                    'cmd': [
                        "ffmpeg", "-f", "dshow", "-i", "audio=@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}\\wave_{00000000-0000-0000-0000-000000000000}",
                        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y",
                        self.recording_file_path
                    ]
                },
                {
                    'name': 'DirectSound capture',
                    'cmd': [
                        "ffmpeg", "-f", "dshow", "-audio_device_number", "0", "-i", "audio=dummy",
                        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y",
                        self.recording_file_path
                    ]
                }
            ])
            
            # Try each recording method until one works
            for attempt in recording_attempts:
                try:
                    self.add_terminal_text(f"Trying: {attempt['name']}\n")
                    self.add_terminal_text(f"Command: {' '.join(attempt['cmd'])}\n")
                    
                    # Test the command briefly to see if it works
                    test_process = subprocess.Popen(
                        attempt['cmd'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    # Wait a moment to see if it starts successfully
                    time.sleep(2)
                    
                    if test_process.poll() is None:  # Process is still running
                        # Success! Use this command
                        self.recording_process = test_process
                        break
                    else:
                        # Process failed, try next method
                        test_process.terminate()
                        self.add_terminal_text("❌ This method failed, trying next...\n")
                        continue
                        
                except Exception as e:
                    self.add_terminal_text(f"❌ Error with {attempt['name']}: {e}\n")
                    continue
            
            if not self.recording_process or self.recording_process.poll() is not None:
                self.add_terminal_text("❌ All recording methods failed!\n")
                self.add_terminal_text("Possible solutions:\n")
                self.add_terminal_text("1. Check microphone permissions in Windows Settings\n")
                self.add_terminal_text("2. Make sure microphone is plugged in and working\n")
                self.add_terminal_text("3. Try running as administrator\n")
                return
            
            # Update UI - recording started successfully
            self.is_recording = True
            self.recording_start_time = time.time()
            self.record_btn.text = "⏹️ Stop Recording"
            self.record_btn.background_color = (0.5, 0.5, 0.5, 1)  # Gray when recording
            self.recording_status.text = "🔴 Recording in progress..."
            
            # Start timer update
            Clock.schedule_interval(self.update_recording_timer, 1.0)
            
            self.add_terminal_text("✅ Recording started successfully!\n")
            
        except Exception as e:
            self.add_terminal_text(f"❌ Failed to start recording: {e}\n")
            self.add_terminal_text("Make sure FFmpeg is installed and microphone permissions are granted.\n")
    
    def stop_recording(self):
        """Stop microphone recording"""
        try:
            if self.recording_process:
                # Terminate the recording process
                self.recording_process.terminate()
                
                # Wait a moment for graceful shutdown
                try:
                    self.recording_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.recording_process.kill()
                
                self.recording_process = None
            
            # Update UI
            self.is_recording = False
            Clock.unschedule(self.update_recording_timer)
            
            self.record_btn.text = "🎤 Start Recording"
            self.record_btn.background_color = (0.8, 0.2, 0.2, 1)  # Back to red
            self.recording_status.text = "Recording stopped"
            self.recording_timer.text = "00:00"
            
            # Check if file was created
            if self.recording_file_path and os.path.exists(self.recording_file_path):
                file_size = os.path.getsize(self.recording_file_path)
                self.add_terminal_text(f"✅ Recording saved: {self.recording_file_path}\n")
                self.add_terminal_text(f"File size: {file_size:,} bytes\n")
                
                # Ask if user wants to transcribe
                self.show_transcribe_recorded_popup()
            else:
                self.add_terminal_text("⚠️ Recording file not found. Recording may have failed.\n")
                
        except Exception as e:
            self.add_terminal_text(f"❌ Error stopping recording: {e}\n")
    
    def update_recording_timer(self, dt):
        """Update the recording timer display"""
        if self.recording_start_time:
            elapsed = time.time() - self.recording_start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            self.recording_timer.text = f"{minutes:02d}:{seconds:02d}"
        return True  # Continue scheduling
    
    def show_transcribe_recorded_popup(self):
        """Show popup asking if user wants to transcribe the recorded audio"""
        layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        message = Label(
            text=f"Recording complete!\n\nFile: {os.path.basename(self.recording_file_path)}\n\nWould you like to transcribe this recording now?",
            text_size=(400, None),
            halign='center'
        )
        layout.add_widget(message)
        
        button_layout = BoxLayout(orientation='horizontal', size_hint=(1, 0.3), spacing=10)
        
        yes_btn = Button(text='Yes, Transcribe Now', background_color=(0.3, 0.7, 0.3, 1))
        yes_btn.bind(on_press=lambda x: self.transcribe_recorded_file(popup))
        button_layout.add_widget(yes_btn)
        
        no_btn = Button(text='No, Maybe Later', background_color=(0.6, 0.6, 0.6, 1))
        no_btn.bind(on_press=lambda x: popup.dismiss())
        button_layout.add_widget(no_btn)
        
        layout.add_widget(button_layout)
        
        popup = Popup(
            title='Recording Complete',
            content=layout,
            size_hint=(0.8, 0.6),
            auto_dismiss=False
        )
        popup.open()
    
    def transcribe_recorded_file(self, popup):
        """Transcribe the recorded audio file"""
        popup.dismiss()
        
        if self.recording_file_path and os.path.exists(self.recording_file_path):
            self.selected_file = self.recording_file_path
            
            filename = os.path.basename(self.recording_file_path)
            self.add_terminal_text(f"\n📝 Starting transcription of recorded file: {filename}\n")
            self.status_label.text = f"Transcribing recorded file: {filename}"
            
            # Start transcription
            self.start_transcription()
        else:
            self.add_terminal_text("❌ Recorded file not found for transcription.\n")
    
    def enable_summary_button(self):
        """Enable the summary button after successful transcription"""
        self.summarize_btn.disabled = False
        self.add_terminal_text("🤖 AI Summary button is now available!\n")
    
    def show_summary_options(self, instance):
        """Show summary options popup"""
        if not self.last_srt_file or not os.path.exists(self.last_srt_file):
            self.add_terminal_text("❌ No SRT file found for summarization.\n")
            return
        
        layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        title = Label(
            text='AI Summary Options',
            font_size='18sp',
            bold=True,
            size_hint=(1, 0.2)
        )
        layout.add_widget(title)
        
        description = Label(
            text=f'Generate AI summary from:\n{os.path.basename(self.last_srt_file)}\n\nChoose summary type:',
            text_size=(400, None),
            halign='center',
            size_hint=(1, 0.3)
        )
        layout.add_widget(description)
        
        # Summary type buttons
        button_layout = BoxLayout(orientation='vertical', size_hint=(1, 0.5), spacing=10)
        
        # Meeting minutes button
        minutes_btn = Button(
            text='📋 Meeting Minutes\n(Structured with action items)',
            background_color=(0.2, 0.7, 0.9, 1),
            font_size='14sp'
        )
        minutes_btn.bind(on_press=lambda x: self.create_summary(popup, 'meeting_minutes'))
        button_layout.add_widget(minutes_btn)
        
        # Brief summary button
        summary_btn = Button(
            text='📝 Brief Summary\n(Key points and highlights)',
            background_color=(0.3, 0.8, 0.3, 1),
            font_size='14sp'
        )
        summary_btn.bind(on_press=lambda x: self.create_summary(popup, 'brief_summary'))
        button_layout.add_widget(summary_btn)
        
        # Detailed summary button
        detailed_btn = Button(
            text='📄 Detailed Summary\n(Comprehensive overview)',
            background_color=(0.9, 0.6, 0.2, 1),
            font_size='14sp'
        )
        detailed_btn.bind(on_press=lambda x: self.create_summary(popup, 'detailed_summary'))
        button_layout.add_widget(detailed_btn)
        
        # Cancel button
        cancel_btn = Button(
            text='Cancel',
            background_color=(0.6, 0.6, 0.6, 1),
            font_size='14sp',
            size_hint=(1, 0.8)
        )
        cancel_btn.bind(on_press=lambda x: popup.dismiss())
        button_layout.add_widget(cancel_btn)
        
        layout.add_widget(button_layout)
        
        popup = Popup(
            title='AI Summary',
            content=layout,
            size_hint=(0.85, 0.8),
            auto_dismiss=False
        )
        popup.open()
    
    def create_summary(self, popup, summary_type):
        """Create AI summary of the SRT file"""
        popup.dismiss()
        
        # Update UI
        self.status_label.text = "🤖 Generating AI summary... Please wait."
        self.add_terminal_text(f"\n🤖 Starting AI summary generation ({summary_type})...\n")
        self.add_terminal_text("-" * 50 + "\n")
        
        # Run summarization in background thread
        threading.Thread(target=self.run_summarization, args=(summary_type,), daemon=True).start()
    
    def run_summarization(self, summary_type):
        """Run the actual AI summarization"""
        try:
            # Read the SRT file
            Clock.schedule_once(lambda dt: self.add_terminal_text("📖 Reading transcript file...\n"), 0)
            
            with open(self.last_srt_file, 'r', encoding='utf-8') as f:
                srt_content = f.read()
            
            # Extract text from SRT (remove timestamps)
            transcript_text = self.extract_text_from_srt(srt_content)
            
            if not transcript_text.strip():
                Clock.schedule_once(lambda dt: self.add_terminal_text("❌ No text found in SRT file.\n"), 0)
                Clock.schedule_once(lambda dt: self.update_status("❌ Empty transcript file."), 0)
                return
            
            Clock.schedule_once(lambda dt: self.add_terminal_text(f"📊 Transcript length: {len(transcript_text)} characters\n"), 0)
            
            # Choose AI service and generate summary
            summary = self.generate_ai_summary(transcript_text, summary_type)
            
            if summary:
                # Save summary to file
                self.save_summary_file(summary, summary_type)
            else:
                Clock.schedule_once(lambda dt: self.add_terminal_text("❌ Failed to generate summary.\n"), 0)
                Clock.schedule_once(lambda dt: self.update_status("❌ Summary generation failed."), 0)
                
        except Exception as error:
            error_msg = f"Summary generation failed: {str(error)}"
            Clock.schedule_once(lambda dt: self.add_terminal_text(f"❌ Error: {error_msg}\n"), 0)
            Clock.schedule_once(lambda dt: self.update_status("❌ Summary generation error."), 0)
    
    def extract_text_from_srt(self, srt_content):
        """Extract clean text from SRT subtitle format"""
        lines = srt_content.strip().split('\n')
        text_lines = []
        
        for line in lines:
            # Skip sequence numbers and timestamps
            if line.isdigit() or '-->' in line or line.strip() == '':
                continue
            # Keep the actual subtitle text
            text_lines.append(line.strip())
        
        return ' '.join(text_lines)
    
    def generate_ai_summary(self, transcript_text, summary_type):
        """Generate AI summary using backend service or local methods"""
        try:
            Clock.schedule_once(lambda dt: self.add_terminal_text("🌐 Trying backend AI service...\n"), 0)
            
            # Try backend service first (for mobile compatibility)
            backend_summary = self.try_backend_service(transcript_text, summary_type)
            if backend_summary:
                return backend_summary
            
            # Fallback to local methods (desktop)
            Clock.schedule_once(lambda dt: self.add_terminal_text("🖥️ Backend unavailable, trying local methods...\n"), 0)
            
            # Try Groq API (if configured locally)
            summary = self.try_groq_summary(self.create_prompt(transcript_text, summary_type))
            if summary:
                return summary
            
            # Try Ollama (if available locally)
            summary = self.try_ollama_summary(self.create_prompt(transcript_text, summary_type))
            if summary:
                return summary
            
            # Try Hugging Face (if configured locally)
            summary = self.try_huggingface_summary(transcript_text, summary_type)
            if summary:
                return summary
            
            # Final fallback to simple analysis
            summary = self.create_simple_summary(transcript_text, summary_type)
            return summary
            
        except Exception as error:
            error_msg = f"AI summary error: {error}"
            Clock.schedule_once(lambda dt: self.add_terminal_text(f"❌ {error_msg}\n"), 0)
            return None
    
    def try_backend_service(self, transcript_text, summary_type):
        """Try the backend service for AI summary"""
        try:
            import requests
            
            # Your backend URL (you'll change this after deployment)
            backend_url = "https://your-backend-url.com/api/summarize"  # Update this!
            
            data = {
                "transcript": transcript_text,
                "summary_type": summary_type,
                "app_version": "1.0"
            }
            
            response = requests.post(
                backend_url,
                json=data,
                timeout=60,  # Allow time for AI processing
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                result = response.json()
                summary_text = result.get('summary', {})
                
                # Handle both old and new response formats
                if isinstance(summary_text, dict):
                    summary_text = summary_text.get('text', str(summary_text))
                
                service_used = result.get('service_used', 'backend')
                Clock.schedule_once(lambda dt: self.add_terminal_text(f"✅ Backend AI summary generated! (via {service_used})\n"), 0)
                return summary_text
            
            elif response.status_code == 429:
                Clock.schedule_once(lambda dt: self.add_terminal_text("⚠️ Rate limit exceeded. Try again in an hour.\n"), 0)
                return None
            else:
                Clock.schedule_once(lambda dt: self.add_terminal_text(f"⚠️ Backend error: {response.status_code}\n"), 0)
                return None
                
        except requests.exceptions.ConnectTimeout:
            Clock.schedule_once(lambda dt: self.add_terminal_text("⚠️ Backend timeout. Trying local methods...\n"), 0)
            return None
        except requests.exceptions.ConnectionError:
            Clock.schedule_once(lambda dt: self.add_terminal_text("⚠️ Backend unavailable. Trying local methods...\n"), 0)
            return None
        except Exception as error:
            Clock.schedule_once(lambda dt: self.add_terminal_text(f"⚠️ Backend service failed: {error}\n"), 0)
            return None
    
    def create_prompt(self, transcript_text, summary_type):
        """Create prompts for different summary types"""
        prompts = {
            'meeting_minutes': f"""Please create professional meeting minutes from this transcript. Include:

1. MEETING OVERVIEW (brief description)
2. KEY PARTICIPANTS (if identifiable)  
3. MAIN TOPICS DISCUSSED
4. DECISIONS MADE
5. ACTION ITEMS (who does what by when)
6. NEXT STEPS

Format as a clean, professional document suitable for sharing.

Transcript:
{transcript_text}""",

            'brief_summary': f"""Please create a brief, concise summary of this transcript. Focus on:

- Main topics discussed
- Key decisions or conclusions
- Important points raised
- Overall outcome

Keep it under 200 words and make it easy to scan quickly.

Transcript:
{transcript_text}""",

            'detailed_summary': f"""Please create a comprehensive summary of this transcript. Include:

- Detailed overview of all topics discussed
- Key arguments and perspectives presented
- Important details and context
- Decisions made and reasoning
- Notable quotes or insights
- Implications and follow-up items

Organize with clear headings and maintain important details.

Transcript:
{transcript_text}"""
        }
        
        return prompts.get(summary_type, prompts['brief_summary'])
    
    def try_openai_summary(self, prompt):
        """Try to use OpenAI API for summarization"""
        try:
            # Check if openai library is available
            import openai
            
            Clock.schedule_once(lambda dt: self.add_terminal_text("🔗 Trying OpenAI API...\n"), 0)
            
            # You would need to set your API key here
            # openai.api_key = "your-api-key-here"
            
            # For now, return None to indicate this method isn't set up
            Clock.schedule_once(lambda dt: self.add_terminal_text("⚠️ OpenAI API key not configured. Trying other methods...\n"), 0)
            return None
            
            # Uncomment this section when you have an API key:
            # response = openai.ChatCompletion.create(
            #     model="gpt-3.5-turbo",
            #     messages=[{"role": "user", "content": prompt}],
            #     max_tokens=1000,
            #     temperature=0.7
            # )
            # return response.choices[0].message.content
            
        except ImportError:
            Clock.schedule_once(lambda dt: self.add_terminal_text("⚠️ OpenAI library not installed. Trying other methods...\n"), 0)
            return None
        except Exception as error:
            error_msg = f"⚠️ OpenAI API failed: {error}. Trying other methods...\n"
            Clock.schedule_once(lambda dt: self.add_terminal_text(error_msg), 0)
            return None
    
    def try_groq_summary(self, prompt):
        """Try to use Groq API (free tier, very fast)"""
        try:
            import requests
            import json
            
            Clock.schedule_once(lambda dt: self.add_terminal_text("⚡ Trying Groq API (free & fast)...\n"), 0)
            
            # Check if Groq API key is set (you'll need to get this from https://console.groq.com)
            groq_api_key = None  # Set this to your Groq API key
            # groq_api_key = "gsk_your_api_key_here"  # Uncomment and add your key
            
            if not groq_api_key:
                Clock.schedule_once(lambda dt: self.add_terminal_text("⚠️ Groq API key not configured. Get free key at https://console.groq.com\n"), 0)
                return None
            
            headers = {
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "messages": [{"role": "user", "content": prompt}],
                "model": "llama-3.1-8b-instant",  # Free model
                "max_tokens": 1000,
                "temperature": 0.7
            }
            
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result["choices"][0]["message"]["content"]
                Clock.schedule_once(lambda dt: self.add_terminal_text("✅ Groq AI summary generated!\n"), 0)
                return summary
            else:
                Clock.schedule_once(lambda dt: self.add_terminal_text(f"⚠️ Groq API error: {response.status_code}\n"), 0)
                return None
                
        except ImportError:
            Clock.schedule_once(lambda dt: self.add_terminal_text("⚠️ Requests library needed for Groq. Install with: pip install requests\n"), 0)
            return None
        except Exception as error:
            Clock.schedule_once(lambda dt: self.add_terminal_text(f"⚠️ Groq API failed: {error}\n"), 0)
            return None
    
    def try_ollama_summary(self, prompt):
        """Try to use Ollama (completely free local AI)"""
        try:
            Clock.schedule_once(lambda dt: self.add_terminal_text("🖥️ Trying Ollama (local AI)...\n"), 0)
            
            # Check if ollama is available
            import subprocess
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                Clock.schedule_once(lambda dt: self.add_terminal_text("⚠️ Ollama not found. Install from https://ollama.ai\n"), 0)
                return None
            
            # Check for available models
            available_models = result.stdout
            
            # Try models in order of preference
            preferred_models = [
                "llama3.1:8b",
                "llama3.1",
                "qwen2.5:7b", 
                "mistral:7b",
                "llama3:8b",
                "llama2"
            ]
            
            model_to_use = None
            for model in preferred_models:
                if model in available_models:
                    model_to_use = model
                    break
            
            if not model_to_use:
                Clock.schedule_once(lambda dt: self.add_terminal_text("⚠️ No suitable Ollama models found. Try: ollama pull llama3.1:8b\n"), 0)
                return None
            
            Clock.schedule_once(lambda dt: self.add_terminal_text(f"✅ Using Ollama model: {model_to_use}\n"), 0)
            
            # Use ollama for local AI
            process = subprocess.run([
                "ollama", "run", model_to_use, prompt
            ], capture_output=True, text=True, timeout=180)  # 3 minute timeout
            
            if process.returncode == 0 and process.stdout.strip():
                Clock.schedule_once(lambda dt: self.add_terminal_text("✅ Ollama summary generated!\n"), 0)
                return process.stdout.strip()
            else:
                Clock.schedule_once(lambda dt: self.add_terminal_text(f"⚠️ Ollama failed. Error: {process.stderr}\n"), 0)
                return None
            
        except Exception as error:
            error_msg = f"⚠️ Ollama failed: {error}\n"
            Clock.schedule_once(lambda dt: self.add_terminal_text(error_msg), 0)
            return None
    
    def try_huggingface_summary(self, transcript_text, summary_type):
        """Try to use Hugging Face API (free tier)"""
        try:
            import requests
            import json
            
            Clock.schedule_once(lambda dt: self.add_terminal_text("🤗 Trying Hugging Face API (free)...\n"), 0)
            
            # Hugging Face API token (get from https://huggingface.co/settings/tokens)
            hf_token = None  # Set this to your HF token
            # hf_token = "hf_your_token_here"  # Uncomment and add your token
            
            if not hf_token:
                Clock.schedule_once(lambda dt: self.add_terminal_text("⚠️ Hugging Face token not configured. Get free token at https://huggingface.co\n"), 0)
                return None
            
            # Choose model based on summary type
            if summary_type == 'brief_summary':
                model = "facebook/bart-large-cnn"
            else:
                model = "google/pegasus-large"
            
            # Truncate text if too long (HF has input limits)
            max_length = 1000 if summary_type == 'brief_summary' else 2000
            text_to_summarize = transcript_text[:max_length]
            
            headers = {
                "Authorization": f"Bearer {hf_token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "inputs": text_to_summarize,
                "options": {"wait_for_model": True}
            }
            
            url = f"https://api-inference.huggingface.co/models/{model}"
            response = requests.post(url, headers=headers, json=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    summary = result[0].get("summary_text", "")
                    if summary:
                        Clock.schedule_once(lambda dt: self.add_terminal_text("✅ Hugging Face summary generated!\n"), 0)
                        return summary
            
            Clock.schedule_once(lambda dt: self.add_terminal_text(f"⚠️ Hugging Face API error: {response.status_code}\n"), 0)
            return None
            
        except ImportError:
            Clock.schedule_once(lambda dt: self.add_terminal_text("⚠️ Requests library needed for HF. Install with: pip install requests\n"), 0)
            return None
        except Exception as error:
            Clock.schedule_once(lambda dt: self.add_terminal_text(f"⚠️ Hugging Face failed: {error}\n"), 0)
            return None
    
    def create_simple_summary(self, transcript_text, summary_type):
        """Create a simple summary using text analysis (fallback method)"""
        Clock.schedule_once(lambda dt: self.add_terminal_text("📊 Creating summary using text analysis...\n"), 0)
        
        sentences = transcript_text.split('. ')
        word_count = len(transcript_text.split())
        
        if summary_type == 'meeting_minutes':
            summary = f"""MEETING SUMMARY
Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}

OVERVIEW:
This meeting transcript contains approximately {word_count} words across {len(sentences)} main points.

KEY TOPICS:
{self.extract_key_topics(transcript_text)}

TRANSCRIPT LENGTH: {len(transcript_text)} characters
ESTIMATED DURATION: {len(transcript_text) // 200} minutes (estimated based on text length)

NOTE: This is a basic text analysis. For detailed AI-powered summaries, 
configure OpenAI API or install a local AI model like Ollama."""

        elif summary_type == 'brief_summary':
            summary = f"""BRIEF SUMMARY

Word Count: {word_count} words
Key Points: {len(sentences)} main segments

{self.extract_key_topics(transcript_text)}

This transcript covers the main discussion points above. 
For detailed AI analysis, configure an AI service."""

        else:  # detailed_summary
            summary = f"""DETAILED TRANSCRIPT ANALYSIS

STATISTICS:
- Total words: {word_count:,}
- Text segments: {len(sentences)}
- Estimated speaking time: {word_count // 150} minutes
- Character count: {len(transcript_text):,}

CONTENT BREAKDOWN:
{self.extract_key_topics(transcript_text)}

FULL TRANSCRIPT PREVIEW:
{transcript_text[:500]}...

NOTE: This is a basic analysis. For AI-powered insights, 
set up OpenAI API or local AI model."""

        Clock.schedule_once(lambda dt: self.add_terminal_text("✅ Basic summary created!\n"), 0)
        return summary
    
    def extract_key_topics(self, text):
        """Extract key topics using simple keyword analysis"""
        import re
        from collections import Counter
        
        # Remove common stop words and extract meaningful words
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
        
        # Extract words (3+ characters, alphabetic)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        meaningful_words = [w for w in words if w not in stop_words]
        
        # Get most common words
        common_words = Counter(meaningful_words).most_common(10)
        
        topics = []
        for word, count in common_words:
            topics.append(f"• {word.title()} (mentioned {count} times)")
        
        return '\n'.join(topics) if topics else "• General discussion topics identified"
    
    def save_summary_file(self, summary, summary_type):
        """Save the summary to a file"""
        try:
            # Create filename
            base_name = os.path.splitext(os.path.basename(self.last_srt_file))[0]
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_filename = f"{base_name}_{summary_type}_{timestamp}.txt"
            summary_path = os.path.join(os.path.dirname(self.last_srt_file), summary_filename)
            
            # Save summary
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(summary)
            
            Clock.schedule_once(lambda dt: self.add_terminal_text(f"✅ Summary saved: {summary_filename}\n"), 0)
            Clock.schedule_once(lambda dt: self.update_status(f"✅ AI Summary complete! Saved:\n{summary_path}"), 0)
            
            # Show preview of summary
            preview = summary[:200] + "..." if len(summary) > 200 else summary
            Clock.schedule_once(lambda dt: self.add_terminal_text(f"\n📄 Summary Preview:\n{preview}\n"), 0)
            Clock.schedule_once(lambda dt: self.add_terminal_text("-" * 50 + "\n"), 0)
            
        except Exception as error:
            Clock.schedule_once(lambda dt: self.add_terminal_text(f"❌ Failed to save summary: {error}\n"), 0)

# Run the app
if __name__ == '__main__':
    WhisperApp().run()