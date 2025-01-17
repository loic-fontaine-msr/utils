# utils

brew install aws-console

AWS_PROFILE=bidap aws-console

In Automator, create a new Application.

In that application, add an action "Run AppleScript" For the content of that AppleScript,

tell application "Terminal"
        activate
        do script "ssh aide199@192.16.1.15"
    end tell
Save the application, then in the Finder, drag the new application to the Dock