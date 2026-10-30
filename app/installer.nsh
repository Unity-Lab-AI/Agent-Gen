; Agent Gen NSIS hooks (electron-builder `nsis.include`).
; Operator: "the .exe has to install all things it needs to run with option to uninstall oall things also if wanted";
; "i dint see the uninstall option on the installer when it was already installed ... the uninstall wasnt an option
; when it should be".
; The app installs its runtimes and models into %LOCALAPPDATA%\AgentGen on first run. The setup offers to remove
; all of it when run over an existing install; the uninstaller offers the same.

!macro customInit
  ; an existing per-user install registers here (electron-builder writes UninstallString + InstallLocation)
  ReadRegStr $R0 HKCU "${UNINSTALL_REGISTRY_KEY}" "UninstallString"
  ${If} $R0 != ""
    ReadRegStr $R1 HKCU "${UNINSTALL_REGISTRY_KEY}" "InstallLocation"
    MessageBox MB_YESNOCANCEL|MB_ICONQUESTION "Agent Gen is already installed.$\r$\n$\r$\nYES    update it (keeps her models, runtimes and settings)$\r$\nNO     uninstall everything, including the models in$\r$\n            $LOCALAPPDATA\AgentGen$\r$\nCANCEL leave it alone" IDYES agentgenUpdate IDNO agentgenRemoveAll
    Quit
  agentgenRemoveAll:
    ; run the existing uninstaller in place (synchronously), then take the data folder with it
    ExecWait '$R0 /S _?=$R1'
    RMDir /r "$R1"
    RMDir /r "$LOCALAPPDATA\AgentGen"
    MessageBox MB_OK|MB_ICONINFORMATION "Agent Gen and everything it installed for itself have been removed."
    Quit
  agentgenUpdate:
  ${EndIf}
!macroend

!macro customUnInstall
  MessageBox MB_YESNO|MB_ICONQUESTION "Also remove everything Agent Gen downloaded for itself?$\r$\n$\r$\n$LOCALAPPDATA\AgentGen$\r$\n(Python runtime, model weights, her brain's models, logs; tens of gigabytes. Cannot be undone.)" /SD IDNO IDNO keepData
    RMDir /r "$LOCALAPPDATA\AgentGen"
  keepData:
!macroend
