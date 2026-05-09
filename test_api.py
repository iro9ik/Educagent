import urllib.request
import json

url = "http://localhost:8000/api/settings"
data = json.dumps({
    "settings": {
        "provider": "custom",
        "base_url": "http://localhost:11434/v1",
        "model": "qwen3:8b",
        "embed_model": "nomic-embed-text"
    }
}).encode("utf-8")

req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

try:
    response = urllib.request.urlopen(req)
    print("SUCCESS:", response.read().decode("utf-8"))
except Exception as e:
    print("ERROR:", e)
    if hasattr(e, "read"):
        print("Response:", e.read().decode("utf-8"))
