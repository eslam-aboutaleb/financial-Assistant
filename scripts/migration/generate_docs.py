import os

docs_dir = "docs/migration"

content = {
    "README.md": """# Readme

This directory contains the baseline documentation for the Next.js to React migration.

## Rollback Requirement
To restore the original Next.js application:
`git checkout nextjs-baseline-before-react-migration`
or
`git switch main`
""",
    "CURRENT_APPLICATION_STATE.md": """# Current Application State

- Framework: Next.js 14.0.0
- React version: 18.2.0
- Styling: Tailwind CSS
- State Management: React Context (Auth), React Query (Data Fetching), Local Component State
- Baseline Tag: `nextjs-baseline-before-react-migration`
""",
    "ARCHITECTURE.md": """# Architecture

The application is currently a Next.js App Router application (`src/app`).
- Uses `app/layout.tsx` for root layout, providers, and global font.
- Uses `app/page.tsx` for the main interface (sidebar + chat window).
- Global styles in `app/globals.css`.
- API endpoints are external (backend API), called via `src/lib/api.ts`.
- No Next.js API routes are used in `src/app/api`.
""",
    "ROUTES.md": """# Routes

| Route | Auth | Component | Query Params | Redirects | APIs |
|-------|------|-----------|--------------|-----------|------|
| `/`   | Yes  | `app/page.tsx` (Main layout with Sidebar and ChatWindow) | None | To AuthModal if unauthenticated | `/api/v1/chat`, `/api/v1/auth` |
""",
    "COMPONENT_INVENTORY.md": """# Component Inventory

1. `AuthModal.tsx`
2. `ChatInput.tsx`
3. `ChatWindow.tsx`
4. `MessageBubble.tsx`
5. `Sidebar.tsx`
6. `SourcesBadge.tsx`
7. `ToolCallBadge.tsx`
""",
    "DESIGN_SYSTEM.md": """# Design System

Colors, spacing, typography are defined via Tailwind configuration and CSS variables.

**Theme colors:**
- `ochre` (50-950)
- `insurance`: `bg`, `surface`, `surface-secondary`, `ink`, `ink-secondary`, `ink-tertiary`, `border`, `border-strong`, `success`, `warning`, `error`, `info`.
- `warm`: `stone`, `ink`, `border`, `muted`, `surface`.
""",
    "TYPOGRAPHY.md": """# Typography

- Font Family: Inter (via Google Fonts `next/font/google`).
- Weights: Default configurations.
- Subsets: Latin.
- Base font size: 15px (via prose).
""",
    "COLORS.md": """# Colors

- `--color-primary`: #b87318
- `--color-primary-dark`: #8a5310
- `--color-bg`: #faf9f6
- `--color-surface`: #ffffff
- `--color-text`: #24211e
- `--color-border`: #e5e0d9
- `--color-success`: #2f7d5a
- `--color-warning`: #b87a2a
- `--color-error`: #b94a48
- `--color-info`: #456b9c
""",
    "SPACING_AND_LAYOUT.md": """# Spacing And Layout

- Tailwind default spacing.
- Radius:
  - `--radius-sm`: 8px
  - `--radius-md`: 12px
  - `--radius-lg`: 16px
""",
    "RESPONSIVE_BEHAVIOR.md": """# Responsive Behavior

- Sidebar is hidden behind a hamburger menu on mobile (screens < `md`).
- On `md` and above, Sidebar is fixed/relative with width `272px`.
- Chat input takes full width of chat container, adjusted by padding.
""",
    "AUTHENTICATION.md": """# Authentication

- Provider: Custom AuthContext (`src/context/AuthContext.tsx`).
- Stores token and userId.
- Initial load checks `localStorage`.
- Unauthenticated users are shown the `AuthModal` overlay over the main page.
""",
    "API_CONTRACTS.md": """# Api Contracts

External backend API is consumed via `src/lib/api.ts`.
- POST `/api/v1/auth/login`
- POST `/api/v1/auth/signup`
- POST `/api/v1/chat/message`
- POST `/api/v1/chat/reset`
- GET `/api/v1/chat/history`
- GET `/api/v1/chat/sessions`
""",
    "STATE_MANAGEMENT.md": """# State Management

- `AuthContext`: Manages `token`, `userId`, `isLoaded`.
- React Query: Used for fetching chat history, sessions, etc. (configured in `providers.tsx`).
- Local State: Form inputs (useState), UI toggles (sidebarOpen).
""",
    "BROWSER_STORAGE.md": """# Browser Storage

- `localStorage`: Used to persist authentication token and possibly session metadata.
""",
    "INTERACTIONS.md": """# Interactions

- Sidebar toggle on mobile.
- Form submissions (Auth, Chat input).
- Retry message on failure.
- Auto-scroll to bottom of chat window.
""",
    "VALIDATION_RULES.md": """# Validation Rules

- Email must be valid format (Auth).
- Password visibility toggle.
- Empty chat messages cannot be sent.
""",
    "ERROR_STATES.md": """# Error States

- Authentication errors show in AuthModal.
- Chat message failures show an error bubble with a "Retry" button.
- Toasts (react-hot-toast) used for global notifications.
""",
    "LOADING_STATES.md": """# Loading States

- Auth loading (spinner in button).
- Chat loading (typing indicator animation `typing-dot`).
- Skeleton loaders for history.
""",
    "ACCESSIBILITY.md": """# Accessibility

- Semantic HTML (main, aside, etc.).
- `aria-label` on buttons (e.g. "Open menu").
- Keyboard navigable focus rings (`*:focus-visible`).
""",
    "NEXTJS_FEATURE_INVENTORY.md": """# Nextjs Feature Inventory

- `next/font/google`: Inter font.
- `next/image`: Possibly used for logos/avatars.
- `app/layout.tsx`: Server component structure.
- `app/page.tsx`: Client-side rendered components inside server layout.
- `next.config.js`: Configuration.
""",
    "MIGRATION_PLAN.md": """# Migration Plan

Phase 0: Repository protection
Phase 1: Application inventory
Phase 2: Baseline documentation
Phase 3: Baseline Playwright tests
Phase 4: Baseline screenshots and hashes
Phase 5: Infrastructure setup for React (Vite)
Phase 6: Routing migration
Phase 7: Shared components
Phase 8: Authentication
Phase 9: Main application shell
Phase 10: Chat
Phase 11: Claims/policies
Phase 12: Forms/uploads
Phase 13: Responsive behavior
Phase 14: Accessibility
Phase 15: Behavioral parity testing
Phase 16: Visual parity testing
Phase 17: Final differential testing
Phase 18: Final Git checkpoint
""",
    "MIGRATION_RISKS.md": """# Migration Risks

- Fonts: Changing from `next/font/google` to standard web fonts might slightly alter rendering.
- Build system: Vite handles env vars differently (`VITE_` prefix vs `NEXT_PUBLIC_`).
""",
    "TEST_MATRIX.md": """# Test Matrix

| Feature | Action | Expected Result | URL | API | Visual |
|---------|--------|-----------------|-----|-----|--------|
| Auth    | Login  | Successful login | `/` | `/api/v1/auth/login` | |
| Chat    | Send   | Message appears  | `/` | `/api/v1/chat/message` | |
""",
    "PARITY_CRITERIA.md": """# Parity Criteria

- Binary screenshot artifacts should be compared byte-for-byte where deterministic
- User-visible output should be compared pixel-for-pixel
- Behavior should be compared through test assertions
- Network behavior should be compared structurally
- Textual output should be compared exactly
- Browser state should be compared
- Source-code/bundle identity should NOT be treated as a parity requirement
""",
    "KNOWN_ISSUES.md": """# Known Issues

None yet.
"""
}

for filename, text in content.items():
    filepath = os.path.join(docs_dir, filename)
    with open(filepath, "w") as f:
        f.write(text)

components = [
    "AuthModal.tsx", "ChatInput.tsx", "ChatWindow.tsx",
    "MessageBubble.tsx", "Sidebar.tsx", "SourcesBadge.tsx", "ToolCallBadge.tsx"
]

for comp in components:
    comp_name = comp.replace(".tsx", "")
    filepath = os.path.join(docs_dir, "components", f"{comp_name}.md")
    with open(filepath, "w") as f:
        f.write(f"# {comp_name}\n\n## File Location\n`frontend/src/components/{comp}`\n\n## Purpose\n\n## Props\n\n## State\n\n## Events\n\n## API Dependencies\n\n## Side Effects\n\n## Conditional Rendering\n\n## Loading States\n\n## Error States\n\n## Empty States\n\n## Responsive Behavior\n\n## Styling\n\n## Accessibility\n\n## Dependencies\n\n## Migration Notes\n")

print("Docs generated successfully.")
