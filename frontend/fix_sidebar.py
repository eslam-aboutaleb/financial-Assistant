with open("src/components/Sidebar.tsx", "r") as f:
    content = f.read()

# Fix the broken div
content = content.replace('<div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20"><Shield className="w-5 h-5 text-white" /></div><div className="hidden"\n          data-testid="sidebar-logo"\n          aria-hidden="true"\n        />', '<div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex flex-shrink-0 items-center justify-center shadow-lg shadow-indigo-500/30" data-testid="sidebar-logo"><Shield className="w-5 h-5 text-white" strokeWidth={2.5} /></div>')

with open("src/components/Sidebar.tsx", "w") as f:
    f.write(content)
