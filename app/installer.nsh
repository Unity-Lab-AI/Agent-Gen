; Agent Gen NSIS hooks (electron-builder `nsis.include`).
; Operator: "the .exe has to install all things it needs to run with option to uninstall oall things also if wanted";
; "i dint see the uninstall option on the installer when it was already installed ... the uninstall wasnt an option
; when it should be".
; The app installs its runtimes and models into a data folder on first run (%LOCALAPPDATA%\AgentGen unless the
; user picked another; the pick is remembered in %LOCALAPPDATA%\AgentGen.location). The setup offers to remove all
; of it when run over an existing install; the uninstaller offers the same.

; $R2 <- the data folder (pointer file first, default second)
!macro agentgenDataDir
  StrCpy $R2 "$LOCALAPPDATA\AgentGen"
  IfFileExists "$LOCALAPPDATA\AgentGen.location" 0 +6
    FileOpen $R3 "$LOCALAPPDATA\AgentGen.location" r
    FileRead $R3 $R4
    FileClose $R3
    StrCmp $R4 "" +2 0
    StrCpy $R2 $R4
!macroend

!macro customInit
  ; an existing per-user install registers here (electron-builder writes UninstallString + InstallLocation)
  ReadRegStr $R0 HKCU "${UNINSTALL_REGISTRY_KEY}" "UninstallString"
  ${If} $R0 != ""
    ReadRegStr $R1 HKCU "${UNINSTALL_REGISTRY_KEY}" "InstallLocation"
    !insertmacro agentgenDataDir
    ; the update replaces the whole install folder: refuse to proceed if her data folder is inside it
    StrLen $R5 $R1
    StrCpy $R6 $R2 $R5
    ${If} $R6 == $R1
      MessageBox MB_OK|MB_ICONSTOP "Her data folder ($R2) is inside the app folder ($R1). Updating would delete it. Move it out first (the app's first-run screen has a Change folder button), then run this setup again."
      Quit
    ${EndIf}
    MessageBox MB_YESNOCANCEL|MB_ICONQUESTION "Agent Gen is already installed.$\r$\n$\r$\nYES    update it (keeps her models, runtimes and settings)$\r$\nNO     uninstall everything, including the models in$\r$\n            $R2$\r$\nCANCEL leave it alone" IDYES agentgenUpdate IDNO agentgenRemoveAll
    Quit
  agentgenRemoveAll:
    ; run the existing uninstaller in place (synchronously), then take the data folder with it
    ExecWait '$R0 /S _?=$R1'
    RMDir /r "$R1"
    RMDir /r "$R2"
    Delete "$LOCALAPPDATA\AgentGen.location"
    MessageBox MB_OK|MB_ICONINFORMATION "Agent Gen and everything it installed for itself have been removed."
    Quit
  agentgenUpdate:
  ${EndIf}
!macroend

!macro customUnInstall
  !insertmacro agentgenDataDir
  MessageBox MB_YESNO|MB_ICONQUESTION "Also remove everything Agent Gen downloaded for itself?$\r$\n$\r$\n$R2$\r$\n(Python runtime, model weights, her brain's models, logs; tens of gigabytes. Cannot be undone.)" /SD IDNO IDNO keepData
    RMDir /r "$R2"
    Delete "$LOCALAPPDATA\AgentGen.location"
  keepData:
!macroend

; the wizard copies the 430 MB app; the honest total is what the first-run screen downloads into the data folder
!macro customWelcomePage
  !define MUI_WELCOMEPAGE_TITLE "Agent Gen"
  !define MUI_WELCOMEPAGE_TEXT "This copies the app itself (about 430 MB).$\r$\n$\r$\nOn first launch she installs what she runs on: a Python runtime, PyTorch, her model weights and her brain. About 80 GB, into a folder you choose on that screen (D: if C: is tight).$\r$\n$\r$\nNVIDIA 16 GB card, Windows 11, 32 GB RAM."
  !insertmacro MUI_PAGE_WELCOME
!macroend
