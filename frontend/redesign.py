import os
import glob
import re

replacements = {
    "bg-beige-100": "bg-slate-50",
    "bg-beige-50": "bg-white",
    "bg-beige-200": "bg-slate-100",
    "bg-beige-300": "bg-slate-200",
    "bg-beige-400": "bg-slate-300",
    "bg-beige-900": "bg-slate-900",
    
    "border-warm-border": "border-slate-200",
    "text-warm-dark": "text-slate-900",
    "text-warm-gray": "text-slate-500",
    "bg-warm-gray": "bg-slate-500",
    "bg-warm-dark": "bg-indigo-600",
    
    "bg-amber-700": "bg-indigo-600",
    "bg-amber-800": "bg-indigo-700",
    "text-amber-800": "text-indigo-700",
    "text-amber-700": "text-indigo-600",
    "bg-amber-100": "bg-indigo-100",
    "bg-amber-50": "bg-indigo-50",
    "border-amber-400": "border-indigo-500",
    "ring-amber-200": "ring-indigo-200",
    "ring-amber-400": "ring-indigo-400",
    
    "prose-stone": "prose-slate",
}

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
        
    for old, new in replacements.items():
        content = content.replace(old, new)
        
    with open(filepath, 'w') as f:
        f.write(content)

src_files = glob.glob("src/**/*.tsx", recursive=True) + glob.glob("src/**/*.ts", recursive=True) + glob.glob("src/**/*.css", recursive=True)
for f in src_files:
    process_file(f)

print("Color replacements done.")
