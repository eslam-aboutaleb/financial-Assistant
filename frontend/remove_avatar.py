import re
with open("src/components/MessageBubble.tsx", "r") as f:
    content = f.read()

# Remove user avatar block completely
user_avatar_regex = r'\{\s*isUser\s*&&\s*\(\s*<div[^>]*id={`user-avatar-\$\{message\.id\}`}[^>]*>.*?</div>\s*\)\s*\}'
content = re.sub(user_avatar_regex, '', content, flags=re.DOTALL)

with open("src/components/MessageBubble.tsx", "w") as f:
    f.write(content)
