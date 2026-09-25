import re
with open("backend/tests/test_chat.py", "r") as f:
    content = f.read()

content = content.replace(
    'assert "Simulated internal LLM service crash" in data["error"]["message"]',
    'assert "An unexpected error occurred" in data["error"]["message"]'
)
with open("backend/tests/test_chat.py", "w") as f:
    f.write(content)
