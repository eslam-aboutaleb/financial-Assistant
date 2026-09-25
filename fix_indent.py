with open("backend/tests/test_security_isolation.py", "r") as f:
    content = f.read()

content = content.replace(
    '        mock_session.add = MagicMock()\n                mock_result = MagicMock()',
    '                mock_session.add = MagicMock()\n                mock_result = MagicMock()'
)
with open("backend/tests/test_security_isolation.py", "w") as f:
    f.write(content)
