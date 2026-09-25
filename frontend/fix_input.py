with open("src/components/ChatInput.tsx", "r") as f:
    content = f.read()

# Input wrapper
content = content.replace('className="relative flex items-end w-full bg-white border border-slate-200 rounded-2xl shadow-sm focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-200 p-2 transition-all duration-200"', 'className="relative flex items-end w-full bg-white border border-slate-200 rounded-3xl shadow-lg shadow-slate-200/50 focus-within:border-indigo-500 focus-within:ring-4 focus-within:ring-indigo-500/10 p-2 transition-all duration-300"')

# Textarea
content = content.replace('className="w-full max-h-[200px] bg-transparent text-slate-900 placeholder-slate-500 resize-none outline-none py-2 px-3 overflow-y-auto disabled:opacity-50"', 'className="w-full max-h-[200px] bg-transparent text-slate-900 placeholder-slate-400 font-medium resize-none outline-none py-3 px-4 overflow-y-auto disabled:opacity-50"')

# Send button
content = content.replace('className="mb-1 mr-1 p-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:bg-slate-200 disabled:text-slate-500 transition-colors duration-200 flex-shrink-0"', 'className="mb-1.5 mr-1.5 p-2.5 bg-indigo-600 text-white rounded-2xl hover:bg-indigo-700 hover:shadow-md disabled:bg-slate-100 disabled:text-slate-400 transition-all duration-200 flex-shrink-0"')

with open("src/components/ChatInput.tsx", "w") as f:
    f.write(content)
