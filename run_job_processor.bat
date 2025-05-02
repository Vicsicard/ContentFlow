@echo off
echo ===================================================
echo ContentFlow Job Processor
echo ===================================================
echo.
echo Running job processor to check for pending jobs...
echo.

python process_jobs.py

echo.
echo Job processor run complete.
echo.
echo Run this batch file periodically or set up a scheduled task
echo to automatically process jobs through the workflow.
echo ===================================================
pause
