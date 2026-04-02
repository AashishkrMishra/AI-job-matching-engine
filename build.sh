#!/usr/bin/env bash
# Render build script — installs Python deps + spaCy model

set -o errexit

pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
