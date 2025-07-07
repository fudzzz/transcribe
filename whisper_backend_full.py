from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import os
import time
import hashlib
import json
import subprocess
import tempfile
import shutil
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = '/tmp/whisper_uploads'
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB max file size
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'm4a', 'ogg', 'webm', 'flac'}

# Create upload directory
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Rate limiting (simple in-memory storage)
rate_limits = {}
RATE_LIMIT_REQUESTS = 5  # transcriptions per hour per IP
RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def rate_limit_check(ip_address):
    """Simple rate limiting for transcription requests"""
    current_time = time.time()
    
    # Clean old entries
    for ip in list(rate_limits.keys()):
        rate_limits[ip] = [req_time for req_time in rate_limits[ip] 
                          if current_time - req_time < RATE_LIMIT_WINDOW]
        if not rate_limits[ip]:
            del rate_limits[ip]
    
    # Check current IP
    if ip_address not in rate_limits:
        rate_limits[ip_address] = []
    
    if len(rate_limits[ip_address]) >= RATE_LIMIT_REQUESTS:
        return False
    
    rate_limits[ip_address].append(current_time)
    return True

def require_rate_limit(f):
    """Decorator for rate limiting"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if not rate_limit_check(ip):
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': f'Maximum {RATE_LIMIT_REQUESTS} transcriptions per hour allowed'
            }), 429
        return f(*args, **kwargs)
    return decorated_function

def cleanup_old_files():
    """Clean up old upload files (older than 1 hour)"""
    try:
        current_time = time.time()
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getctime(filepath)
                if file_age > 3600:  # 1 hour
                    os.remove(filepath)
    except Exception as e:
        print(f"Cleanup error: {e}")

@app.route('/')
def home():
    """Simple status page"""
    cleanup_old_files()  # Clean up old files
    
    status_page = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Whisper AI Backend</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            .status { color: green; }
            .error { color: red; }
            .endpoint { background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 5px; }
            .warning { color: orange; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🎤 Whisper AI Transcription Backend</h1>
        <p class="status">✅ Backend is running!</p>
        
        <h2>Available Endpoints:</h2>
        <div class="endpoint">
            <strong>POST /api/transcribe</strong><br>
            Upload audio file for Whisper transcription<br>
            <em>Supports: MP3, WAV, M4A, OGG, WebM, FLAC (max 50MB)</em>
        </div>
        <div class="endpoint">
            <strong>POST /api/summarize</strong><br>
            Generate AI summary from transcript text
        </div>
        <div class="endpoint">
            <strong>GET /api/status</strong><br>
            Check service status and available features
        </div>
        
        <h2>Rate Limits:</h2>
        <p>• {{ rate_limit }} transcriptions per hour per IP address</p>
        <p>• Summary requests: 10 per hour per IP</p>
        
        <h2>File Upload:</h2>
        <p>• Maximum file size: 50MB</p>
        <p>• Supported formats: MP3, WAV, M4A, OGG, WebM, FLAC</p>
        <p>• Files are automatically deleted after 1 hour</p>
        
        <div class="warning">
        <h2>⚠️ Whisper Status:</h2>
        <p>{{ whisper_status }}</p>
        </div>
        
        <p><em>Last updated: {{ timestamp }}</em></p>
    </body>
    </html>
    """
    
    # Check if Whisper is available
    whisper_available = shutil.which("whisper") is not None
    whisper_status = "✅ Whisper CLI is installed and ready" if whisper_available else "❌ Whisper CLI not installed. Install with: pip install openai-whisper"
    
    return render_template_string(status_page, 
                                rate_limit=RATE_LIMIT_REQUESTS,
                                whisper_status=whisper_status,
                                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'))

@app.route('/api/status')
def api_status():
    """API status endpoint"""
    whisper_available = shutil.which("whisper") is not None
    
    return jsonify({
        'status': 'online',
        'timestamp': datetime.utcnow().isoformat(),
        'features': {
            'transcription': whisper_available,
            'summarization': True,
            'file_upload': True
        },
        'limits': {
            'max_file_size_mb': MAX_FILE_SIZE // (1024 * 1024),
            'transcriptions_per_hour': RATE_LIMIT_REQUESTS,
            'supported_formats': list(ALLOWED_EXTENSIONS)
        },
        'whisper_available': whisper_available
    })

@app.route('/api/transcribe', methods=['POST'])
@require_rate_limit
def transcribe_audio():
    """Main transcription endpoint - accepts audio file uploads"""
    try:
        cleanup_old_files()  # Clean up before processing
        
        # Check if Whisper is available
        if not shutil.which("whisper"):
            return jsonify({
                'error': 'Whisper not available',
                'message': 'OpenAI Whisper is not installed on this server'
            }), 503
        
        # Validate request
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        file = request.files['audio']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'error': 'Invalid file type',
                'message': f'Supported formats: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                'error': 'File too large',
                'message': f'Maximum file size: {MAX_FILE_SIZE // (1024 * 1024)}MB'
            }), 413
        
        # Get options from request
        model = request.form.get('model', 'base')  # base, small, medium, large
        output_format = request.form.get('output_format', 'srt')
        language = request.form.get('language', 'auto')  # auto-detect or specific language
        
        # Validate model choice
        valid_models = ['tiny', 'base', 'small', 'medium', 'large']
        if model not in valid_models:
            model = 'base'
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(filepath)
        
        print(f"Processing file: {unique_filename}, size: {file_size} bytes, model: {model}")
        
        # Run Whisper transcription
        result = run_whisper_transcription(filepath, model, output_format, language)
        
        # Clean up uploaded file
        try:
            os.remove(filepath)
        except:
            pass
        
        if result['success']:
            return jsonify({
                'success': True,
                'transcript': result['transcript'],
                'srt_content': result['srt_content'],
                'filename': filename,
                'model_used': model,
                'language_detected': result.get('language', 'unknown'),
                'processing_time': result.get('processing_time', 0),
                'timestamp': datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                'error': 'Transcription failed',
                'message': result['error']
            }), 500
            
    except Exception as e:
        print(f"Transcription error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

def run_whisper_transcription(filepath, model, output_format, language):
    """Run Whisper transcription on uploaded file"""
    try:
        start_time = time.time()
        
        # Create temporary output directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Build Whisper command
            cmd = [
                "whisper", filepath,
                "--model", model,
                "--output_format", output_format,
                "--output_dir", temp_dir,
                "--verbose", "False"
            ]
            
            # Add language if specified
            if language != 'auto':
                cmd.extend(["--language", language])
            
            print(f"Running Whisper command: {' '.join(cmd)}")
            
            # Run Whisper
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                encoding='utf-8',
                errors='replace'
            )
            
            if process.returncode != 0:
                return {
                    'success': False,
                    'error': f"Whisper failed: {process.stderr}"
                }
            
            # Find output files
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            srt_file = os.path.join(temp_dir, f"{base_name}.srt")
            txt_file = os.path.join(temp_dir, f"{base_name}.txt")
            
            # Read SRT content
            srt_content = ""
            if os.path.exists(srt_file):
                with open(srt_file, 'r', encoding='utf-8') as f:
                    srt_content = f.read()
            
            # Read plain text transcript
            transcript = ""
            if os.path.exists(txt_file):
                with open(txt_file, 'r', encoding='utf-8') as f:
                    transcript = f.read()
            elif srt_content:
                # Extract text from SRT if no txt file
                transcript = extract_text_from_srt(srt_content)
            
            processing_time = time.time() - start_time
            
            return {
                'success': True,
                'transcript': transcript,
                'srt_content': srt_content,
                'processing_time': processing_time,
                'language': 'auto-detected'  # Whisper output doesn't easily give us detected language
            }
            
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Transcription timeout (maximum 5 minutes)'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Processing error: {str(e)}"
        }

def extract_text_from_srt(srt_content):
    """Extract plain text from SRT subtitle format"""
    lines = srt_content.strip().split('\n')
    text_lines = []
    
    for line in lines:
        # Skip sequence numbers and timestamps
        if line.isdigit() or '-->' in line or line.strip() == '':
            continue
        # Keep the actual subtitle text
        text_lines.append(line.strip())
    
    return ' '.join(text_lines)

# Keep the existing summarization endpoint from before
@app.route('/api/summarize', methods=['POST'])
@require_rate_limit
def summarize_transcript():
    """Summary endpoint (from previous version)"""
    try:
        if not request.json:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        transcript = request.json.get('transcript', '').strip()
        summary_type = request.json.get('summary_type', 'brief_summary')
        
        if not transcript:
            return jsonify({'error': 'No transcript text provided'}), 400
        
        if len(transcript) < 50:
            return jsonify({'error': 'Transcript too short (minimum 50 characters)'}), 400
        
        # Simple summary for now
        word_count = len(transcript.split())
        summary = f"""SUMMARY ({summary_type})
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Word Count: {word_count} words
Estimated Duration: {word_count // 150} minutes

This transcript discusses the main topics mentioned throughout the conversation. 
For detailed AI-powered summaries, configure an AI service API key.

Key Statistics:
• Total words: {word_count:,}
• Character count: {len(transcript):,}
• Estimated reading time: {word_count // 200} minutes

Note: This is a basic analysis. For advanced AI summaries with insights and action items, 
add an AI service API key to the backend configuration."""
        
        return jsonify({
            'summary': summary,
            'summary_type': summary_type,
            'transcript_length': len(transcript),
            'timestamp': datetime.utcnow().isoformat(),
            'service_used': 'basic_analysis'
        })
        
    except Exception as e:
        print(f"Error in summarize_transcript: {e}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("🚀 Starting Whisper AI Backend...")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Max file size: {MAX_FILE_SIZE // (1024 * 1024)}MB")
    print(f"Supported formats: {ALLOWED_EXTENSIONS}")
    print(f"Whisper available: {shutil.which('whisper') is not None}")
    
    app.run(host='0.0.0.0', port=port, debug=False)