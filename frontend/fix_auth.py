with open("src/components/AuthModal.tsx", "r") as f:
    content = f.read()

# Make the title gradient
content = content.replace('className="text-xl md:text-2xl font-bold text-slate-900 mb-6 text-center"', 'className="text-2xl md:text-3xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-slate-900 to-slate-600 mb-8 text-center tracking-tight"')

# Form inputs
content = content.replace('className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-xl p-3.5 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent transition-all"', 'className="w-full bg-slate-50/50 border border-slate-200 text-slate-900 font-medium rounded-2xl p-4 focus:outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all shadow-sm"')

# Form button
content = content.replace('className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium p-3.5 rounded-xl transition-colors duration-200 disabled:opacity-50"', 'className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold p-4 rounded-2xl shadow-md shadow-indigo-500/20 hover:shadow-lg hover:shadow-indigo-500/30 transition-all duration-300 disabled:opacity-50"')

with open("src/components/AuthModal.tsx", "w") as f:
    f.write(content)
