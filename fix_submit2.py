import re
with open("backend/tests/test_submit_claim.py", "r") as f:
    content = f.read()

content = content.replace('         patch("app.agent.context.current_user_id.get") as mock_get_user:', '')
content = content.replace('        mock_get_user.return_value = uuid.uuid4()', '        from app.agent.context import current_user_id\n        current_user_id.set(uuid.uuid4())')

# Add it to the other tests as well!
content = content.replace('    result = await submit_claim(', '    from app.agent.context import current_user_id\n    current_user_id.set(uuid.uuid4())\n    result = await submit_claim(')

with open("backend/tests/test_submit_claim.py", "w") as f:
    f.write(content)
