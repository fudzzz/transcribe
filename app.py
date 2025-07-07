import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return "🎤 Whisper AI Backend is running!"

@app.route('/api/status')
def status():
    return jsonify({
        'status': 'online',
        'message': 'Backend is working!'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
