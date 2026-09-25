import os

docs_dir = "docs/migration"
components_dir = os.path.join(docs_dir, "components")

os.makedirs(components_dir, exist_ok=True)

files = [
    "README.md",
    "CURRENT_APPLICATION_STATE.md",
    "ARCHITECTURE.md",
    "ROUTES.md",
    "COMPONENT_INVENTORY.md",
    "DESIGN_SYSTEM.md",
    "TYPOGRAPHY.md",
    "COLORS.md",
    "SPACING_AND_LAYOUT.md",
    "RESPONSIVE_BEHAVIOR.md",
    "AUTHENTICATION.md",
    "API_CONTRACTS.md",
    "STATE_MANAGEMENT.md",
    "BROWSER_STORAGE.md",
    "INTERACTIONS.md",
    "VALIDATION_RULES.md",
    "ERROR_STATES.md",
    "LOADING_STATES.md",
    "ACCESSIBILITY.md",
    "NEXTJS_FEATURE_INVENTORY.md",
    "MIGRATION_PLAN.md",
    "MIGRATION_RISKS.md",
    "TEST_MATRIX.md",
    "PARITY_CRITERIA.md",
    "KNOWN_ISSUES.md",
]

for file in files:
    filepath = os.path.join(docs_dir, file)
    if not os.path.exists(filepath):
        with open(filepath, "w") as f:
            f.write(f"# {file.replace('.md', '').replace('_', ' ').title()}\n\n")

print("Created documentation files.")
