import re
with open("backend/tests/test_auth_security.py", "r") as f:
    content = f.read()

# Replace ["detail"] with ["error"]["message"]
content = content.replace('r2.json()["detail"]', 'r2.json()["error"]["message"]')
content = content.replace('assert "detail" in data', 'assert "error" in data')
with open("backend/tests/test_auth_security.py", "w") as f:
    f.write(content)
