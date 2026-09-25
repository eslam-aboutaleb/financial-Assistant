with open("tests/test_security_isolation.py", "r") as f:
    content = f.read()

import re

# We will remove two_users from the async tests entirely!
# Wait! They NEED two_users. 
