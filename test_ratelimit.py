import requests
BASE_URL = "http://localhost:8000/api"
print("Testing Rate Limiting...")
for i in range(6):
    res = requests.post(f"{BASE_URL}/legal/chat", json={
        "country": "Pakistan",
        "region": "Punjab",
        "topic": "Tenancy Rights",
        "question": "What are my rights as a tenant? " + str(i),
        "history": [],
        "model": "llama-3.3-70b-versatile",
        "language": "English",
        "reasoning_mode": "Standard Guidance"
    })
    print(f"Req {i+1}: {res.status_code}")
