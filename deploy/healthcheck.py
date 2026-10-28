"""Проверка здоровья контейнера: GET /robots.txt должен ответить кодом < 400.

Host берётся из ALLOWED_HOSTS (первый), чтобы Django не отверг запрос;
X-Forwarded-Proto: https — чтобы при SECURE_SSL_REDIRECT=1 не было редиректа.
"""
import http.client
import os
import sys

port = int(os.environ.get("PORT", "8000"))
hosts = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost").split(",") if h.strip()]
host = next((h.lstrip(".") for h in hosts if h != "*"), "localhost")

try:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
    conn.request("GET", "/robots.txt", headers={"Host": host, "X-Forwarded-Proto": "https"})
    status = conn.getresponse().status
except Exception as exc:  # noqa: BLE001
    print(f"unhealthy: {exc}")
    sys.exit(1)
print(f"status {status}")
sys.exit(0 if status < 400 else 1)
