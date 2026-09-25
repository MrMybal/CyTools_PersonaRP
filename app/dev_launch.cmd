@echo off
rem Development launcher. The delivered entry point is CyTools_PersonaRP.exe at the root.
cd /d "%~dp0.."
if not exist "runtime\python\Scripts\pythonw.exe" (
  echo Private runtime missing. See LISEZ-MOI.md.
  pause
  exit /b 1
)
start "" "%~dp0..\runtime\python\Scripts\pythonw.exe" "%~dp0desktop.py" %*
