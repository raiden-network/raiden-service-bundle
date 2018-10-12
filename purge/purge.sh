#!/bin/sh

if [ ! -d ./venv ]; then
    python3 -m venv venv
    . ./venv/bin/activate
    pip3 install -r requirements.txt
else
    . ./venv/bin/activate
fi

exec python3 purge.py "$@"
