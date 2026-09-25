import re
with open("backend/tests/test_chat.py", "r") as f:
    content = f.read()

content = content.replace('data["detail"]', 'data["error"]["message"]')
content = content.replace('assert "detail" in data', 'assert "error" in data')
with open("backend/tests/test_chat.py", "w") as f:
    f.write(content)
