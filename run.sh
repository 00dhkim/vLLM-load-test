#!/usr/bin/env bash
# run.sh: session 수를 10→20→40→80→160→320 순으로 두 배씩 늘려가며 run.py를 실행합니다.

list=(10 20 40 80 160 320 640)

for sess in "${list[@]}"; do
  echo "===== Running with SESSION_COUNT=${sess} ====="
  python3 main.py "${sess}"
  echo "sleeping for 10 seconds..."
  sleep 10
done

python3 visualize.py
echo "All sessions completed. Visualization generated."
echo "Done."