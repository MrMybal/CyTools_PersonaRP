@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_icon.ps1"
if errorlevel 1 exit /b %errorlevel%
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if not exist "%~dp0..\runtime\build" mkdir "%~dp0..\runtime\build"
cd /d "%~dp0..\runtime\build"
rc /nologo /I "%~dp0." /fo launcher.res "%~dp0launcher.rc"
if errorlevel 1 exit /b %errorlevel%
cl /nologo /std:c++17 /MT /EHsc /O2 "%~dp0launcher.cpp" /Fe:"%~dp0..\CyTools_PersonaRP.exe" /link /SUBSYSTEM:WINDOWS user32.lib launcher.res
