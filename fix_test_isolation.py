with open("backend/tests/test_security_isolation.py", "r") as f:
    content = f.read()

content = content.replace(
    'mock_session = AsyncMock()',
    'mock_session = AsyncMock()\n        mock_session.add = MagicMock()'
)
with open("backend/tests/test_security_isolation.py", "w") as f:
    f.write(content)
