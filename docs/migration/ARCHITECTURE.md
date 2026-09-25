# Architecture

The application is currently a Next.js App Router application (`src/app`).
- Uses `app/layout.tsx` for root layout, providers, and global font.
- Uses `app/page.tsx` for the main interface (sidebar + chat window).
- Global styles in `app/globals.css`.
- API endpoints are external (backend API), called via `src/lib/api.ts`.
- No Next.js API routes are used in `src/app/api`.
