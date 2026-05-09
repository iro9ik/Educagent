import urllib.request
import json

url = "http://localhost:8000/api/chats"
req = urllib.request.Request(url, method="GET")

try:
    response = urllib.request.urlopen(req)
    print("SUCCESS:", response.read().decode("utf-8"))
except Exception as e:
    print("ERROR:", e)
    if hasattr(e, "read"):
        print("Response:", e.read().decode("utf-8"))
