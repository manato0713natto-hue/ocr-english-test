#!/usr/bin/env bash

sleep 10

while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
  echo "Waiting for dpkg lock..."
  sleep 3
done

apt-get update
apt-get install -y tesseract-ocr
