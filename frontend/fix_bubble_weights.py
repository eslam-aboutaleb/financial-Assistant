import re

with open("src/components/MessageBubble.tsx", "r") as f:
    content = f.read()

# Replace the bubble styling
# We want different padding and shadows for user vs assistant
old_bubble_classes = """className={`px-5 py-3.5 text-[15px] leading-relaxed shadow-sm
            ${
              isUser
                ? "bg-amber-700 text-white rounded-2xl rounded-br-sm"
                : isError
                  ? "bg-red-50 border border-red-200 text-red-800 rounded-2xl rounded-bl-sm"
                  : "bg-beige-50 border border-warm-border text-warm-dark rounded-2xl rounded-bl-sm"
            }`}"""

new_bubble_classes = """className={`text-[15px] leading-relaxed
            ${
              isUser
                ? "px-5 py-3 bg-warm-dark text-white rounded-3xl rounded-tr-sm shadow-md"
                : isError
                  ? "px-5 py-3 bg-red-50 border border-red-200 text-red-800 rounded-2xl rounded-bl-sm shadow-sm"
                  : "px-2 py-2 bg-transparent text-warm-dark"
            }`}"""

content = content.replace(old_bubble_classes, new_bubble_classes)

# Also fix the flex-col alignment for assistant to take more space
# Current: className={`flex flex-col max-w-[85%] ${isUser ? "items-end" : "items-start"}`}
old_flex = 'className={`flex flex-col max-w-[85%] ${isUser ? "items-end" : "items-start"}`}'
new_flex = 'className={`flex flex-col ${isUser ? "items-end max-w-[75%]" : "items-start max-w-[90%]"}`}'
content = content.replace(old_flex, new_flex)

# And let's remove the user's avatar to make it look more like iMessage / ChatGPT
# User doesn't need an avatar if they have a distinct right-aligned colored bubble.
# Actually, the user avatar is here:
#       {isUser && (
#         <div
#           id={`user-avatar-${message.id}`}
#           className="w-8 h-8 rounded-full bg-beige-300 flex items-center justify-center flex-shrink-0 mt-1"
#           data-testid={`user-avatar-${message.id}`}
#         >
#           <User className="w-5 h-5 text-white" data-testid="user-icon" />
#         </div>
#       )}

with open("src/components/MessageBubble.tsx", "w") as f:
    f.write(content)
