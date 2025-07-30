#!/bin/bash
while true; do
    python manage.py generate_rounds
    sleep 300
done
