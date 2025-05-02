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
            if create_response.status_code not in [200, 201, 400]:
                print(f"Failed to create storage bucket: {create_response.status_code} {create_response.text}")
        
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

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Handle file upload and job creation with detailed error logging"""
    # For GET requests, just display the upload form
    if request.method == 'GET':
        clients = get_clients_from_supabase()
        return render_template('index.html', clients=clients)
        
    # For POST requests, process the upload
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
    """Process pending jobs with enhanced logging"""
    if request.method == 'POST':
        process_log = []
        try:
            print("DEBUG: Starting to process pending jobs")
            process_log.append("Starting job processing at " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # Get pending jobs
            supabase = get_supabase_client()
            
            # Updated: Also include jobs with status 'app1' or 'app2' that might be stuck
            print("DEBUG: Fetching jobs with status: pending, app1, app2, app1_complete, app2_complete")
            response = requests.get(
                f"{supabase['url']}/rest/v1/processing_jobs?status=in.(pending,app1,app2,app1_complete,app2_complete)&order=created_at.desc",
                headers=supabase["headers"]
            )
            
            print(f"DEBUG: Fetch jobs response status: {response.status_code}")
            if response.status_code != 200:
                error_msg = f"Error fetching jobs: {response.status_code}"
                print(f"ERROR: {error_msg}")
                process_log.append("ERROR: " + error_msg)
                return render_template('jobs.html', 
                                      jobs=get_jobs(), 
                                      error=error_msg,
                                      process_log='\n'.join(process_log))
            
            jobs = response.json()
            print(f"DEBUG: Found {len(jobs)} job(s) to process")
            process_log.append(f"Found {len(jobs)} job(s) to process")
            
            if not jobs:
                process_log.append("No pending jobs found to process")
                return render_template('jobs.html', 
                                      jobs=get_jobs(), 
                                      process_log='\n'.join(process_log))
                
            for job in jobs:
                job_id = job["id"]
                client_id = job["client_id"]
                status = job["status"]
                
                log_msg = f"Processing job {job_id} for client {client_id} with status {status}"
                print(f"DEBUG: {log_msg}")
                process_log.append(log_msg)
                
                # Process jobs based on current status
                if status == 'pending':
                    # Process through App 1
                    log_msg = f"Running App 1 for job {job_id}"
                    print(f"DEBUG: {log_msg}")
                    process_log.append(log_msg)
                    
                    # Update job status
                    print(f"DEBUG: Updating job {job_id} status to app1")
                    update_response = requests.patch(
                        f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
                        headers=supabase["headers"],
                        json={
                            "status": "app1",
                            "last_updated": datetime.now().isoformat()
                        }
                    )
                    
                    print(f"DEBUG: Update job status response: {update_response.status_code}")
                    # Accept both 200 and 204 as success codes for Supabase PATCH
                    if update_response.status_code not in [200, 204]:
                        error_msg = f"Error updating job status: {update_response.status_code}"
                        print(f"ERROR: {error_msg}")
                        process_log.append("ERROR: " + error_msg)
                        continue
                    
                    # Get VTT file
                    vtt_filename = job["vtt_filename"]
                    print(f"DEBUG: Processing VTT file: {vtt_filename}")
                    
                    # Run App 1 (simplified for demo)
                    # Replace this with actual App 1 processing logic
                    print(f"DEBUG: Starting App 1 processing for job {job_id}")
                    app1_success = process_app1_job(job)
                    process_log.append("App 1 processing (replace with actual App 1 call)")
                    
                    if app1_success:
                        log_msg = f"App 1 completed successfully for job {job_id}"
                        print(f"DEBUG: {log_msg}")
                        process_log.append(log_msg)
                        
                        # Update job status to app1_complete
                        print(f"DEBUG: Updating job {job_id} status to app1_complete")
                        update_response = requests.patch(
                            f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
                            headers=supabase["headers"],
                            json={
                                "status": "app1_complete",
                                "last_updated": datetime.now().isoformat()
                            }
                        )
                        
                        print(f"DEBUG: Update job status response: {update_response.status_code}")
                        # Accept both 200 and 204 as success codes for Supabase PATCH
                        if update_response.status_code not in [200, 204]:
                            error_msg = f"Error updating job status: {update_response.status_code}"
                            print(f"ERROR: {error_msg}")
                            process_log.append("ERROR: " + error_msg)
                    else:
                        error_msg = f"App 1 failed for job {job_id}"
                        print(f"ERROR: {error_msg}")
                        process_log.append("ERROR: " + error_msg)
                        
                        # Update job status to error
                        print(f"DEBUG: Updating job {job_id} status to error")
                        update_response = requests.patch(
                            f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
                            headers=supabase["headers"],
                            json={
                                "status": "error",
                                "error": "App 1 processing failed",
                                "last_updated": datetime.now().isoformat()
                            }
                        )
                
                # If App 1 is complete, run App 2
                elif status == 'app1_complete':
                    log_msg = f"Running App 2 for job {job_id}"
                    print(f"DEBUG: {log_msg}")
                    process_log.append(log_msg)
                    
                    # Update job status
                    print(f"DEBUG: Updating job {job_id} status to app2")
                    update_response = requests.patch(
                        f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
                        headers=supabase["headers"],
                        json={
                            "status": "app2",
                            "last_updated": datetime.now().isoformat()
                        }
                    )
                    
                    print(f"DEBUG: Update job status response: {update_response.status_code}")
                    # Accept both 200 and 204 as success codes for Supabase PATCH
                    if update_response.status_code not in [200, 204]:
                        error_msg = f"Error updating job status: {update_response.status_code}"
                        print(f"ERROR: {error_msg}")
                        process_log.append("ERROR: " + error_msg)
                        continue
                    
                    # Run App 2
                    print(f"DEBUG: Starting App 2 processing for job {job_id}")
                    app2_success = process_app2_job(job)
                    process_log.append("App 2 processing (replace with actual App 2 call)")
                    
                    if app2_success:
                        log_msg = f"App 2 completed successfully for job {job_id}"
                        print(f"DEBUG: {log_msg}")
                        process_log.append(log_msg)
                        
                        # Update job status to app2_complete
                        print(f"DEBUG: Updating job {job_id} status to app2_complete")
                        update_response = requests.patch(
                            f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
                            headers=supabase["headers"],
                            json={
                                "status": "app2_complete",
                                "last_updated": datetime.now().isoformat()
                            }
                        )
                        
                        print(f"DEBUG: Update job status response: {update_response.status_code}")
                        # Accept both 200 and 204 as success codes for Supabase PATCH
                        if update_response.status_code not in [200, 204]:
                            error_msg = f"Error updating job status: {update_response.status_code}"
                            print(f"ERROR: {error_msg}")
                            process_log.append("ERROR: " + error_msg)
                    else:
                        error_msg = f"App 2 failed for job {job_id}"
                        print(f"ERROR: {error_msg}")
                        process_log.append("ERROR: " + error_msg)
                        
                        # Update job status to error
                        print(f"DEBUG: Updating job {job_id} status to error")
                        update_response = requests.patch(
                            f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
                            headers=supabase["headers"],
                            json={
                                "status": "error",
                                "error": "App 2 processing failed",
                                "last_updated": datetime.now().isoformat()
                            }
                        )
                
                # Note: App 3 is now manually triggered via the UI and not automatically run
                elif status == 'app2_complete':
                    log_msg = f"Job {job_id} is ready for manual App 3 processing"
                    print(f"DEBUG: {log_msg}")
                    process_log.append(log_msg)
                
            process_log.append("Job processing completed at " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            print("DEBUG: Job processing completed")
            
            return render_template('jobs.html', 
                                  jobs=get_jobs(), 
                                  process_log='\n'.join(process_log))
        except Exception as e:
            error_msg = f"Error processing jobs: {str(e)}"
            print(f"ERROR: {error_msg}")
            print(f"ERROR DETAILS: {traceback.format_exc()}")
            process_log.append("ERROR: " + error_msg)
            return render_template('jobs.html', 
                                  jobs=get_jobs(), 
                                  error=error_msg,
                                  process_log='\n'.join(process_log))
    else:
        return redirect(url_for('jobs'))

@app.route('/process-jobs', methods=['POST'])
def process_jobs_legacy():
    """DEPRECATED: Process pending jobs via old implementation"""
    print("WARNING: Using deprecated process-jobs route. Please update to /process_jobs")
    return redirect(url_for('process_jobs'))

@app.route('/reset_job/<job_id>', methods=['POST'])
def reset_job(job_id):
    """Reset a job to pending status"""
    try:
        # Update job status to pending
        supabase = get_supabase_client()
        print(f"DEBUG: Resetting job {job_id} to pending status")
        response = requests.patch(
            f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
            headers=supabase["headers"],
            json={"status": "pending", "error": None, "last_updated": datetime.now().isoformat()}
        )
        
        print(f"DEBUG: Reset job response status: {response.status_code}")
        if response.status_code not in [200, 204]:
            error_msg = f"Error resetting job: {response.status_code}"
            print(f"ERROR: {error_msg}")
            flash(error_msg)
        else:
            success_msg = f"Reset job {job_id} to pending status"
            print(f"DEBUG: {success_msg}")
            flash(success_msg)
        
        return redirect(url_for('jobs'))
    except Exception as e:
        error_msg = f"Error resetting job: {str(e)}"
        print(f"ERROR: {error_msg}")
        print(f"ERROR DETAILS: {traceback.format_exc()}")
        flash(error_msg)
        return redirect(url_for('jobs'))

@app.route('/trigger_app3/<job_id>', methods=['POST'])
def trigger_app3(job_id):
    """Manually trigger App 3 processing for a job with enhanced logging"""
    try:
        print(f"DEBUG: Manually triggering App 3 for job {job_id}")
        
        # Get job details
        supabase = get_supabase_client()
        print(f"DEBUG: Fetching job details for {job_id}")
        job_response = requests.get(
            f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
            headers=supabase["headers"]
        )
        
        print(f"DEBUG: Job fetch response status: {job_response.status_code}")
        if job_response.status_code != 200:
            error_msg = f"Error retrieving job: {job_response.status_code}"
            print(f"ERROR: {error_msg}")
            flash(error_msg)
            return redirect(url_for('jobs'))
            
        jobs = job_response.json()
        if not jobs:
            error_msg = f"Job not found: {job_id}"
            print(f"ERROR: {error_msg}")
            flash(error_msg)
            return redirect(url_for('jobs'))
            
        job = jobs[0]
        client_id = job["client_id"]
        print(f"DEBUG: Processing job {job_id} for client {client_id}")
        
        # Verify App 1 & App 2 artifacts exist before running App 3
        print(f"DEBUG: Verifying App 1 output for client {client_id}")
        app1_verified = verify_app1_output(client_id)
        print(f"DEBUG: App 1 verification result: {app1_verified}")
        
        print(f"DEBUG: Verifying App 2 output for client {client_id}")
        app2_verified = verify_app2_output(client_id)
        print(f"DEBUG: App 2 verification result: {app2_verified}")
        
        if not app1_verified:
            error_msg = f"App 1 artifacts not found for client {client_id}. Cannot run App 3."
            print(f"ERROR: {error_msg}")
            flash(error_msg)
            return redirect(url_for('jobs'))
            
        if not app2_verified:
            error_msg = f"App 2 artifacts not found for client {client_id}. Cannot run App 3."
            print(f"ERROR: {error_msg}")
            flash(error_msg)
            return redirect(url_for('jobs'))
        
        # Update job status to app3
        print(f"DEBUG: Updating job {job_id} status to app3")
        update_response = requests.patch(
            f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
            headers=supabase["headers"],
            json={
                "status": "app3",
                "last_updated": datetime.now().isoformat()
            }
        )
        
        print(f"DEBUG: Status update response: {update_response.status_code}")
        if update_response.status_code != 204:
            error_msg = f"Error updating job status: {update_response.status_code}"
            print(f"ERROR: {error_msg}")
            flash(error_msg)
            return redirect(url_for('jobs'))
            
        # Start App 3 processing
        print(f"DEBUG: Starting App 3 processing for client {client_id}, job {job_id}")
        result = run_app3_job(client_id, job_id)
        
        if result:
            success_msg = "App 3 processing started successfully. Check back later for results."
            print(f"DEBUG: {success_msg}")
            flash(success_msg)
        else:
            error_msg = "Error starting App 3 processing. Check logs for details."
            print(f"ERROR: {error_msg}")
            flash(error_msg)
            
            # Update job status to error
            print(f"DEBUG: Updating job {job_id} status to error")
            error_update_response = requests.patch(
                f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
                headers=supabase["headers"],
                json={
                    "status": "error",
                    "error": "Failed to start App 3 processing",
                    "last_updated": datetime.now().isoformat()
                }
            )
            
        return redirect(url_for('jobs'))
    except Exception as e:
        error_msg = f"Error triggering App 3: {str(e)}"
        print(f"ERROR: {error_msg}")
        print(f"ERROR DETAILS: {traceback.format_exc()}")
        flash(error_msg)
        return redirect(url_for('jobs'))

@app.route('/delete_job/<job_id>', methods=['POST'])
def delete_job(job_id):
    """Delete a job from the database"""
    try:
        # Delete the job from the database
        supabase = get_supabase_client()
        print(f"DEBUG: Deleting job {job_id}")
        response = requests.delete(
            f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
            headers=supabase["headers"]
        )
        
        print(f"DEBUG: Delete job response status: {response.status_code}")
        if response.status_code not in [200, 204]:
            error_msg = f"Error deleting job: {response.status_code}"
            print(f"ERROR: {error_msg}")
            flash(error_msg)
        else:
            success_msg = f"Job {job_id} deleted successfully"
            print(f"DEBUG: {success_msg}")
            flash(success_msg)
        
        return redirect(url_for('jobs'))
    except Exception as e:
        error_msg = f"Error deleting job: {str(e)}"
        print(f"ERROR: {error_msg}")
        print(f"ERROR DETAILS: {traceback.format_exc()}")
        flash(error_msg)
        return redirect(url_for('jobs'))

@app.route('/delete_all_jobs', methods=['POST'])
def delete_all_jobs():
    """Delete all jobs from the database"""
    try:
        # Delete all jobs from the database
        supabase = get_supabase_client()
        print(f"DEBUG: Deleting all jobs")
        
        # First get all job IDs
        jobs_response = requests.get(
            f"{supabase['url']}/rest/v1/processing_jobs?select=id",
            headers=supabase["headers"]
        )
        
        if jobs_response.status_code != 200:
            error_msg = f"Error fetching jobs: {jobs_response.status_code}"
            print(f"ERROR: {error_msg}")
            flash(error_msg)
            return redirect(url_for('jobs'))
            
        jobs = jobs_response.json()
        
        if not jobs:
            message = "No jobs to delete"
            print(f"DEBUG: {message}")
            flash(message)
            return redirect(url_for('jobs'))
            
        # Delete each job individually
        success_count = 0
        failure_count = 0
        
        for job in jobs:
            job_id = job["id"]
            delete_response = requests.delete(
                f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
                headers=supabase["headers"]
            )
            
            if delete_response.status_code in [200, 204]:
                success_count += 1
                print(f"DEBUG: Successfully deleted job {job_id}")
            else:
                failure_count += 1
                print(f"ERROR: Failed to delete job {job_id}: {delete_response.status_code}")
        
        if failure_count == 0:
            success_msg = f"Successfully deleted {success_count} jobs"
            print(f"DEBUG: {success_msg}")
            flash(success_msg)
        else:
            warning_msg = f"Deleted {success_count} jobs, failed to delete {failure_count} jobs"
            print(f"WARNING: {warning_msg}")
            flash(warning_msg)
        
        return redirect(url_for('jobs'))
    except Exception as e:
        error_msg = f"Error deleting all jobs: {str(e)}"
        print(f"ERROR: {error_msg}")
        print(f"ERROR DETAILS: {traceback.format_exc()}")
        flash(error_msg)
        return redirect(url_for('jobs'))

@app.route('/view_content_suggestions/<client_id>/<job_id>')
def view_content_suggestions(client_id, job_id):
    """View generated content suggestions for a job"""
    try:
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Get all content for this project_id from dynamic_content table
        response = requests.get(
            f"{supabase['url']}/rest/v1/dynamic_content?project_id=eq.{client_id}",
            headers=supabase["headers"]
        )
        
        if response.status_code != 200:
            flash("Failed to retrieve content suggestions", "error")
            return redirect(url_for('jobs'))
            
        dynamic_content = response.json()
        
        # Convert to a dictionary for easier template access
        content_dict = {}
        for item in dynamic_content:
            content_dict[item['key']] = item['value']
            
        # Get job details
        job_response = requests.get(
            f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
            headers=supabase["headers"]
        )
        
        if job_response.status_code != 200 or not job_response.json():
            flash("Failed to retrieve job details", "error")
            return redirect(url_for('jobs'))
            
        job = job_response.json()[0]
        
        # Check if we have a content-suggestions.md file
        storage_url = f"{supabase['url']}/storage/v1/object/client-files/{client_id}/content-suggestions.md"
        md_response = requests.head(
            storage_url,
            headers={
                "Authorization": f"Bearer {supabase['headers']['apikey']}"
            }
        )
        
        suggestions_md = ""
        if md_response.status_code == 200:
            # Get the markdown content
            get_response = requests.get(
                storage_url,
                headers={
                    "Authorization": f"Bearer {supabase['headers']['apikey']}"
                }
            )
            if get_response.status_code == 200:
                suggestions_md = get_response.text
                
        return render_template(
            'content_suggestions.html',
            job_id=job_id,
            client_id=client_id,
            content=content_dict,
            suggestions_md=suggestions_md,
            job=job
        )
        
    except Exception as e:
        flash(f"Error viewing content suggestions: {str(e)}", "error")
        print(f"ERROR: {str(e)}")
        print(traceback.format_exc())
        return redirect(url_for('jobs'))

def verify_app1_output(client_id):
    """Verify that App 1 has processed the transcript and created the necessary artifacts"""
    try:
        print(f"DEBUG: Verifying App 1 output for client {client_id}")
        
        # Check for transcript_chunks.md in storage
        supabase = get_supabase_client()
        storage_url = f"{supabase['url']}/storage/v1/object/client-files/{client_id}/transcript_chunks.md"
        
        print(f"DEBUG: Checking for file at {storage_url}")
        response = requests.head(
            storage_url,
            headers={
                "Authorization": f"Bearer {supabase['headers']['apikey']}"
            }
        )
        
        print(f"DEBUG: Storage check response status: {response.status_code}")
        if response.status_code == 200:
            print(f"DEBUG: Found transcript_chunks.md in storage")
            return True
        
        # Fallback: Check if any transcript chunks exist in the database
        print(f"DEBUG: File not found in storage, checking database")
        transcript_response = requests.get(
            f"{supabase['url']}/rest/v1/transcript_chunks?client_id=eq.{client_id}&select=count",
            headers=supabase["headers"]
        )
        
        if transcript_response.status_code == 200 and transcript_response.json():
            print(f"DEBUG: Found transcript chunks in database")
            return True
            
        print(f"DEBUG: No App 1 artifacts found for client {client_id}")
        return False
    except Exception as e:
        print(f"ERROR verifying App 1 output: {str(e)}")
        print(f"ERROR DETAILS: {traceback.format_exc()}")
        return False

def verify_app2_output(client_id):
    """Verify that App 2 has created the style profile"""
    try:
        print(f"DEBUG: Verifying App 2 output for client {client_id}")
        
        # Check for style-profile.md in storage
        supabase = get_supabase_client()
        storage_url = f"{supabase['url']}/storage/v1/object/client-files/{client_id}/style-profile.md"
        
        print(f"DEBUG: Checking for file at {storage_url}")
        response = requests.head(
            storage_url,
            headers={
                "Authorization": f"Bearer {supabase['headers']['apikey']}"
            }
        )
        
        print(f"DEBUG: Storage check response status: {response.status_code}")
        if response.status_code == 200:
            print(f"DEBUG: Found style-profile.md in storage")
            return True
            
        print(f"DEBUG: No App 2 artifacts found for client {client_id}")
        return False
    except Exception as e:
        print(f"ERROR verifying App 2 output: {str(e)}")
        print(f"ERROR DETAILS: {traceback.format_exc()}")
        return False

def run_app3_job(client_id, job_id):
    """Run App 3 processing for a specific client and job"""
    try:
        print(f"DEBUG: Running App 3 processing for client {client_id}, job {job_id}")
        
        # 1. Get style profile data
        supabase = get_supabase_client()
        
        # First check if style-profile.md exists
        print(f"DEBUG: Verifying style-profile.md exists")
        storage_url = f"{supabase['url']}/storage/v1/object/client-files/{client_id}/style-profile.md"
        head_response = requests.head(
            storage_url,
            headers={
                "Authorization": f"Bearer {supabase['headers']['apikey']}"
            }
        )
        
        if head_response.status_code != 200:
            print(f"ERROR: style-profile.md not found: {head_response.status_code}")
            return False
            
        # Get style-profile.md content
        get_response = requests.get(
            storage_url,
            headers={
                "Authorization": f"Bearer {supabase['headers']['apikey']}"
            }
        )
        
        if get_response.status_code != 200:
            print(f"ERROR: Failed to get style-profile.md: {get_response.status_code}")
            return False
            
        style_profile_md = get_response.text
        print(f"DEBUG: Retrieved style profile, length: {len(style_profile_md)} bytes")
        
        # 2. Get transcript data
        print(f"DEBUG: Fetching transcript chunks from database")
        transcript_response = requests.get(
            f"{supabase['url']}/rest/v1/transcript_chunks?client_id=eq.{client_id}&order=seq_num.asc",
            headers=supabase["headers"]
        )
        
        if transcript_response.status_code != 200:
            print(f"ERROR: Failed to get transcript chunks: {transcript_response.status_code}")
            return False
            
        chunks = transcript_response.json()
        
        if not chunks:
            # Fallback to getting transcript_chunks.md
            print(f"DEBUG: No chunks in database, checking for transcript_chunks.md")
            transcript_url = f"{supabase['url']}/storage/v1/object/client-files/{client_id}/transcript_chunks.md"
            transcript_response = requests.get(
                transcript_url,
                headers={
                    "Authorization": f"Bearer {supabase['headers']['apikey']}"
                }
            )
            
            if transcript_response.status_code != 200:
                print(f"ERROR: Failed to get transcript data: {transcript_response.status_code}")
                return False
                
            transcript_text = transcript_response.text
        else:
            # Combine chunks into a single transcript
            transcript_text = " ".join([chunk["text"] for chunk in chunks])
            
        print(f"DEBUG: Retrieved transcript, length: {len(transcript_text)} characters")
        
        # 3. Generate content based on style profile and transcript
        print(f"DEBUG: Generating content")
        
        # Extract tone from style profile
        tone = "Professional"  # Default
        for line in style_profile_md.split('\n'):
            if line.strip().startswith("Professional") or line.strip().startswith("Conversational"):
                tone = line.strip()
                break
                
        # Extract metrics
        word_count = 0
        for line in style_profile_md.split('\n'):
            if "Word Count:" in line:
                try:
                    word_count = int(line.split(':')[1].strip())
                except:
                    pass
        
        # Use client_id as the project_id (since that's what we have available)
        project_id = client_id
        client_short_name = client_id.split('-')[0]
        
        # Dictionary to store all content for markdown generation
        content_keys = {}
        
        # 4. Create subset of main content fields (only subtitle)
        print(f"DEBUG: Creating main content fields")
        
        # Extract potential name from client ID or filename
        # For demo, we'll just use a formatted version of the client ID
        name_parts = client_id.split('-')[0].split('_')
        capitalized_name = ' '.join([part.capitalize() for part in name_parts])
        
        # Note: We're NOT generating rendered_title or profile_image_url per client request
        # These will be provided directly by the user in SelfCast Dynamic
        
        # rendered_subtitle - Subtitle or tagline (professional title)
        professional_title = "Professional Speaker & Industry Expert"
        requests.post(
            f"{supabase['url']}/rest/v1/dynamic_content",
            headers=supabase["headers"],
            json={
                "key": "rendered_subtitle",
                "project_id": project_id,
                "value": professional_title
            }
        )
        content_keys["rendered_subtitle"] = professional_title
        
        # 5. Bio Section Fields
        print(f"DEBUG: Creating bio section fields")
        
        # rendered_bio_html - Main biography text
        bio_text = f"""<p>{capitalized_name} is a recognized expert in the field with over 15 years of professional experience. 
        Known for delivering impactful presentations and workshops that transform how organizations approach their challenges, 
        {capitalized_name.split()[0]} brings a unique blend of strategic thinking and practical implementation to every engagement.</p>
        
        <p>With deep expertise in {client_short_name}'s industry, {capitalized_name.split()[0]} has helped dozens of organizations 
        navigate complex challenges and achieve breakthrough results. {capitalized_name.split()[0]}'s approach is characterized by a commitment to 
        evidence-based methodologies and a focus on delivering measurable outcomes.</p>"""
        
        requests.post(
            f"{supabase['url']}/rest/v1/dynamic_content",
            headers=supabase["headers"],
            json={
                "key": "rendered_bio_html",
                "project_id": project_id,
                "value": bio_text
            }
        )
        content_keys["rendered_bio_html"] = bio_text
        
        # rendered_bio_html_card_1 - Mind card content in bio section
        mind_card = f"""<h3>Strategic Thinking</h3>
        <p>{capitalized_name.split()[0]} approaches problems with a structured analytical framework that combines industry best practices with innovative thinking. This enables organizations to see beyond immediate challenges to identify root causes and sustainable solutions.</p>"""
        
        requests.post(
            f"{supabase['url']}/rest/v1/dynamic_content",
            headers=supabase["headers"],
            json={
                "key": "rendered_bio_html_card_1",
                "project_id": project_id,
                "value": mind_card
            }
        )
        content_keys["rendered_bio_html_card_1"] = mind_card
        
        # rendered_bio_html_card_2 - Body card content in bio section
        body_card = f"""<h3>Practical Application</h3>
        <p>Beyond theory, {capitalized_name.split()[0]} focuses on actionable strategies that can be implemented immediately. This pragmatic approach ensures that insights translate into tangible results and measurable improvements for organizations.</p>"""
        
        requests.post(
            f"{supabase['url']}/rest/v1/dynamic_content",
            headers=supabase["headers"],
            json={
                "key": "rendered_bio_html_card_2",
                "project_id": project_id,
                "value": body_card
            }
        )
        content_keys["rendered_bio_html_card_2"] = body_card
        
        # rendered_bio_html_card_3 - Soul card content in bio section
        soul_card = f"""<h3>Authentic Leadership</h3>
        <p>{capitalized_name.split()[0]} believes in the power of authentic communication and connection. This philosophy informs {capitalized_name.split()[0]}'s approach to leadership development and organizational culture, helping teams work together more effectively.</p>"""
        
        requests.post(
            f"{supabase['url']}/rest/v1/dynamic_content",
            headers=supabase["headers"],
            json={
                "key": "rendered_bio_html_card_3",
                "project_id": project_id,
                "value": soul_card
            }
        )
        content_keys["rendered_bio_html_card_3"] = soul_card
        
        # 6. Quote Fields
        print(f"DEBUG: Creating quote fields")
        
        # quote_1 - First quote (after bio)
        quote1 = f"\"Success isn't just about what you accomplish, it's about what you inspire others to do.\" - {capitalized_name}"
        requests.post(
            f"{supabase['url']}/rest/v1/dynamic_content",
            headers=supabase["headers"],
            json={
                "key": "quote_1",
                "project_id": project_id,
                "value": quote1
            }
        )
        content_keys["quote_1"] = quote1
        
        # quote_2 - Second quote (after blog)
        quote2 = f"\"The most valuable insights often come from the most challenging situations.\" - {capitalized_name}"
        requests.post(
            f"{supabase['url']}/rest/v1/dynamic_content",
            headers=supabase["headers"],
            json={
                "key": "quote_2",
                "project_id": project_id,
                "value": quote2
            }
        )
        content_keys["quote_2"] = quote2
        
        # quote_3 - Third quote (after social media)
        quote3 = f"\"True expertise isn't about having all the answers, but knowing how to ask the right questions.\" - {capitalized_name}"
        requests.post(
            f"{supabase['url']}/rest/v1/dynamic_content",
            headers=supabase["headers"],
            json={
                "key": "quote_3",
                "project_id": project_id,
                "value": quote3
            }
        )
        content_keys["quote_3"] = quote3
        
        # 7. Generate social media posts for all platforms (16 posts - 4 per platform)
        print(f"DEBUG: Generating 16 social media posts for 4 platforms")
        
        # Topic ideas for variety
        topics = [
            "expertise sharing",
            "industry insights",
            "personal reflection",
            "audience engagement"
        ]
        
        # Helper function to generate posts with the right tone
        def generate_social_post(platform, topic_index, client_name):
            topic = topics[topic_index]
            client_short_name = client_name.split('-')[0]
            
            if platform == "facebook":
                if topic_index == 0:
                    return f"Sharing my expertise on {client_short_name}'s latest project. What I've learned can help you navigate similar challenges in your business. #ExpertTips #ProfessionalDevelopment"
                elif topic_index == 1:
                    return f"The industry is evolving rapidly. Here's my take on where {client_short_name}'s sector is headed in 2025 and how you can prepare. #IndustryTrends #FutureReady"
                elif topic_index == 2:
                    return f"My journey with {client_short_name} has taught me valuable lessons about persistence and adaptability. What challenges have shaped your professional path? #PersonalGrowth"
                else:
                    return f"What's your biggest question about {client_short_name}'s field? Drop it in the comments and I'll share my perspective! #AskMe #Community"
                    
            elif platform == "twitter":
                if topic_index == 0:
                    return f"Just wrapped up a project with {client_short_name}. Key takeaway: success comes from attention to detail and clear communication. #ProfessionalTips"
                elif topic_index == 1:
                    return f"Analyzing trends in {client_short_name}'s market space. Seeing major shifts toward digital integration and sustainability. What are you noticing? #MarketAnalysis"
                elif topic_index == 2:
                    return f"Sometimes the hardest projects teach the most valuable lessons. My work with {client_short_name} reinforced that persistence always pays off. #GrowthMindset"
                else:
                    return f"What's the one thing you want to know about {client_short_name}'s industry? Reply with your questions! #EngageWithMe #ExpertAdvice"
                    
            elif platform == "instagram":
                if topic_index == 0:
                    return f"Swipe to see 5 key insights from my latest project with {client_short_name}. These principles can transform how you approach similar challenges. #ProfessionalDevelopment #ExpertTips"
                elif topic_index == 1:
                    return f"The view from my office today while analyzing trends in {client_short_name}'s sector. Fascinating to see how the market is evolving! What trends are you watching? #IndustryInsights"
                elif topic_index == 2:
                    return f"Behind every success story is a journey of challenges. My collaboration with {client_short_name} taught me that adaptability is the key to growth. What's your most important professional lesson? #PersonalJourney"
                else:
                    return f"Question time! What would you like to know about working in {client_short_name}'s field? Drop your questions below and I'll answer in my stories! #AskMeAnything #ProfessionalChat"
                    
            elif platform == "linkedin":
                if topic_index == 0:
                    return f"I recently completed a project with {client_short_name} that reinforced the importance of strategic thinking in today's complex business environment. Here are three methodologies that proved especially effective: 1) Comprehensive stakeholder analysis, 2) Data-driven decision frameworks, 3) Iterative implementation processes. #ProfessionalStrategy #BusinessInsights"
                elif topic_index == 1:
                    return f"The landscape in {client_short_name}'s industry is undergoing significant transformation. Based on my recent analysis, I've identified several emerging trends that will likely reshape the sector over the next 18-24 months. Organizations that adapt early will position themselves for sustainable competitive advantage. #MarketAnalysis #IndustryTrends"
                elif topic_index == 2:
                    return f"Professional growth often comes from navigating complex challenges. My engagement with {client_short_name} presented unique obstacles that required innovative thinking and resilience. I'm sharing this experience because I believe in the value of professional vulnerability and collective learning. #ProfessionalDevelopment #LeadershipLessons"
                else:
                    return f"I'm opening my calendar for a limited number of conversations about {client_short_name}'s industry and the challenges professionals in this space are facing. If you're working through similar challenges or have questions about this sector, comment below or send me a message. #ProfessionalNetworking #IndustryDiscussion"
        
        # Generate titles for posts
        def generate_post_title(platform, topic_index):
            topic = topics[topic_index]
            
            if topic_index == 0:
                return f"Expert Insights: Key Learnings to Apply"
            elif topic_index == 1:
                return f"Industry Trends: What's Coming Next"
            elif topic_index == 2:
                return f"Professional Journey: Valuable Lessons"
            else:
                return f"Let's Connect: Your Questions Answered"
        
        # Generate excerpts for posts
        def generate_post_excerpt(platform, topic_index, client_short_name):
            if topic_index == 0:
                return f"A focused discussion of key professional insights gained from working with {client_short_name}, highlighting practical applications for readers."
            elif topic_index == 1:
                return f"An analysis of emerging industry trends in {client_short_name}'s sector with predictions for future developments and strategic recommendations."
            elif topic_index == 2:
                return f"Personal reflections on professional growth and adaptability learned through collaboration with {client_short_name} and how these lessons apply broadly."
            else:
                return f"An invitation to engage in professional dialogue about {client_short_name}'s industry with opportunities for Q&A and knowledge sharing."
        
        # Store posts in dynamic_content table using the exact field names from SelfCast Dynamic
        print(f"DEBUG: Storing posts in dynamic_content table")
        
        # Define all the content keys we need to create
        platforms = ["facebook", "twitter", "instagram", "linkedin"]
        
        # Generate social media posts for all platforms
        for platform in platforms:
            for i in range(1, 5):  # 4 posts per platform
                post_key = f"{platform}_post_{i}"
                title_key = f"{platform}_title_{i}"
                excerpt_key = f"{platform}_excerpt_{i}"  # New excerpt key for each social post
                
                content_value = generate_social_post(platform, i-1, client_id)
                title_value = generate_post_title(platform, i-1)
                excerpt_value = generate_post_excerpt(platform, i-1, client_short_name)
                
                # Store post content
                post_response = requests.post(
                    f"{supabase['url']}/rest/v1/dynamic_content",
                    headers=supabase["headers"],
                    json={
                        "key": post_key,
                        "project_id": project_id,
                        "value": content_value
                    }
                )
                
                if post_response.status_code not in [200, 201, 204]:
                    print(f"WARNING: Failed to store {post_key} in dynamic_content: {post_response.status_code}")
                    print(f"Response: {post_response.text}")
                else:
                    print(f"DEBUG: Successfully stored {post_key} in dynamic_content")
                
                # Store post title
                title_response = requests.post(
                    f"{supabase['url']}/rest/v1/dynamic_content",
                    headers=supabase["headers"],
                    json={
                        "key": title_key,
                        "project_id": project_id,
                        "value": title_value
                    }
                )
                
                if title_response.status_code not in [200, 201, 204]:
                    print(f"WARNING: Failed to store {title_key} in dynamic_content: {title_response.status_code}")
                    print(f"Response: {title_response.text}")
                else:
                    print(f"DEBUG: Successfully stored {title_key} in dynamic_content")
                
                # Store post excerpt (new)
                excerpt_response = requests.post(
                    f"{supabase['url']}/rest/v1/dynamic_content",
                    headers=supabase["headers"],
                    json={
                        "key": excerpt_key,
                        "project_id": project_id,
                        "value": excerpt_value
                    }
                )
                
                if excerpt_response.status_code not in [200, 201, 204]:
                    print(f"WARNING: Failed to store {excerpt_key} in dynamic_content: {excerpt_response.status_code}")
                    print(f"Response: {excerpt_response.text}")
                else:
                    print(f"DEBUG: Successfully stored {excerpt_key} in dynamic_content")
                
                # Store the values for our markdown summary
                content_keys[post_key] = content_value
                content_keys[title_key] = title_value
                content_keys[excerpt_key] = excerpt_value
        
        # 8. Generate blog post content - using the correct keys from SelfCast Dynamic
        print(f"DEBUG: Generating blog post content")
        
        blog_titles = [
            f"Key Insights from My Work with {client_short_name}",
            f"Industry Trends: The Future of {client_short_name}'s Sector",
            f"Professional Development Lessons from {client_short_name}",
            f"Expert Analysis: Understanding {client_short_name}'s Approach"
        ]
        
        blog_excerpts = [
            f"Discover the most valuable insights I've gained while working with {client_short_name} and how they can benefit your business.",
            f"An in-depth look at emerging trends in {client_short_name}'s industry and what they mean for the future.",
            f"Personal reflections on the professional growth opportunities that came from my collaboration with {client_short_name}.",
            f"A detailed analysis of {client_short_name}'s innovative approach and methodology."
        ]
        
        # Generate placeholder blog content - in a real implementation, this would be more substantive
        blog_contents = [
            f"In my recent work with {client_short_name}, I've discovered several key insights that have broader applications across the industry. This article explores the most significant learnings and how you can apply them to your own context.",
            f"The landscape in {client_short_name}'s sector is rapidly evolving. This article examines the most significant trends that are shaping the future of the industry and how professionals can prepare.",
            f"Professional development often happens in unexpected ways. My collaboration with {client_short_name} provided valuable lessons in leadership, communication, and strategic thinking that I'm sharing in this article.",
            f"What makes {client_short_name}'s approach unique? This analysis breaks down the methodology and examines why it's effective in today's challenging business environment."
        ]
        
        # Store blog content in dynamic_content table - using correct keys from code inspection
        for i in range(1, 5):  # 4 blog posts
            # SelfCast Dynamic uses blog_1_title (not blog_post_1_title)
            blog_title_key = f"blog_{i}_title"
            blog_excerpt_key = f"blog_{i}_excerpt"  # Uses excerpt not description
            blog_content_key = f"blog_{i}"  # Just blog_1 not blog_post_1
            blog_featured_key = f"blog_{i}_featured"
            blog_active_key = f"blog_{i}_active"
            
            # Store blog title
            requests.post(
                f"{supabase['url']}/rest/v1/dynamic_content",
                headers=supabase["headers"],
                json={
                    "key": blog_title_key,
                    "project_id": project_id,
                    "value": blog_titles[i-1]
                }
            )
            
            # Store blog excerpt
            requests.post(
                f"{supabase['url']}/rest/v1/dynamic_content",
                headers=supabase["headers"],
                json={
                    "key": blog_excerpt_key,
                    "project_id": project_id,
                    "value": blog_excerpts[i-1]
                }
            )
            
            # Store blog content
            requests.post(
                f"{supabase['url']}/rest/v1/dynamic_content",
                headers=supabase["headers"],
                json={
                    "key": blog_content_key,
                    "project_id": project_id,
                    "value": blog_contents[i-1]
                }
            )
            
            # Set featured status
            requests.post(
                f"{supabase['url']}/rest/v1/dynamic_content",
                headers=supabase["headers"],
                json={
                    "key": blog_featured_key,
                    "project_id": project_id,
                    "value": "true" if i == 1 else "false"  # First blog is featured
                }
            )
            
            # Set active status
            requests.post(
                f"{supabase['url']}/rest/v1/dynamic_content",
                headers=supabase["headers"],
                json={
                    "key": blog_active_key,
                    "project_id": project_id,
                    "value": "true"  # All blogs are active
                }
            )
            
            # Store for our markdown summary
            content_keys[blog_title_key] = blog_titles[i-1]
            content_keys[blog_excerpt_key] = blog_excerpts[i-1]
            content_keys[blog_content_key] = blog_contents[i-1]
            
        # 9. Create content-suggestions.md file with all generated content
        print(f"DEBUG: Creating content-suggestions.md with all generated content")
        
        # Format as markdown
        md_content = f"""# Content Generated by App 3

## Main Content

**Subtitle:** {content_keys["rendered_subtitle"]}

## Bio Section

**Main Bio:**
{content_keys["rendered_bio_html"]}

**Mind Card:**
{content_keys["rendered_bio_html_card_1"]}

**Body Card:**
{content_keys["rendered_bio_html_card_2"]}

**Soul Card:**
{content_keys["rendered_bio_html_card_3"]}

## Quotes

**Quote 1:** {content_keys["quote_1"]}
**Quote 2:** {content_keys["quote_2"]}
**Quote 3:** {content_keys["quote_3"]}

## Social Media Posts

### Facebook
"""
        
        for i in range(1, 5):
            md_content += f"""
#### {content_keys[f'facebook_title_{i}']}
**Excerpt:** {content_keys[f'facebook_excerpt_{i}']}
**Content:** {content_keys[f'facebook_post_{i}']}

"""
            
        md_content += f"""
### Twitter
"""
        
        for i in range(1, 5):
            md_content += f"""
#### {content_keys[f'twitter_title_{i}']}
**Excerpt:** {content_keys[f'twitter_excerpt_{i}']}
**Content:** {content_keys[f'twitter_post_{i}']}

"""
            
        md_content += f"""
### Instagram
"""
        
        for i in range(1, 5):
            md_content += f"""
#### {content_keys[f'instagram_title_{i}']}
**Excerpt:** {content_keys[f'instagram_excerpt_{i}']}
**Content:** {content_keys[f'instagram_post_{i}']}

"""
            
        md_content += f"""
### LinkedIn
"""
        
        for i in range(1, 5):
            md_content += f"""
#### {content_keys[f'linkedin_title_{i}']}
**Excerpt:** {content_keys[f'linkedin_excerpt_{i}']}
**Content:** {content_keys[f'linkedin_post_{i}']}

"""
            
        md_content += f"""
## Blog Posts

"""

        for i in range(1, 5):
            md_content += f"""
### Blog {i}: {content_keys[f'blog_{i}_title']}

**Excerpt:** {content_keys[f'blog_{i}_excerpt']}

**Content:**
{content_keys[f'blog_{i}']}

"""
            
        md_content += f"""
## Generated
{datetime.now().isoformat()}
"""
        
        # Store the file
        storage_url = f"{supabase['url']}/storage/v1/object/client-files/{client_id}/content-suggestions.md"
        response = requests.post(
            storage_url,
            headers={
                "Authorization": f"Bearer {supabase['headers']['apikey']}",
                "Content-Type": "text/plain"
            },
            data=md_content
        )
        
        if response.status_code not in [200, 201]:
            print(f"ERROR: Failed to upload content-suggestions.md: {response.status_code}")
            return False
            
        print(f"DEBUG: Successfully stored content-suggestions.md")
        
        # 10. Update job status to app3_complete
        print(f"DEBUG: Updating job {job_id} status to app3_complete")
        update_response = requests.patch(
            f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
            headers=supabase["headers"],
            json={
                "status": "app3_complete",
                "last_updated": datetime.now().isoformat()
            }
        )
        
        if update_response.status_code not in [200, 204]:
            print(f"ERROR: Failed to update job status: {update_response.status_code}")
            return False
            
        print(f"DEBUG: App 3 processing completed successfully")
        return True
    except Exception as e:
        print(f"ERROR in run_app3_job: {str(e)}")
        print(traceback.format_exc())
        return False

def process_app2_job(job):
    """Process a job with App 2 to create a style profile"""
    job_id = job["id"]
    client_id = job["client_id"]
    
    try:
        # Update job status to app2
        print(f"DEBUG: Starting App 2 processing for job {job_id}, client {client_id}")
        
        # 1. Load transcript data from App 1 output
        supabase = get_supabase_client()
        
        # First check if transcript_chunks.md exists
        print(f"DEBUG: Verifying transcript_chunks.md exists")
        storage_url = f"{supabase['url']}/storage/v1/object/client-files/{client_id}/transcript_chunks.md"
        head_response = requests.head(
            storage_url,
            headers={
                "Authorization": f"Bearer {supabase['headers']['apikey']}"
            }
        )
        
        if head_response.status_code != 200:
            print(f"ERROR: transcript_chunks.md not found: {head_response.status_code}")
            return False
            
        # Get transcript_chunks.md content
        get_response = requests.get(
            storage_url,
            headers={
                "Authorization": f"Bearer {supabase['headers']['apikey']}"
            }
        )
        
        if get_response.status_code != 200:
            print(f"ERROR: Failed to get transcript_chunks.md: {get_response.status_code}")
            return False
            
        transcript_text = get_response.text
        print(f"DEBUG: Retrieved transcript, length: {len(transcript_text)} bytes")
        
        # 2. Generate style profile (simplified analysis for demo)
        print(f"DEBUG: Generating style profile from transcript")
        
        # Extract basic metrics
        word_count = len(transcript_text.split())
        sentence_count = len([s for s in transcript_text.split('.') if s])
        avg_sentence_length = word_count / max(1, sentence_count)
        
        # Define a basic style profile
        style_profile = {
            "tone": "Professional",
            "word_count": word_count,
            "sentence_count": sentence_count,
            "avg_sentence_length": round(avg_sentence_length, 2),
            "timestamp": datetime.now().isoformat()
        }
        
        # 3. Format as markdown
        print(f"DEBUG: Formatting style profile as markdown")
        style_markdown = f"""# Style Profile

## Tone
{style_profile['tone']}

## Content Analysis
- Word Count: {style_profile['word_count']}
- Sentence Count: {style_profile['sentence_count']}
- Average Sentence Length: {style_profile['avg_sentence_length']} words

## Generated
{style_profile['timestamp']}
"""
        
        # 4. Store as style-profile.md in Supabase storage
        print(f"DEBUG: Storing style-profile.md in Supabase for client {client_id}")
        storage_url = f"{supabase['url']}/storage/v1/object/client-files/{client_id}/style-profile.md"
        
        response = requests.post(
            storage_url,
            headers={
                "Authorization": f"Bearer {supabase['headers']['apikey']}",
                "Content-Type": "text/plain"
            },
            data=style_markdown
        )
        
        if response.status_code not in [200, 201]:
            print(f"ERROR: Failed to upload style profile: {response.status_code}")
            print(f"ERROR: Response: {response.text}")
            return False
            
        print(f"DEBUG: Successfully stored style-profile.md")
        
        # 5. Store style profile in style_profiles table
        print(f"DEBUG: Storing style profile in database")
        
        profile_response = requests.post(
            f"{supabase['url']}/rest/v1/style_profiles",
            headers=supabase["headers"],
            json={
                "client_id": client_id,
                "profile_data": json.dumps(style_profile)
            }
        )
        
        if profile_response.status_code not in [200, 201, 204]:
            print(f"WARNING: Could not store style profile in database: {profile_response.status_code}")
            # Continue anyway since we stored the file
            
        return True
    except Exception as e:
        print(f"ERROR in process_app2_job: {str(e)}")
        print(traceback.format_exc())
        return False

def process_app1_job(job):
    """Process a job with App 1 to extract and chunk transcript"""
    job_id = job["id"]
    client_id = job["client_id"]
    vtt_filename = job["vtt_filename"]
    
    try:
        print(f"DEBUG: Starting App 1 processing for job {job_id}, client {client_id}")
        
        # 1. Download VTT file from storage
        supabase = get_supabase_client()
        print(f"DEBUG: Downloading VTT file: {vtt_filename}")
        
        storage_url = f"{supabase['url']}/storage/v1/object/input-files/{vtt_filename}"
        response = requests.get(
            storage_url,
            headers={
                "Authorization": f"Bearer {supabase['headers']['apikey']}"
            }
        )
        
        if response.status_code != 200:
            print(f"ERROR: Failed to download VTT file: {response.status_code}")
            print(f"ERROR: {response.text}")
            return False
            
        vtt_content = response.text
        print(f"DEBUG: Downloaded VTT file, size: {len(vtt_content)} bytes")
        
        # 2. Extract transcript text from VTT
        print(f"DEBUG: Extracting transcript from VTT")
        transcript_lines = []
        
        # Simple VTT parsing - extract text lines and remove timestamps
        for line in vtt_content.split('\n'):
            # Skip blank lines, timestamps (contains -->), and VTT headers
            if not line.strip() or '-->' in line or line.startswith('WEBVTT'):
                continue
                
            # Skip numeric lines (caption numbers)
            if line.strip().isdigit():
                continue
                
            transcript_lines.append(line.strip())
            
        transcript_text = ' '.join(transcript_lines)
        print(f"DEBUG: Extracted transcript text, length: {len(transcript_text)} characters")
        
        # 3. Chunk the transcript
        print(f"DEBUG: Chunking transcript")
        words = transcript_text.split()
        chunk_size = 500  # words per chunk
        chunks = []
        
        for i in range(0, len(words), chunk_size):
            chunk_text = ' '.join(words[i:i+chunk_size])
            chunks.append({
                "chunk_id": f"chunk_{i//chunk_size + 1}",
                "text": chunk_text,
                "word_count": len(chunk_text.split()),
                "seq_num": i//chunk_size + 1
            })
            
        print(f"DEBUG: Created {len(chunks)} transcript chunks")
        
        # 4. Store chunks in transcript_chunks table
        print(f"DEBUG: Storing transcript chunks in database")
        
        for chunk in chunks:
            chunk_data = {
                "client_id": client_id,
                "job_id": job_id,
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "word_count": chunk["word_count"],
                "seq_num": chunk["seq_num"]
            }
            
            chunk_response = requests.post(
                f"{supabase['url']}/rest/v1/transcript_chunks",
                headers=supabase["headers"],
                json=chunk_data
            )
            
            if chunk_response.status_code not in [200, 201, 204]:
                print(f"WARNING: Failed to store chunk {chunk['chunk_id']}: {chunk_response.status_code}")
                # Continue anyway to store as many chunks as possible
        
        # 5. Store as transcript_chunks.md in Supabase storage
        print(f"DEBUG: Creating transcript_chunks.md")
        
        # Format as markdown
        md_content = f"""# Transcript Chunks\n\n"""
        
        for chunk in chunks:
            md_content += f"## {chunk['chunk_id']}\n\n{chunk['text']}\n\n"
            
        print(f"DEBUG: Storing transcript_chunks.md in Supabase for client {client_id}")
        storage_url = f"{supabase['url']}/storage/v1/object/client-files/{client_id}/transcript_chunks.md"
        
        response = requests.post(
            storage_url,
            headers={
                "Authorization": f"Bearer {supabase['headers']['apikey']}",
                "Content-Type": "text/plain"
            },
            data=md_content
        )
        
        if response.status_code not in [200, 201]:
            print(f"ERROR: Failed to upload transcript_chunks.md: {response.status_code}")
            print(f"ERROR: Response: {response.text}")
            # Continue anyway since we stored the chunks in database
            
        print(f"DEBUG: App 1 processing completed successfully")
        return True
    except Exception as e:
        print(f"ERROR in process_app1_job: {str(e)}")
        print(traceback.format_exc())
        return False

if __name__ == '__main__':
    app.run(debug=True, port=5000)
