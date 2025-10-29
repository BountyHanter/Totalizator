#!/bin/bash
while true; do
    python manage.py run_playoff &       # запустить в фоне
    python manage.py play_round          # запустить и ждать завершения
done
