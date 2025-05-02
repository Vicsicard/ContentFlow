"""
ContentFlow Job Processor

This script checks for pending jobs and processes them through the workflow:
1. Find the next job in 'pending' status
2. Process it with App 1
3. When complete, update status to 'app1_complete'
4. Find jobs in 'app1_complete' status and process with App 2
5. When complete, update status to 'app2_complete'
6. Find jobs in 'app2_complete' status and process with App 3
7. When complete, update status to 'complete'

Run this script on a schedule (e.g., every 15 minutes) to progress jobs through the workflow.
"""

import os
import sys
import subprocess
import requests
import json
from datetime import datetime
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

# Application paths
APP_PATHS = {
    'app1': os.path.abspath(r'C:\Users\digit\CascadeProjects\self-cast-studio-app-1'),
    'app2': os.path.abspath(r'C:\Users\digit\CascadeProjects\style_profiler App2'),
    'app3': os.path.abspath(r'C:\Users\digit\CascadeProjects\App 3 Content Generator Suite')
}

def get_supabase_client():
    """Get a simple wrapper for Supabase API calls"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    return {"url": SUPABASE_URL, "headers": headers}

def log(message):
    """Simple logging function"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def update_job_status(job_id, status, error=None):
    """Update a job's status in Supabase"""
    try:
        supabase = get_supabase_client()
        
        update_data = {
            "status": status,
            "last_updated": datetime.now().isoformat()
        }
        
        if error:
            update_data["error"] = error
        
        response = requests.patch(
            f"{supabase['url']}/rest/v1/processing_jobs?id=eq.{job_id}",
            headers=supabase["headers"],
            json=update_data
        )
        
        if response.status_code == 204:
            log(f"Updated job {job_id} status to {status}")
            return True
        else:
            log(f"Error updating job status: {response.status_code} {response.text}")
            return False
    except Exception as e:
        log(f"Error updating job status: {str(e)}")
        return False

def get_next_job(status="pending"):
    """Get the next job with the specified status"""
    try:
        supabase = get_supabase_client()
        
        response = requests.get(
            f"{supabase['url']}/rest/v1/processing_jobs?status=eq.{status}&order=created_at.asc&limit=1",
            headers=supabase["headers"]
        )
        
        if response.status_code == 200:
            jobs = response.json()
            if jobs:
                return jobs[0]
            else:
                return None
        else:
            log(f"Error fetching next job: {response.status_code} {response.text}")
            return None
    except Exception as e:
        log(f"Error fetching next job: {str(e)}")
        return None

def process_app1_job(job):
    """Process a job with App 1"""
    try:
        job_id = job["id"]
        client_id = job["client_id"]
        vtt_filename = job["vtt_filename"]
        
        log(f"Processing job {job_id} with App 1")
        
        # Update job status to in-progress
        update_job_status(job_id, "app1")
        
        # Download VTT file from Supabase
        supabase = get_supabase_client()
        storage_url = f"{supabase['url']}/storage/v1/object/input-files/{client_id}/{vtt_filename}"
        
        response = requests.get(
            storage_url,
            headers={"Authorization": f"Bearer {SUPABASE_KEY}"}
        )
        
        if response.status_code != 200:
            error_msg = f"Failed to download VTT file: {response.status_code} {response.text}"
            log(error_msg)
            update_job_status(job_id, "error", error_msg)
            return False
        
        # Save VTT file to App 1 input directory
        app1_input_dir = os.path.join(APP_PATHS['app1'], 'input')
        os.makedirs(app1_input_dir, exist_ok=True)
        
        vtt_path = os.path.join(app1_input_dir, vtt_filename)
        with open(vtt_path, 'wb') as f:
            f.write(response.content)
        
        log(f"Saved VTT file to {vtt_path}")
        
        # Run App 1
        os.chdir(APP_PATHS['app1'])
        
        process = subprocess.run(
            ['python', 'process_interview.py', vtt_path],
            capture_output=True,
            text=True
        )
        
        if process.returncode != 0:
            error_msg = f"App 1 processing failed: {process.stderr}"
            log(error_msg)
            update_job_status(job_id, "error", error_msg)
            return False
        
        # Mark job as app1_complete
        update_job_status(job_id, "app1_complete")
        log(f"App 1 processing complete for job {job_id}")
        
        return True
    except Exception as e:
        error_msg = f"Error in App 1 processing: {str(e)}"
        log(error_msg)
        update_job_status(job_id, "error", error_msg)
        return False

def process_app2_job(job):
    """Process a job with App 2"""
    try:
        job_id = job["id"]
        client_id = job["client_id"]
        
        log(f"Processing job {job_id} with App 2")
        
        # Update job status to in-progress
        update_job_status(job_id, "app2")
        
        # App 2 should already have access to the transcript chunks via Supabase
        # We just need to run the App 2 process
        
        os.chdir(APP_PATHS['app2'])
        
        process = subprocess.run(
            ['python', 'profile_generator.py', '--client_id', client_id],
            capture_output=True,
            text=True
        )
        
        if process.returncode != 0:
            error_msg = f"App 2 processing failed: {process.stderr}"
            log(error_msg)
            update_job_status(job_id, "error", error_msg)
            return False
        
        # Mark job as app2_complete
        update_job_status(job_id, "app2_complete")
        log(f"App 2 processing complete for job {job_id}")
        
        return True
    except Exception as e:
        error_msg = f"Error in App 2 processing: {str(e)}"
        log(error_msg)
        update_job_status(job_id, "error", error_msg)
        return False

def process_app3_job(job):
    """Process a job with App 3"""
    try:
        job_id = job["id"]
        client_id = job["client_id"]
        
        log(f"Processing job {job_id} with App 3")
        
        # Update job status to in-progress
        update_job_status(job_id, "app3")
        
        # App 3 accesses everything via Supabase, so we just need to run it
        
        os.chdir(APP_PATHS['app3'])
        
        process = subprocess.run(
            ['python', 'content_generator/content_generator.py', 
             '--use_enhanced', 
             '--client_id', client_id,
             '--supabase_key', SUPABASE_KEY],
            capture_output=True,
            text=True
        )
        
        if process.returncode != 0:
            error_msg = f"App 3 processing failed: {process.stderr}"
            log(error_msg)
            update_job_status(job_id, "error", error_msg)
            return False
        
        # Mark job as complete
        update_job_status(job_id, "complete")
        log(f"App 3 processing complete for job {job_id}")
        
        return True
    except Exception as e:
        error_msg = f"Error in App 3 processing: {str(e)}"
        log(error_msg)
        update_job_status(job_id, "error", error_msg)
        return False

def main():
    """Main processing function"""
    log("Starting ContentFlow job processor")
    
    # Process App 1 jobs (status: pending)
    pending_job = get_next_job("pending")
    if pending_job:
        log(f"Found pending job {pending_job['id']}")
        process_app1_job(pending_job)
    else:
        log("No pending jobs found for App 1")
    
    # Process App 2 jobs (status: app1_complete)
    app1_complete_job = get_next_job("app1_complete")
    if app1_complete_job:
        log(f"Found app1_complete job {app1_complete_job['id']}")
        process_app2_job(app1_complete_job)
    else:
        log("No app1_complete jobs found for App 2")
    
    # Process App 3 jobs (status: app2_complete)
    app2_complete_job = get_next_job("app2_complete")
    if app2_complete_job:
        log(f"Found app2_complete job {app2_complete_job['id']}")
        process_app3_job(app2_complete_job)
    else:
        log("No app2_complete jobs found for App 3")
    
    log("Completed ContentFlow job processing run")

if __name__ == "__main__":
    main()
