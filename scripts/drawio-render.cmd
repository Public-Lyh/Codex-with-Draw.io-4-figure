@echo off
python "%~dp0drawio_render.py" %*
exit /b %errorlevel%
