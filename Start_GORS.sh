#!/bin/bash
set -e

APP_DIR="$HOME/Downloads/GORS_APP_PROD"

if [ ! -d "$APP_DIR" ]; then
  echo "GORS_APP_PROD folder not found at:"
  echo "$APP_DIR"
  echo "Please unzip GORS.zip first."
  exit 1
fi

cd "$APP_DIR"
chmod +x run_GORS_APP_PROD.sh
./run_GORS_APP_PROD.sh
