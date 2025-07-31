#!/bin/bash
while true; do
    python manage.py play_round
done

nohup bash round_play.sh > round_play.log 2>&1 &