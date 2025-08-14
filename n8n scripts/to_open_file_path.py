#!/usr/bin/env python3
# to decide os
import sys, json, os
import platform

system = platform.system()

if system == "Darwin":
    print("macOS")
elif system == "Windows":
    print("windows")
else:
    print("linux")