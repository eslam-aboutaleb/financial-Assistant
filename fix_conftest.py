import re
with open("backend/tests/conftest.py", "r") as f:
    content = f.read()

content = content.replace('@pytest.fixture(scope="function")\ndef sample_claims_path(', '@pytest.fixture(scope="session")\ndef sample_claims_path(')
content = content.replace('@pytest.fixture(scope="function")\ndef test_client(', '@pytest.fixture(scope="session")\ndef test_client(')

with open("backend/tests/conftest.py", "w") as f:
    f.write(content)
