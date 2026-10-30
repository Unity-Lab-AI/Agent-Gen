; Agent Gen NSIS hooks (electron-builder `nsis.include`).
; Operator: "the .exe has to install all things it needs to run with option to uninstall oall things also if wanted".
; The app itself installs its runtimes and models into %LOCALAPPDATA%\AgentGen on first run; the uninstaller offers
; to take that folder with it.

!macro customUnInstall
  MessageBox MB_YESNO|MB_ICONQUESTION "Also remove everything Agent Gen downloaded for itself?$\r$\n$\r$\n$LOCALAPPDATA\AgentGen$\r$\n(Python runtime, model weights, her brain's models, logs; tens of gigabytes. Cannot be undone.)" IDNO keepData
    RMDir /r "$LOCALAPPDATA\AgentGen"
  keepData:
!macroend
