import os
import subprocess
import time
import shutil
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Application paths
APP_PATHS = {
    'app1': os.path.abspath(r'C:\Users\digit\CascadeProjects\self-cast-studio-app-1'),
    'app2': os.path.abspath(r'C:\Users\digit\CascadeProjects\style_profiler App2'),
    'app3': os.path.abspath(r'C:\Users\digit\CascadeProjects\App 3 Content Generator Suite')
}

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

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
    'mp4_file': None,
    'app1_output_dir': None,
    'app2_output_dir': None,
    'app3_output_dir': None
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
        # This is a simplified version - in production, use the Supabase client
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

def run_app1(vtt_file_path, client_id):
    """Run App 1 (Self-Cast Studio)"""
    try:
        PROCESS_STATUS['current_step'] = 'app1'
        log_message(f"Starting App 1 processing for client {client_id}")
        
        # Copy VTT file to App 1 input directory
        app1_input_dir = os.path.join(APP_PATHS['app1'], 'input')
        vtt_filename = os.path.basename(vtt_file_path)
        app1_vtt_path = os.path.join(app1_input_dir, vtt_filename)
        
        shutil.copy2(vtt_file_path, app1_vtt_path)
        log_message(f"Copied VTT file to App 1: {app1_vtt_path}")
        
        # Run App 1
        os.chdir(APP_PATHS['app1'])
        log_message("Running App 1 process_interview.py")
        
        # In production, you would use subprocess.Popen to run without blocking
        # For this example, we're simplifying
        process = subprocess.run(
            ['python', 'process_interview.py', app1_vtt_path],
            capture_output=True, 
            text=True
        )
        
        if process.returncode != 0:
            log_message(f"App 1 processing failed: {process.stderr}", is_error=True)
            return False
        
        # Find the output directory - usually the most recently created directory with today's date
        output_dir = os.path.join(APP_PATHS['app1'], 'output')
        today_str = datetime.now().strftime("%Y%m%d")
        
        # Find most recent directory with today's date
        dirs = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d)) and d.startswith(today_str)]
        if not dirs:
            log_message("No output directory found for App 1", is_error=True)
            return False
            
        dirs.sort(reverse=True)
        app1_output_dir = os.path.join(output_dir, dirs[0])
        PROCESS_STATUS['app1_output_dir'] = app1_output_dir
        
        log_message(f"App 1 processing complete. Output directory: {app1_output_dir}")
        return True
        
    except Exception as e:
        log_message(f"Error in App 1 processing: {str(e)}", is_error=True)
        return False

def run_app2(app1_output_dir, client_id):
    """Run App 2 (Style Profiler)"""
    try:
        PROCESS_STATUS['current_step'] = 'app2'
        log_message(f"Starting App 2 processing for client {client_id}")
        
        # Copy output from App 1 to App 2 input directory
        app2_input_dir = os.path.join(APP_PATHS['app2'], 'input')
        
        # Create client directory in App 2 input if it doesn't exist
        client_input_dir = os.path.join(app2_input_dir, client_id)
        os.makedirs(client_input_dir, exist_ok=True)
        
        # Copy transcript chunks from App 1 output to App 2 input
        transcript_file = os.path.join(app1_output_dir, 'transcript_chunks.md')
        if not os.path.exists(transcript_file):
            log_message(f"Transcript file not found: {transcript_file}", is_error=True)
            return False
            
        app2_transcript_path = os.path.join(client_input_dir, 'transcript_chunks.md')
        shutil.copy2(transcript_file, app2_transcript_path)
        log_message(f"Copied transcript to App 2: {app2_transcript_path}")
        
        # Run App 2
        os.chdir(APP_PATHS['app2'])
        log_message("Running App 2 style profiler")
        
        # In production, you would use subprocess.Popen to run without blocking
        process = subprocess.run(
            ['python', 'profile_generator.py', '--client_id', client_id],
            capture_output=True, 
            text=True
        )
        
        if process.returncode != 0:
            log_message(f"App 2 processing failed: {process.stderr}", is_error=True)
            return False
        
        # Find the output directory
        app2_output_dir = os.path.join(APP_PATHS['app2'], 'output', client_id)
        if not os.path.exists(app2_output_dir):
            log_message(f"App 2 output directory not found: {app2_output_dir}", is_error=True)
            return False
            
        PROCESS_STATUS['app2_output_dir'] = app2_output_dir
        log_message(f"App 2 processing complete. Output directory: {app2_output_dir}")
        return True
        
    except Exception as e:
        log_message(f"Error in App 2 processing: {str(e)}", is_error=True)
        return False

def run_app3(client_id):
    """Run App 3 (Content Generator)"""
    try:
        PROCESS_STATUS['current_step'] = 'app3'
        log_message(f"Starting App 3 processing for client {client_id}")
        
        # App 3 accesses the files directly from Supabase, so we don't need to copy files
        # We just need to run the enhanced content generator
        
        # Change to App 3 directory
        os.chdir(APP_PATHS['app3'])
        
        # Run App 3 enhanced content generator
        log_message("Running App 3 enhanced content generator")
        
        # In production, provide the actual Supabase key securely
        supabase_key = SUPABASE_KEY or "dummy_key_for_testing"
        
        # Run the enhanced content generator
        process = subprocess.run(
            ['python', 'content_generator/content_generator.py', 
             '--use_enhanced', 
             '--client_id', client_id,
             '--supabase_key', supabase_key],
            capture_output=True, 
            text=True
        )
        
        if process.returncode != 0:
            log_message(f"App 3 processing failed: {process.stderr}", is_error=True)
            return False
        
        log_message(f"App 3 processing complete. Content generated for client {client_id}")
        return True
        
    except Exception as e:
        log_message(f"Error in App 3 processing: {str(e)}", is_error=True)
        return False

def process_workflow(vtt_file, mp4_file, client_id):
    """Process the complete workflow from App 1 through App 3"""
    try:
        PROCESS_STATUS['is_processing'] = True
        PROCESS_STATUS['start_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        PROCESS_STATUS['client_id'] = client_id
        PROCESS_STATUS['vtt_file'] = os.path.basename(vtt_file)
        PROCESS_STATUS['mp4_file'] = os.path.basename(mp4_file) if mp4_file else None
        
        # Clear previous logs
        PROCESS_STATUS['logs'] = []
        PROCESS_STATUS['errors'] = []
        
        log_message(f"Starting workflow for client {client_id}")
        
        # Run App 1
        if not run_app1(vtt_file, client_id):
            log_message("Workflow stopped due to App 1 failure", is_error=True)
            PROCESS_STATUS['is_processing'] = False
            return False
            
        # Run App 2
        if not run_app2(PROCESS_STATUS['app1_output_dir'], client_id):
            log_message("Workflow stopped due to App 2 failure", is_error=True)
            PROCESS_STATUS['is_processing'] = False
            return False
            
        # Run App 3
        if not run_app3(client_id):
            log_message("Workflow stopped due to App 3 failure", is_error=True)
            PROCESS_STATUS['is_processing'] = False
            return False
            
        log_message("Entire workflow completed successfully!")
        PROCESS_STATUS['is_processing'] = False
        return True
        
    except Exception as e:
        log_message(f"Error in workflow processing: {str(e)}", is_error=True)
        PROCESS_STATUS['is_processing'] = False
        return False

# Routes
@app.route('/')
def index():
    """Display the upload form"""
    clients = get_clients_from_supabase()
    return render_template('index.html', clients=clients)

@app.route('/upload', methods=['POST'])
def upload():
    """Handle file upload and start processing"""
    if PROCESS_STATUS['is_processing']:
        flash('A process is already running. Please wait for it to complete.')
        return redirect(url_for('status'))
        
    if 'vtt_file' not in request.files:
        flash('No VTT file selected')
        return redirect(url_for('index'))
        
    vtt_file = request.files['vtt_file']
    mp4_file = request.files.get('mp4_file')
    client_id = request.form.get('client_id')
    
    if not vtt_file.filename or not client_id:
        flash('Missing required fields')
        return redirect(url_for('index'))
        
    # Save uploaded files
    upload_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    
    vtt_path = os.path.join(upload_dir, vtt_file.filename)
    vtt_file.save(vtt_path)
    
    mp4_path = None
    if mp4_file and mp4_file.filename:
        mp4_path = os.path.join(upload_dir, mp4_file.filename)
        mp4_file.save(mp4_path)
    
    # Start workflow processing in a separate thread
    # In a production app, you'd use a proper task queue like Celery
    # For simplicity, we're just starting the process directly
    # This will block the web server until completion!
    process_workflow(vtt_path, mp4_path, client_id)
    
    return redirect(url_for('status'))

@app.route('/status')
def status():
    """Display current processing status"""
    return render_template('status.html', status=PROCESS_STATUS)

if __name__ == '__main__':
    # Create uploads directory
    os.makedirs(os.path.join(os.path.dirname(__file__), 'uploads'), exist_ok=True)
    
    # Create templates directory if it doesn't exist
    os.makedirs(os.path.join(os.path.dirname(__file__), 'templates'), exist_ok=True)
    
    app.run(debug=True, port=5000)
