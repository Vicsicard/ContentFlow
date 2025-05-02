import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import requests
from dotenv import load_dotenv
import uuid
import traceback
import subprocess

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
        "Prefer": "return=representation"  # This tells Supabase to return the created record
    }
    return {"url": SUPABASE_URL, "headers": headers}

def get_clients_from_supabase():
    """Fetch client list from Supabase"""
    try:
        supabase = get_supabase_client()
        
        if not supabase["url"] or not supabase["headers"]["apikey"]:
            return []
            
        response = requests.get(
            f"{supabase['url']}/rest/v1/clients?select=id,name",
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
        return [
            {"id": "client1", "name": "Demo Client 1"},
            {"id": "client2", "name": "Demo Client 2"},
            {"id": "annie", "name": "Annie"},
        ]

def create_job(client_id, vtt_filename, mp4_filename=None):
    """Create a new processing job in Supabase with extensive error logging"""
    try:
        print(f"DEBUG: Creating job for client {client_id} with VTT {vtt_filename}")
        supabase = get_supabase_client()
        
        # Verify client exists first
        print(f"DEBUG: Verifying client ID: {client_id}")
        client_check_response = requests.get(
            f"{supabase['url']}/rest/v1/clients?id=eq.{client_id}&select=id",
            headers=supabase["headers"]
        )
        
        if client_check_response.status_code != 200:
            print(f"DEBUG ERROR: Client check failed - Status: {client_check_response.status_code}, Response: {client_check_response.text}")
        else:
            clients = client_check_response.json()
            if not clients:
                print(f"DEBUG ERROR: Client with ID {client_id} does not exist")
                
        # Create the job data
        job_data = {
            "client_id": client_id,
            "vtt_filename": vtt_filename,
            "status": "pending"
        }
        
        if mp4_filename:
            job_data["mp4_filename"] = mp4_filename
            
        print(f"DEBUG: Job data prepared: {job_data}")
        
        # Print details of the request we're about to make
        url = f"{supabase['url']}/rest/v1/processing_jobs"
        print(f"DEBUG: Job creation URL: {url}")
        print(f"DEBUG: Headers: Authorization: Bearer [TOKEN], apikey: [API_KEY]")
        print(f"DEBUG: JSON data: {job_data}")
        
        # Send the request
        response = requests.post(
            url,
            headers=supabase["headers"],
            json=job_data
        )
        
        # Log the response details
        print(f"DEBUG: Job creation response status code: {response.status_code}")
        print(f"DEBUG: Job creation response headers: {response.headers}")
        print(f"DEBUG: Job creation response text: {response.text}")
        
        if response.status_code in [200, 201]:
            try:
                job = response.json()
                job_id = job[0]["id"] if job and len(job) > 0 else None
                print(f"DEBUG: Job created successfully with ID: {job_id}")
                return job_id
            except Exception as e:
                print(f"DEBUG ERROR: Could not parse job ID from response: {str(e)}")
                print(f"DEBUG ERROR: Response content: {response.text}")
                return None
        else:
            print(f"DEBUG ERROR: Job creation failed - Status: {response.status_code}")
            print(f"DEBUG ERROR: Response: {response.text}")
            
            # Try to parse the error response
            try:
                error_details = response.json()
                print(f"DEBUG ERROR details: {error_details}")
            except:
                pass
                
            return None
    except Exception as e:
        print(f"DEBUG EXCEPTION in create_job: {str(e)}")
        print(f"DEBUG EXCEPTION TRACEBACK: {traceback.format_exc()}")
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
    """Upload a file to Supabase Storage with improved error handling"""
    try:
        print(f"DEBUG: Uploading file to Supabase: {filename}")
        supabase = get_supabase_client()
        
        # Get just the filename without client path for cleaner logging
        base_filename = os.path.basename(filename)
        print(f"DEBUG: Base filename: {base_filename}")
        
        # Make sure storage bucket exists
        create_bucket_response = requests.post(
            f"{supabase['url']}/storage/v1/bucket",
            headers={
                "Authorization": f"Bearer {supabase['headers']['apikey']}",
                "Content-Type": "application/json"
            },
            json={
                "id": bucket_name,
                "name": bucket_name,
                "public": True
            }
        )
        
        print(f"DEBUG: Create/check bucket response: {create_bucket_response.status_code}")
        if create_bucket_response.status_code not in [200, 201, 400]:  # 400 means bucket already exists
            print(f"DEBUG: Error creating bucket: {create_bucket_response.text}")
        
        # Storage API URL
        storage_url = f"{supabase['url']}/storage/v1/object/{bucket_name}/{filename}"
        print(f"DEBUG: Upload URL: {storage_url}")
        
        # Set appropriate headers
        headers = {
            "Authorization": f"Bearer {supabase['headers']['apikey']}",
            "Content-Type": "application/octet-stream"
        }
        
        print("DEBUG: Sending upload request")
        
        # Try POST first (for new files)
        response = requests.post(
            storage_url,
            headers=headers,
            data=file_content
        )
        
        print(f"DEBUG: Upload response status: {response.status_code}")
        
        # If POST fails, try PUT (for updating existing files)
        if response.status_code not in [200, 201]:
            print("DEBUG: POST failed, trying PUT instead")
            response = requests.put(
                storage_url,
                headers=headers,
                data=file_content
            )
            print(f"DEBUG: PUT response status: {response.status_code}")
        
        if response.status_code in [200, 201]:
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
            # Try fetching the error response
            try:
                error_details = response.json()
                print(f"DEBUG ERROR details: {json.dumps(error_details, indent=2)}")
            except:
                pass
            return None
    except Exception as e:
        print(f"DEBUG EXCEPTION in create_new_client: {str(e)}")
        print(f"DEBUG EXCEPTION TRACEBACK: {traceback.format_exc()}")
        return None

def process_upload(client_id, vtt_file):
    """Process the upload with detailed error logging and improved robustness"""
    try:
        print(f"DEBUG: Processing upload for client: {client_id}")
        
        # Read file content
        print("DEBUG: Reading file content")
        file_content = vtt_file.read()
        
        # Create directory structure based on client ID
        filename = f"{client_id}/{vtt_file.filename}"
        print(f"DEBUG: Target filename in Supabase: {filename}")
        
        print("DEBUG: Uploading file to Supabase")
        # Try uploading multiple times with different methods if needed
        upload_success = False
        
        # Try method 1: Direct upload to path with client ID
        upload_success = upload_file_to_supabase(file_content, filename)
        
        # If that fails, try method 2: Upload to root of bucket
        if not upload_success:
            print("DEBUG: First upload method failed, trying alternative")
            upload_success = upload_file_to_supabase(file_content, vtt_file.filename)
            
            # If this succeeds, update the filename to what we actually used
            if upload_success:
                filename = vtt_file.filename
        
        print(f"DEBUG: Upload final result: {upload_success}")
        
        if upload_success:
            # Create job
            print("DEBUG: Creating job record")
            job_id = create_job(client_id, filename)
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

def ensure_storage_bucket_exists():
    """Make sure the input-files storage bucket exists"""
    try:
        supabase = get_supabase_client()
        
        # Check if bucket exists
        response = requests.get(
            f"{supabase['url']}/storage/v1/bucket/input-files",
            headers={
                "Authorization": f"Bearer {supabase['headers']['apikey']}",
                "Content-Type": "application/json"
            }
        )
        
        # If bucket doesn't exist, create it
        if response.status_code != 200:
            print("Creating input-files storage bucket")
            create_response = requests.post(
                f"{supabase['url']}/storage/v1/bucket",
                headers={
                    "Authorization": f"Bearer {supabase['headers']['apikey']}",
                    "Content-Type": "application/json"
                },
                json={
                    "id": "input-files",
                    "name": "input-files",
                    "public": True
                }
            )
            
            if create_response.status_code in [200, 201]:
                print("Storage bucket created successfully")
                return True
            else:
                print(f"Failed to create storage bucket: {create_response.status_code} {create_response.text}")
                return False
        else:
            print("Storage bucket already exists")
            return True
            
    except Exception as e:
        print(f"Error ensuring storage bucket exists: {str(e)}")
        return False

# Routes
@app.route('/', methods=['GET'])
def index():
    """Display the upload form"""
    # Ensure storage bucket exists on startup
    ensure_storage_bucket_exists()
    
    clients = get_clients_from_supabase()
    return render_template('index.html', clients=clients)

@app.route('/upload', methods=['POST'])
def upload():
    """Handle file upload and job creation with detailed error logging"""
    try:
        print("\n" + "="*50)
        print("DEBUG: Upload function started")
        print("="*50)
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
        print("DEBUG: Starting upload process")
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

@app.route('/setup_database')
def setup_database():
    """Set up required tables in Supabase database"""
    try:
        print("Setting up database tables")
        supabase = get_supabase_client()
        
        # Create clients table
        response = requests.post(
            f"{supabase['url']}/rest/v1/rpc/execute_sql",
            headers=supabase["headers"],
            json={
                "sql": """
                -- Create clients table
                CREATE TABLE IF NOT EXISTS clients (
                  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                  name TEXT NOT NULL,
                  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
                );
                """
            }
        )
        
        if response.status_code not in [200, 201]:
            return f"<h1>Error creating clients table</h1><p>{response.text}</p>"
        
        # Create processing_jobs table
        response = requests.post(
            f"{supabase['url']}/rest/v1/rpc/execute_sql",
            headers=supabase["headers"],
            json={
                "sql": """
                -- Create processing_jobs table
                CREATE TABLE IF NOT EXISTS processing_jobs (
                  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                  client_id UUID REFERENCES clients(id),
                  vtt_filename TEXT NOT NULL,
                  mp4_filename TEXT,
                  status TEXT NOT NULL DEFAULT 'pending',
                  error TEXT,
                  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
                  last_updated TIMESTAMP WITH TIME ZONE DEFAULT now()
                );
                """
            }
        )
        
        if response.status_code not in [200, 201]:
            return f"<h1>Error creating processing_jobs table</h1><p>{response.text}</p>"
        
        # Create storage bucket for input files
        try:
            response = requests.post(
                f"{supabase['url']}/storage/v1/buckets",
                headers={
                    "Authorization": f"Bearer {supabase['headers']['apikey']}",
                    "Content-Type": "application/json"
                },
                json={
                    "id": "input-files",
                    "name": "input-files",
                    "public": False
                }
            )
            
            # 200 success, 400 means it likely already exists
            if response.status_code not in [200, 201, 400]:
                return f"<h1>Error creating storage bucket</h1><p>{response.text}</p>"
                
        except Exception as e:
            return f"<h1>Error creating storage bucket</h1><p>{str(e)}</p>"
        
        return """
        <html>
        <body>
            <h1>Database Setup Complete</h1>
            <p>All required tables and storage buckets have been created.</p>
            <a href="/">Return to Home</a>
        </body>
        </html>
        """
    except Exception as e:
        return f"<h1>Error setting up database</h1><p>{str(e)}</p>"

@app.route('/jobs')
def jobs():
    """List processing jobs"""
    try:
        # Get all jobs
        jobs_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/processing_jobs?select=*",
            headers={"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
            params={"order": "created_at.desc"}
        )
        jobs = jobs_response.json()
        return render_template('jobs.html', jobs=jobs)
    except Exception as e:
        return render_template('jobs.html', error=f"Error retrieving jobs: {str(e)}")

@app.route('/process_jobs', methods=['POST'])
def process_jobs():
    """Process pending jobs"""
    try:
        # Get pending jobs
        jobs_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/processing_jobs?select=*",
            headers={"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
            params={"status": "eq.pending"}
        )
        pending_jobs = jobs_response.json()
        
        if not pending_jobs:
            return render_template('jobs.html', error="No pending jobs found")
        
        # Process each job
        log_output = []
        for job in pending_jobs:
            log_output.append(f"Processing job {job['id']} (VTT-only mode)")
            
            # Run the VTT-only processing script
            try:
                result = subprocess.run([
                    'python', 'process_vtt_only.py', 
                    '--job_id', job['id']
                ], capture_output=True, text=True)
                
                log_output.append(result.stdout)
                
                if result.returncode != 0:
                    log_output.append(f"Error: {result.stderr}")
            except Exception as e:
                log_output.append(f"Error executing process_vtt_only.py: {str(e)}")
        
        # Get updated jobs list
        jobs_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/processing_jobs?select=*",
            headers={"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
            params={"order": "created_at.desc"}
        )
        jobs = jobs_response.json()
        
        process_log = "\n".join(log_output)
        return render_template('jobs.html', jobs=jobs, process_log=process_log)
    except Exception as e:
        return render_template('jobs.html', error=f"Error processing jobs: {str(e)}")

@app.route('/reset_job/<job_id>', methods=['POST'])
def reset_job(job_id):
    """Reset a job to pending status"""
    try:
        # Update job status to pending
        response = requests.patch(
            f"{SUPABASE_URL}/rest/v1/processing_jobs",
            headers={"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
            json={"status": "pending", "error": None},
            params={"id": "eq." + job_id}
        )
        
        # Get updated jobs list
        jobs_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/processing_jobs?select=*",
            headers={"Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
            params={"order": "created_at.desc"}
        )
        jobs = jobs_response.json()
        
        return render_template('jobs.html', jobs=jobs, process_log=f"Reset job {job_id} to pending status")
    except Exception as e:
        return render_template('jobs.html', error=f"Error resetting job: {str(e)}")

@app.route('/process-jobs', methods=['POST'])
def process_jobs_legacy():
    """DEPRECATED: Process pending jobs via old implementation"""
    print("WARNING: Using deprecated process-jobs route. Please update to /process_jobs")
    return redirect(url_for('process_jobs'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
