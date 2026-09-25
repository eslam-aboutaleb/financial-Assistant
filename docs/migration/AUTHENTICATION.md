# Authentication

- Provider: Custom AuthContext (`src/context/AuthContext.tsx`).
- Stores token and userId.
- Initial load checks `localStorage`.
- Unauthenticated users are shown the `AuthModal` overlay over the main page.
