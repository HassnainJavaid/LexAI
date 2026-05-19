import requests
import time

BASE_URL = "http://localhost:8000/api"

print("1. Testing Signup...")
res = requests.post(f"{BASE_URL}/v1/auth/signup", json={
    "first_name": "Test",
    "last_name": "Admin",
    "email": "admin2@lexai.app",
    "password": "password123"
})
print("Signup Response:", res.status_code)
if res.status_code == 200:
    token = res.json()["access_token"]
else:
    # already exists
    res = requests.post(f"{BASE_URL}/v1/auth/login", json={"email": "admin2@lexai.app", "password": "password123"})
    token = res.json()["access_token"]

print("\n2. Testing Admin Analytics...")
res = requests.get(f"{BASE_URL}/v1/admin/analytics", headers={"Authorization": f"Bearer {token}"})
print("Admin Analytics Response:", res.status_code)
if res.status_code == 200:
    print(res.json())

print("\n3. Testing Legal Chat (with rate limiting)...")
for i in range(2):
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
    print(f"Chat Response {i+1}:", res.status_code)

print("\nTests completed successfully.")
