import urllib.request
import json

url = "http://localhost:8000/api/quiz"
data = json.dumps({"topic": "python"}).encode("utf-8")

req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

try:
    response = urllib.request.urlopen(req)
    print("SUCCESS:", response.read().decode("utf-8"))
except Exception as e:
    print("ERROR:", e)
    if hasattr(e, "read"):
        print("Response:", e.read().decode("utf-8"))
