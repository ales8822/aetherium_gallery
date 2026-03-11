#Requires AutoHotkey v2.0
; 1. Configuration
; 1.1 Set the working directory to the folder containing this script
SetWorkingDir(A_ScriptDir)

; 1.2 Define variables
AppName := "Aetherium Gallery"
HostUrl := "http://127.0.0.1:8000"
; Construct the path to the venv python executable
PythonExe := A_ScriptDir . "\venv\Scripts\python.exe"

; 2. Main Logic
; 2.1 Check if server is already running (simple check for existing window)
if WinExist("ahk_exe uvicorn.exe") or WinExist(AppName . " Server") {
    MsgBox(AppName . " is already running.", "Startup", "Iconi T3")
    Run(HostUrl)
    ExitApp()
}

; 2.2 Launch the server
; We run python directly to avoid cmd window staying open unnecessarily
; /c starts uvicorn. Change --reload to --no-reload for slightly faster startup if not coding.
RunWait('cmd.exe /c title ' . AppName . ' Server && ' . PythonExe . ' -m uvicorn aetherium_gallery.main:app --reload --host 0.0.0.0 --port 8000', , "Min")

; 2.3 Wait 2 seconds for the model/server to initialize, then open browser
Sleep(2000)
Run(HostUrl)

; 3. Hotkeys
; 3.1 Global Close Shortcut: Ctrl + Alt + S
^!s:: {
    Result := MsgBox("Shutdown " . AppName . " Server?", "Confirm Exit", "YesNo IconQ")
    if (Result = "Yes") {
        ; Kill the python process running uvicorn
        ProcessClose("python.exe") 
        MsgBox(AppName . " has been shut down.", "Server Status", "Iconi T2")
        ExitApp()
    }
}