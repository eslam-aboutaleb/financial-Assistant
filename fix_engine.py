import re
with open("backend/app/main.py", "r") as f:
    content = f.read()

content = content.replace(
    'logger.info(f"Shutting down {settings.app_name}...")\n',
    'logger.info(f"Shutting down {settings.app_name}...")\n    from app.database import engine\n    await engine.dispose()\n'
)
with open("backend/app/main.py", "w") as f:
    f.write(content)

with open("backend/tests/conftest.py", "r") as f:
    content = f.read()

content = content.replace("    engine.sync_engine.dispose()\n", "")
with open("backend/tests/conftest.py", "w") as f:
    f.write(content)
