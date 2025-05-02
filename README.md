# ContentFlow

A simple workflow automation portal for processing content through App 1 (Self-Cast Studio), App 2 (Style Profiler), and App 3 (Content Generator Suite).

## Overview

ContentFlow automates the process of:
1. Uploading VTT and MP4 files
2. Running App 1 to process transcripts
3. Running App 2 to create a style profile
4. Running App 3 to generate enhanced content
5. Notifying the client when complete

## Setup

1. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

2. **Configure environment variables**:
   Edit the `.env` file and set your Supabase credentials:
   ```
   SUPABASE_URL=your-supabase-url
   SUPABASE_KEY=your-supabase-service-role-key
   ```

3. **Run the portal**:
   ```
   python app.py
   ```
   Or double-click on `start_portal.bat`

4. **Access the portal**:
   Open your browser and navigate to: http://localhost:5000

## Usage

1. Select a client from the dropdown
2. Upload a VTT file (required)
3. Optionally upload an MP4 file
4. Click "Upload and Process"
5. Monitor the status page for progress

## Important Notes

- Processing can take 30-60 minutes depending on file size
- The web server will be busy during processing
- Check the status page for any errors
- All logs are displayed on the status page

## Deployment

ContentFlow can be deployed to Vercel or other Python-compatible hosting services. Make sure to:
1. Set up the necessary environment variables
2. Configure paths to access the three content processing applications
3. Ensure storage permissions are properly set up

## Folder Structure

- `/uploads` - Temporary storage for uploaded files
- `/templates` - HTML templates for the web interface
