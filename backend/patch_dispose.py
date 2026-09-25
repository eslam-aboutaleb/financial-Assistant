with open("tests/conftest.py", "r") as f:
    content = f.read()

new_content = content.replace("    engine.sync_engine.dispose()\n", "")

with open("tests/conftest.py", "w") as f:
    f.write(new_content)
