@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if not exist "%~dp0..\runtime\build" mkdir "%~dp0..\runtime\build"
cd /d "%~dp0..\runtime\build"
cl /nologo /std:c++17 /MT /EHsc /O2 "%~dp0launcher.cpp" /Fe:"%~dp0..\CyTools_PersonaRP.exe" /link /SUBSYSTEM:WINDOWS user32.lib
