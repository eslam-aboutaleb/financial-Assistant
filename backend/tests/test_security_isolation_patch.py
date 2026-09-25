with open("tests/test_security_isolation.py") as f:
    content = f.read()


# We will remove two_users from the async tests entirely!
# Wait! They NEED two_users.
