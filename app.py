import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

# Process status tracking
PROCESS_STATUS = {
    'current_step': None,
    'client_id': None,
    'client_name': None,
    'project_id': None,
    'start_time': None,
    'logs': [],
    'errors': [],
    'is_processing': False,
    'vtt_file': None,
    'mp4_file': None
}

def log_message(message, is_error=False):
    """Add a message to the logs with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    PROCESS_STATUS['logs'].append(log_entry)
    
    if is_error:
        PROCESS_STATUS['errors'].append(log_entry)
        print(f"ERROR: {log_entry}")
    else:
        print(log_entry)

def get_clients_from_supabase():
    """Fetch client list from Supabase"""
    try:
        # This is a simplified version for demo purposes
        if not SUPABASE_URL or not SUPABASE_KEY:
            log_message("Supabase credentials not configured", is_error=True)
            return []
            
        # For demonstration purposes, returning dummy data
        # In production, you would make an actual API call to Supabase
        return [
            {"id": "client1", "name": "Demo Client 1"},
            {"id": "client2", "name": "Demo Client 2"},
            {"id": "annie", "name": "Annie"},
        ]
    except Exception as e:
        log_message(f"Error fetching clients: {str(e)}", is_error=True)
        return []

def simulate_processing():
    """Simulate processing for demo purposes"""
    PROCESS_STATUS['is_processing'] = True
    PROCESS_STATUS['current_step'] = 'app1'
    log_message(f"Starting App 1 processing for client {PROCESS_STATUS['client_id']}")
    log_message("App 1 processing complete")
    
    PROCESS_STATUS['current_step'] = 'app2'
    log_message(f"Starting App 2 processing for client {PROCESS_STATUS['client_id']}")
    log_message("App 2 processing complete")
    
    PROCESS_STATUS['current_step'] = 'app3'
    log_message(f"Starting App 3 processing for client {PROCESS_STATUS['client_id']}")
    log_message("App 3 processing complete")
    
    log_message("Entire workflow completed successfully!")
    PROCESS_STATUS['is_processing'] = False
    return True

# Routes
@app.route('/')
def index():
    """Display the upload form"""
    clients = get_clients_from_supabase()
    return render_template('index.html', clients=clients, status=PROCESS_STATUS)

@app.route('/upload', methods=['POST'])
def upload():
    """Handle file upload and simulate processing"""
    if PROCESS_STATUS['is_processing']:
        flash('A process is already running. Please wait for it to complete.')
        return redirect(url_for('status'))
        
    client_id = request.form.get('client_id')
    
    if not client_id:
        flash('Missing required fields')
        return redirect(url_for('index'))
    
    # In a serverless environment, we would store files in cloud storage
    # and trigger processing via webhooks or queues
    PROCESS_STATUS['client_id'] = client_id
    PROCESS_STATUS['start_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Clear previous logs
    PROCESS_STATUS['logs'] = []
    PROCESS_STATUS['errors'] = []
    
    # Simulate processing for demo
    if 'vtt_file' in request.files:
        vtt_file = request.files['vtt_file']
        if vtt_file.filename:
            PROCESS_STATUS['vtt_file'] = vtt_file.filename
            
    if 'mp4_file' in request.files:
        mp4_file = request.files['mp4_file']
        if mp4_file and mp4_file.filename:
            PROCESS_STATUS['mp4_file'] = mp4_file.filename
    
    # Note: In a real serverless app, we would upload files to cloud storage
    # and use webhooks or queues to trigger processing
    
    # For the demo, simulate processing
    simulate_processing()
    
    return redirect(url_for('status'))

@app.route('/status')
def status():
    """Display current processing status"""
    return render_template('status.html', status=PROCESS_STATUS)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
