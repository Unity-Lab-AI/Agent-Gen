; Agent Gen NSIS hooks (electron-builder `nsis.include`).
; Operator: "the .exe has to install all things it needs to run with option to uninstall oall things also if wanted";
; "ther are NOT two folders!!! only one"; "the uninstaller needs to proplery remove that when uninistalled".
;
; One folder. The app is installed where the wizard is pointed; her runtimes and models go into <that folder>\data
; on first run. An update replaces the app files but spares data (customRemoveFiles). A plain uninstall asks whether
; data goes too. Running the setup over an existing install asks: update, uninstall everything, or cancel.

; the hub runs as a second "Agent Gen.exe" (Electron in node mode), the sidecars are its children and her face
; engine runs from <folder>\data. electron-builder's own check only kills "Agent Gen.exe" and then says "cannot be
; closed" from three places (the running-app check, the old uninstaller's retries, the file copy's retries) when
; anything still holds a file. installer-stop.ps1 kills the whole lot, waits until the app's files can be written,
; and logs what it killed to <folder>\data\logs\setup.log. 64-bit PowerShell (sysnative) so it sees every process.
!macro agentgenStop DIR
  InitPluginsDir
  File "/oname=$PLUGINSDIR\agentgen-stop.ps1" "${PROJECT_DIR}\installer-stop.ps1"
  StrCpy $R8 "$WINDIR\sysnative\WindowsPowerShell\v1.0\powershell.exe"
  IfFileExists "$R8" +2 0
    StrCpy $R8 "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe"
  nsExec::Exec '"$R8" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\agentgen-stop.ps1" -Dir "${DIR}"'
  Pop $R9
!macroend

!macro customCheckAppRunning
  !insertmacro agentgenStop "$INSTDIR"
!macroend

!macro customInit
  ; an existing per-user install registers its uninstaller and its folder (silent /S = update)
  ReadRegStr $R0 HKCU "${UNINSTALL_REGISTRY_KEY}" "UninstallString"
  ${If} $R0 != ""
    ReadRegStr $R1 HKCU "${INSTALL_REGISTRY_KEY}" "InstallLocation"
    MessageBox MB_YESNOCANCEL|MB_ICONQUESTION "Agent Gen is already installed in$\r$\n$R1$\r$\n$\r$\nYES    update it (the app is replaced; her models, runtimes and settings in $R1\data stay)$\r$\nNO     uninstall everything, the app and her models$\r$\nCANCEL leave it alone" /SD IDYES IDYES agentgenUpdate IDNO agentgenRemoveAll
    Quit
  agentgenRemoveAll:
    ${If} $R1 != ""
      !insertmacro agentgenStop "$R1"
      ExecWait '$R0 /S _?=$R1'
      RMDir /r "$R1"
    ${Else}
      ExecWait '$R0 /S'
    ${EndIf}
    MessageBox MB_OK|MB_ICONINFORMATION "Agent Gen and everything it installed for itself have been removed."
    Quit
  agentgenUpdate:
  ${EndIf}
!macroend

; replaces electron-builder's "RMDir /r $INSTDIR": everything in the install folder goes except the data subfolder
!macro customRemoveFiles
  SetOutPath $TEMP
  FindFirst $0 $1 "$INSTDIR\*"
  agentgenRmLoop:
    StrCmp $1 "" agentgenRmDone
    StrCmp $1 "." agentgenRmNext
    StrCmp $1 ".." agentgenRmNext
    StrCmp $1 "data" agentgenRmNext
    IfFileExists "$INSTDIR\$1\*.*" 0 +3
      RMDir /r "$INSTDIR\$1"
      Goto agentgenRmNext
    Delete "$INSTDIR\$1"
  agentgenRmNext:
    FindNext $0 $1
    Goto agentgenRmLoop
  agentgenRmDone:
  FindClose $0
  RMDir "$INSTDIR"
!macroend

; a real uninstall (not the update's internal one) offers to take her data with it
!macro customUnInit
  !insertmacro agentgenStop "$INSTDIR"
!macroend

!macro customUnInstall
  ${ifNot} ${isUpdated}
    ; the in-app "Uninstall everything" button already asked and left this marker: no second question
    IfFileExists "$INSTDIR\data\.purge" 0 agentgenAskData
      RMDir /r "$INSTDIR\data"
      RMDir "$INSTDIR"
      Goto agentgenKeepData
    agentgenAskData:
    MessageBox MB_YESNO|MB_ICONQUESTION "Also remove everything Agent Gen downloaded for itself?$\r$\n$\r$\n$INSTDIR\data$\r$\n(Python runtime, model weights, her brain's models, logs; tens of gigabytes. Cannot be undone.)" /SD IDNO IDNO agentgenKeepData
      RMDir /r "$INSTDIR\data"
      RMDir "$INSTDIR"
    agentgenKeepData:
  ${endIf}
!macroend

; the wizard copies the 430 MB app; the honest total is what the first-run screen downloads into <folder>\data
!macro customWelcomePage
  !define MUI_WELCOMEPAGE_TITLE "Agent Gen"
  !define MUI_WELCOMEPAGE_TEXT "This copies the app itself (about 430 MB) into the folder you pick next.$\r$\n$\r$\nOn first launch she installs what she runs on into that same folder: a Python runtime, PyTorch, her model weights and her brain. About 80 GB, so pick a drive with room.$\r$\n$\r$\nNVIDIA 16 GB card, Windows 11, 32 GB RAM."
  !insertmacro MUI_PAGE_WELCOME
!macroend
