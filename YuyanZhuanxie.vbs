Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = appDir & "\.venv\Scripts\pythonw.exe"
shell.CurrentDirectory = appDir

If fso.FileExists(pythonw) Then
  shell.Run """" & pythonw & """ -m yuyin_zhuanxie", 0, False
Else
  MsgBox "Missing .venv\Scripts\pythonw.exe. Please run install.ps1 first.", 48, "YuyanZhuanxie"
End If
