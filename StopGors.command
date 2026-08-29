#!/bin/bash
APP_DIR="$HOME/Downloads/GORS APP/GORS/GORS_APP_PROD"
pkill -TERM -f "$APP_DIR/app.py" 2>/dev/null || true
sleep 2
pkill -KILL -f "$APP_DIR/app.py" 2>/dev/null || true
echo "GORS stopped. SQLite database preserved."
exit 0
