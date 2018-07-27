#!/usr/bin/env bash
python3.6 -m venv venv --without-pip
source venv/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python
deactivate
source venv/bin/activate
./operations/update_dependencies.sh