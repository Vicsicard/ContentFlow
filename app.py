import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import requests
from dotenv import load_dotenv
import uuid

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
        supabase = get_supabase_client()
        
        # Storage API has a different endpoint
        storage_url = f"{supabase['url']}/storage/v1/object/{bucket_name}/{filename}"
        
        # Custom headers for storage
        headers = supabase["headers"].copy()
        headers["Content-Type"] = "application/octet-stream"
        
        response = requests.post(
            storage_url,
            headers=headers,
            data=file_content
        )
        
        if response.status_code == 200:
            return True
        else:
            print(f"Error uploading file: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"Error uploading file: {str(e)}")
        return False

def create_new_client(client_name):
    """Create a new client in the database"""
    try:
        supabase = get_supabase_client()
        
        # Insert the new client
        response = requests.post(
            f"{supabase['url']}/rest/v1/clients",
            headers=supabase["headers"],
            json={"name": client_name}
        )
        
        if response.status_code == 201:
            # Get the ID of the newly created client
            client_data = response.json()
            return client_data[0]['id'] if client_data else None
        else:
            print(f"Error creating client: {response.status_code} {response.text}")
            return None
    except Exception as e:
        print(f"Error creating client: {str(e)}")
        return None

def process_upload(client_id, vtt_file):
    """Process the upload"""
    try:
        # Upload VTT file to Supabase
        file_content = vtt_file.read()
        filename = f"{client_id}/{vtt_file.filename}"
        
        if upload_file_to_supabase(file_content, filename):
            # Create job
            job_id = create_job(client_id, vtt_file.filename)
            
            if job_id:
                return True, 'File uploaded and job created successfully'
            else:
                return False, 'File uploaded but job creation failed'
        else:
            return False, 'File upload failed'
    except Exception as e:
        print(f"Error in upload: {str(e)}")
        return False, f"An error occurred: {str(e)}"

# Routes
@app.route('/', methods=['GET'])
def index():
    """Display the upload form"""
    clients = get_clients_from_supabase()
    return render_template('index.html', clients=clients)

@app.route('/upload', methods=['POST'])
def upload():
    try:
        client_id = request.form.get('client_id')
        
        # Handle new client creation
        if client_id == 'new':
            new_client_name = request.form.get('newClientName')
            if not new_client_name or new_client_name.strip() == '':
                return render_template('index.html', 
                                     clients=get_clients_from_supabase(), 
                                     error="Please enter a name for the new client")
                
            # Create new client in database
            client_id = create_new_client(new_client_name)
            if not client_id:
                return render_template('index.html', 
                                     clients=get_clients_from_supabase(), 
                                     error="Failed to create new client")
        
        # Handle file upload
        if 'vtt_file' not in request.files:
            return render_template('index.html', 
                                 clients=get_clients_from_supabase(), 
                                 error="No file uploaded")
            
        vtt_file = request.files['vtt_file']
        
        if vtt_file.filename == '':
            return render_template('index.html', 
                                 clients=get_clients_from_supabase(), 
                                 error="No file selected")
            
        if not vtt_file.filename.endswith('.vtt'):
            return render_template('index.html', 
                                 clients=get_clients_from_supabase(), 
                                 error="File must be a .vtt file")
        
        # Process the upload
        success, message = process_upload(client_id, vtt_file)
        
        if success:
            return redirect(url_for('jobs'))
        else:
            return render_template('index.html', 
                                 clients=get_clients_from_supabase(), 
                                 error=message)
    
    except Exception as e:
        print(f"Error in upload: {str(e)}")
        return render_template('index.html', 
                             clients=get_clients_from_supabase(), 
                             error=f"An error occurred: {str(e)}")

@app.route('/jobs')
def jobs():
    """Display all jobs"""
    jobs_list = get_jobs()
    return render_template('jobs.html', jobs=jobs_list)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
