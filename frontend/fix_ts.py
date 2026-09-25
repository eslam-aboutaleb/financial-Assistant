import re
with open("src/app/page.tsx", "r") as f:
    content = f.read()

content = content.replace("export default function Home() {", "import { useRef as usePageRef } from 'react';\n\nexport default function Home() {\n  const touchStartX = usePageRef<number | null>(null);")
content = content.replace("window.startX = touch.clientX;", "touchStartX.current = touch.clientX;")
content = content.replace("if (window.startX && window.startX - touch.clientX > 50) {", "if (touchStartX.current && touchStartX.current - touch.clientX > 50) {")

with open("src/app/page.tsx", "w") as f:
    f.write(content)

with open("__tests__/AuthModal.test.tsx", "r") as f:
    test_content = f.read()

test_content = test_content.replace("onAuthSuccess", "onAuthenticated")

with open("__tests__/AuthModal.test.tsx", "w") as f:
    f.write(test_content)
