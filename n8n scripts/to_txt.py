#!/usr/bin/env python3
import sys, json, os
from datetime import datetime

if len(sys.argv) < 2:
    print("Usage: to_txt.py '<json_string>'", file=sys.stderr)
    sys.exit(1)

raw = sys.argv[1]
data = json.loads(raw)

# Dosya adını belirle
now = datetime.now()

# Dosya adı için format: 
# "2025-07-08-14-45-12" "yyyy-mm-dd-HH-MM-SS"
formatted= now.strftime("%Y-%m-%d-%H-%M-%S")
formatted += ".txt"

# Dosya yolunu belirle
out_dir = os.path.expanduser("~/Desktop/outputs")
os.makedirs(out_dir, exist_ok=True)
file_path = os.path.join(out_dir, formatted)

with open(file_path, "w", encoding="utf-8") as f:
    for obj in data:
        f.write(json.dumps(obj) + "\n")

# Dosyanın kaydedildiği dizin
print(json.dumps({"filePath": file_path}))
