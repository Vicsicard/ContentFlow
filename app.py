import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import requests
from dotenv import load_dotenv
import uuid
import traceback

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

def get_supabase_client():
    """Get a simple wrapper for Supabase API calls"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    return {"url": SUPABASE_URL, "headers": headers}

def get_clients_from_supabase():
    """Fetch client list from Supabase"""
    try:
        supabase = get_supabase_client()
        
        if not supabase["url"] or not supabase["headers"]["apikey"]:
            return []
            
        response = requests.get(
            f"{supabase['url']}/rest/v1/user_projects?select=id,name",
            headers=supabase["headers"]
        )
        
        if response.status_code == 200:
            return response.json()
        
        # Fallback to demo data if API fails
        print(f"Error fetching clients: {response.status_code} {response.text}")
        return [
            {"id": "client1", "name": "Demo Client 1"},
            {"id": "client2", "name": "Demo Client 2"},
            {"id": "annie", "name": "Annie"},
        ]
    except Exception as e:
        print(f"Error fetching clients: {str(e)}")
        # Return demo data on error
        return [
            {"id": "client1", "name": "Demo Client 1"},
            {"id": "client2", "name": "Demo Client 2"},
            {"id": "annie", "name": "Annie"},
        ]

def create_job(client_id, vtt_filename):
    """Create a new job in Supabase"""
    try:
        supabase = get_supabase_client()
        
        job_data = {
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "status": "pending",
            "vtt_filename": vtt_filename,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
        
        response = requests.post(
            f"{supabase['url']}/rest/v1/processing_jobs",
            headers=supabase["headers"],
            json=job_data
        )
        
        if response.status_code == 201:
            return job_data["id"]
        else:
            print(f"Error creating job: {response.status_code} {response.text}")
            return None
    except Exception as e:
        print(f"Error creating job: {str(e)}")
        return None

def get_jobs():
    """Get all jobs from Supabase"""
    try:
        supabase = get_supabase_client()
        
        response = requests.get(
            f"{supabase['url']}/rest/v1/processing_jobs?order=created_at.desc",
            headers=supabase["headers"]
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching jobs: {response.status_code} {response.text}")
            return []
    except Exception as e:
        print(f"Error fetching jobs: {str(e)}")
        return []

def upload_file_to_supabase(file_content, filename, bucket_name="input-files"):
    """Upload a file to Supabase Storage"""
    try:
        print(f"DEBUG: Uploading file to Supabase: {filename}")
        supabase = get_supabase_client()
        
        # Storage API has a different endpoint
        storage_url = f"{supabase['url']}/storage/v1/object/{bucket_name}/{filename}"
        
        # Custom headers for storage
        headers = supabase["headers"].copy()
        headers["Content-Type"] = "application/octet-stream"
        
        print("DEBUG: Preparing upload request")
        
        response = requests.post(
            storage_url,
            headers=headers,
            data=file_content
        )
        
        print(f"DEBUG: Upload response status: {response.status_code}")
        print(f"DEBUG: Upload response text: {response.text}")
        
        if response.status_code == 200:
            print("DEBUG: File upload to Supabase successful")
            return True
        else:
            print(f"DEBUG ERROR: File upload failed - Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"DEBUG EXCEPTION in upload_file_to_supabase: {str(e)}")
        print(f"DEBUG EXCEPTION TRACEBACK: {traceback.format_exc()}")
        return False

def create_new_client(client_name):
    """Create a new client in the database with detailed error logging"""
    try:
        print(f"DEBUG: Creating new client: {client_name}")
        supabase = get_supabase_client()
        
        # Insert the new client
        print("DEBUG: Sending request to Supabase to create client")
        response = requests.post(
            f"{supabase['url']}/rest/v1/clients",
            headers=supabase["headers"],
            json={"name": client_name}
        )
        
        print(f"DEBUG: Supabase response status: {response.status_code}")
        print(f"DEBUG: Supabase response text: {response.text}")
        
        if response.status_code == 201:
            # Get the ID of the newly created client
            client_data = response.json()
            client_id = client_data[0]['id'] if client_data else None
            print(f"DEBUG: New client created with ID: {client_id}")
            return client_id
        else:
            print(f"DEBUG ERROR: Failed to create client - Status: {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        print(f"DEBUG EXCEPTION in create_new_client: {str(e)}")
        print(f"DEBUG EXCEPTION TRACEBACK: {traceback.format_exc()}")
        return None

def process_upload(client_id, vtt_file):
    """Process the upload with detailed error logging"""
    try:
        print(f"DEBUG: Processing upload for client: {client_id}")
        
        # Upload VTT file to Supabase
        print("DEBUG: Reading file content")
        file_content = vtt_file.read()
        filename = f"{client_id}/{vtt_file.filename}"
        print(f"DEBUG: Target filename in Supabase: {filename}")
        
        print("DEBUG: Uploading file to Supabase")
        upload_success = upload_file_to_supabase(file_content, filename)
        print(f"DEBUG: Upload result: {upload_success}")
        
        if upload_success:
            # Create job
            print("DEBUG: Creating job record")
            job_id = create_job(client_id, vtt_file.filename)
            print(f"DEBUG: Job created with ID: {job_id}")
            
            if job_id:
                return True, 'File uploaded and job created successfully'
            else:
                return False, 'File uploaded but job creation failed'
        else:
            return False, 'File upload to Supabase failed'
    except Exception as e:
        error_msg = f"Error in process_upload: {str(e)}"
        print(f"DEBUG EXCEPTION: {error_msg}")
        print(f"DEBUG EXCEPTION TRACEBACK: {traceback.format_exc()}")
        return False, error_msg

# Routes
@app.route('/', methods=['GET'])
def index():
    """Display the upload form"""
    clients = get_clients_from_supabase()
    return render_template('index.html', clients=clients)

@app.route('/upload', methods=['POST'])
def upload():
    """Handle file upload and job creation with detailed error logging"""
    try:
        print("DEBUG: Upload function started")
        print(f"DEBUG: Form data: {request.form}")
        print(f"DEBUG: Files: {request.files}")
        
        client_id = request.form.get('client_id')
        print(f"DEBUG: Client ID: {client_id}")
        
        # Handle new client creation
        if client_id == 'new':
            print("DEBUG: Creating new client")
            new_client_name = request.form.get('newClientName')
            print(f"DEBUG: New client name: {new_client_name}")
            
            if not new_client_name or new_client_name.strip() == '':
                error_msg = "Please enter a name for the new client"
                print(f"DEBUG ERROR: {error_msg}")
                return render_template('index.html', 
                                     clients=get_clients_from_supabase(), 
                                     error=error_msg)
                
            # Create new client in database
            client_id = create_new_client(new_client_name)
            print(f"DEBUG: New client created with ID: {client_id}")
            
            if not client_id:
                error_msg = "Failed to create new client in Supabase"
                print(f"DEBUG ERROR: {error_msg}")
                return render_template('index.html', 
                                     clients=get_clients_from_supabase(), 
                                     error=error_msg)
        
        # Validate client_id
        if not client_id:
            error_msg = "No client selected"
            print(f"DEBUG ERROR: {error_msg}")
            return render_template('index.html', 
                                 clients=get_clients_from_supabase(), 
                                 error=error_msg)
        
        # Handle file upload
        if 'vtt_file' not in request.files:
            error_msg = "No file uploaded"
            print(f"DEBUG ERROR: {error_msg}")
            return render_template('index.html', 
                                 clients=get_clients_from_supabase(), 
                                 error=error_msg)
            
        vtt_file = request.files['vtt_file']
        print(f"DEBUG: VTT filename: {vtt_file.filename}")
        
        if vtt_file.filename == '':
            error_msg = "No file selected"
            print(f"DEBUG ERROR: {error_msg}")
            return render_template('index.html', 
                                 clients=get_clients_from_supabase(), 
                                 error=error_msg)
            
        if not vtt_file.filename.endswith('.vtt'):
            error_msg = "File must be a .vtt file"
            print(f"DEBUG ERROR: {error_msg}")
            return render_template('index.html', 
                                 clients=get_clients_from_supabase(), 
                                 error=error_msg)
        
        # Process the upload
        print("DEBUG: Processing upload")
        success, message = process_upload(client_id, vtt_file)
        print(f"DEBUG: Upload process result - Success: {success}, Message: {message}")
        
        if success:
            print("DEBUG: Upload successful, redirecting to jobs page")
            return redirect(url_for('jobs'))
        else:
            print(f"DEBUG ERROR: Upload failed - {message}")
            return render_template('index.html', 
                                 clients=get_clients_from_supabase(), 
                                 error=message)
    
    except Exception as e:
        error_msg = f"An error occurred: {str(e)}"
        print(f"DEBUG EXCEPTION: {error_msg}")
        print(f"DEBUG EXCEPTION TRACEBACK: {traceback.format_exc()}")
        return render_template('index.html', 
                             clients=get_clients_from_supabase(), 
                             error=error_msg)

@app.route('/jobs')
def jobs():
    """Display all jobs"""
    jobs_list = get_jobs()
    return render_template('jobs.html', jobs=jobs_list)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
