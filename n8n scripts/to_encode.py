from bcrypt import gensalt, hashpw, checkpw
import sys, json, os 
import bcrypt

if len(sys.argv) < 2:
    sys.exit(1)

password = sys.argv[1]
hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

print(json.dumps({"hash_new_pass": hashed}))