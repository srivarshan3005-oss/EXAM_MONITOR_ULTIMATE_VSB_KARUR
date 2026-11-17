@echo off
cd /d C:\Users\sriva\Downloads\Exam_Monitor_Ultimate_VSB_KARUR_FINAL_RELEASE\backend
start /b .venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8765 >C:\Temp\uvicorn_test.log 2>&1
ping -n 8 127.0.0.1 >nul
.venv\Scripts\python.exe test_portal.py
