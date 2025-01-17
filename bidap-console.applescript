tell application "Terminal"
	activate
	do script "AWS_PROFILE=bidap /Users/loic/work/utils/session.sh;AWS_PROFILE=bidap aws-console"
end tell
