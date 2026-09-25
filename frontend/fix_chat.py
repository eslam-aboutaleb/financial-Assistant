import re

with open("src/components/ChatWindow.tsx", "r") as f:
    content = f.read()

# Fix header
content = content.replace('className="text-lg font-semibold text-slate-900 tracking-tight"', 'className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-slate-900 to-slate-600 tracking-tight"')

# Fix empty state logo
empty_state_old = """<div
              className="w-20 h-20 bg-indigo-100 rounded-full flex items-center justify-center mb-2 shadow-sm"
              aria-hidden="true"
            >"""
empty_state_new = """<div
              className="w-20 h-20 bg-gradient-to-br from-indigo-50 to-indigo-100/50 rounded-2xl ring-1 ring-indigo-100 flex items-center justify-center mb-6 shadow-sm rotate-3 hover:rotate-0 transition-transform duration-300"
              aria-hidden="true"
            >"""
content = content.replace(empty_state_old, empty_state_new)

# Fix empty state typography
content = content.replace('text-2xl font-semibold text-slate-900', 'text-3xl font-bold tracking-tight text-slate-900')
content = content.replace('className="text-slate-500 max-w-md leading-relaxed"', 'className="text-slate-500 max-w-md text-lg leading-relaxed"')

# Fix empty state suggestions
old_sugg = 'px-4 py-2 bg-white border border-slate-200 rounded-full text-sm text-slate-500 hover:bg-slate-100 hover:text-slate-900 transition-all duration-200 hover:shadow-sm'
new_sugg = 'px-5 py-2.5 bg-white border border-slate-200/60 rounded-xl text-sm font-medium text-slate-600 hover:border-indigo-300 hover:text-indigo-700 hover:shadow-sm hover:-translate-y-0.5 transition-all duration-200'
content = content.replace(old_sugg, new_sugg)

with open("src/components/ChatWindow.tsx", "w") as f:
    f.write(content)
