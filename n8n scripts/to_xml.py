#!/usr/bin/env python3
import sys, json, os
import xml.etree.ElementTree as ET
from datetime import datetime

if len(sys.argv) < 2:
    print("Usage: to_xml.py '<json_string>'", file=sys.stderr)
    sys.exit(1)

raw  = sys.argv[1]
data = json.loads(raw) 

# Dosya adını belirle
now = datetime.now()

# Dosya adı için format: 
# "2025-07-08-14-45-12" "yyyy-mm-dd-HH-MM-SS"
formatted= now.strftime("%Y-%m-%d-%H-%M-%S")
formatted += ".xml"

out_dir  = os.path.expanduser("~/Desktop/outputs")
os.makedirs(out_dir, exist_ok=True)
file_path = os.path.join(out_dir, formatted)

root = ET.Element("records")

for item in data:
    # her bir dict için bir <record> düğümü
    rec = ET.SubElement(root, "record")
    for key, value in item.items():
        # her alan için <key>value</key>
        child = ET.SubElement(rec, key)
        child.text = str(value)

tree = ET.ElementTree(root)
tree.write(file_path, encoding="utf-8", xml_declaration=True)

# Dosyanın kaydedildiği dizin
print(json.dumps({"filePath": file_path}))