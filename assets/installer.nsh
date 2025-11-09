; Custom NSIS installer script for Windows

!macro customInstall
  ; Add custom installation steps here
  DetailPrint "Installing AGI Assistant..."
  
  ; Create shortcuts
  CreateShortCut "$DESKTOP\AGI Assistant.lnk" "$INSTDIR\AGI Assistant.exe"
  
  DetailPrint "Installation complete!"
!macroend

!macro customUnInstall
  ; Add custom uninstallation steps here
  DetailPrint "Removing AGI Assistant..."
  
  ; Remove shortcuts
  Delete "$DESKTOP\AGI Assistant.lnk"
  
  DetailPrint "Uninstallation complete!"
!macroend

