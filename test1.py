import requests
import uuid

BASE_URL = "http://localhost:8000/api"
USER_EMAIL = "muhammadmurtaza6211@gmail.com"

headers = {
    "Content-Type": "application/json",
    "x-user-email": USER_EMAIL,
}

payload = {
    "course_id": str(uuid.uuid4()),
    "user_input": "Python basics for beginners",
    "type": "video",
}

response = requests.post(
    f"{BASE_URL}/generate-course-layout",
    json=payload,
    headers=headers,
)

print("Status:", response.status_code)
print("Response:", response.json())