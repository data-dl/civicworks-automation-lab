@echo off
rem Double-click to set up (first time only) and open the CivicWorks Lab in your browser.
cd /d "%~dp0"
where py >nul 2>nul && (py -3 start.py %* & goto :end)
where python >nul 2>nul && (python start.py %* & goto :end)
echo Python 3.11 or newer is needed. Install it from https://www.python.org/downloads/ and run this again.
pause
:end
