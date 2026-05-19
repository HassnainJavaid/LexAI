import requests
BASE_URL = "http://localhost:8000/api"
res = requests.post(f"{BASE_URL}/legal/chat", json={
    "country": "Pakistan",
    "region": "Punjab",
    "topic": "Tenancy Rights",
    "question": "What are my rights as a tenant?",
    "history": [],
    "model": "llama-3.3-70b-versatile",
    "language": "English",
    "reasoning_mode": "Standard Guidance"
})
print("Chat Response:", res.status_code, res.text)
