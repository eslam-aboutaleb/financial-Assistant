/**
 * Authentication context for the OmniCare frontend.
 *
 * Provides global access to the current user's authentication state, including
 * the JWT token, user ID, and login/logout methods. State is persisted to
 * ``localStorage`` so sessions survive page refreshes.
 *
 * Usage:
 *   Import ``useAuth`` in any client component to access the auth context:
 *     const { token, userId, login, logout } = useAuth();
 *
 * Lifecycle:
 *   - On mount, the context hydrates state from localStorage.
 *   - ``login`` stores the new token and user ID in both React state and
 *     localStorage.
 *   - ``logout`` clears both and triggers a toast notification.
 */


import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { toast } from "react-hot-toast";

interface AuthContextType {
  /** The JWT access token, or null if not authenticated. */
  token: string | null;
  /** The authenticated user's UUID, or null if not authenticated. */
  userId: string | null;
  /** Whether the auth state has finished hydrating from localStorage. */
  isLoaded: boolean;
  /** Log in a user by storing their token and ID. */
  login: (token: string, userId: string) => void;
  /** Log out the current user and clear stored credentials. */
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  // Hydrate auth state from localStorage on initial mount.
  useEffect(() => {
    const storedToken = localStorage.getItem("omnicare_token");
    const storedUserId = localStorage.getItem("omnicare_user_id");
    if (storedToken && storedUserId) {
      setToken(storedToken);
      setUserId(storedUserId);
    }
    setIsLoaded(true);
  }, []);

  const login = (newToken: string, newUserId: string) => {
    localStorage.setItem("omnicare_token", newToken);
    localStorage.setItem("omnicare_user_id", newUserId);
    setToken(newToken);
    setUserId(newUserId);
  };

  const logout = () => {
    localStorage.removeItem("omnicare_token");
    localStorage.removeItem("omnicare_user_id");
    setToken(null);
    setUserId(null);
    toast.success("Logged out successfully", { id: "Logged out successfully" });
  };

  return (
    <AuthContext.Provider value={{ token, userId, isLoaded, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
