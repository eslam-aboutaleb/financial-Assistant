import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthProvider, useAuth } from '../src/context/AuthContext';
import React from 'react';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Helper to read auth context
function AuthConsumer() {
  const { token, userId, isLoaded, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="token">{token ?? 'null'}</span>
      <span data-testid="userId">{userId ?? 'null'}</span>
      <span data-testid="isLoaded">{isLoaded ? 'yes' : 'no'}</span>
      <button data-testid="login" onClick={() => login('tok-123', 'usr-456')}>Login</button>
      <button data-testid="logout" onClick={logout}>Logout</button>
    </div>
  );
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('hydrates from localStorage on mount', async () => {
    localStorage.setItem('omnicare_token', 'stored-tok');
    localStorage.setItem('omnicare_user_id', 'stored-usr');

    await act(async () => {
      render(
        <AuthProvider>
          <AuthConsumer />
        </AuthProvider>
      );
    });

    expect(screen.getByTestId('token').textContent).toBe('stored-tok');
    expect(screen.getByTestId('userId').textContent).toBe('stored-usr');
    expect(screen.getByTestId('isLoaded').textContent).toBe('yes');
  });

  it('starts with null values when localStorage is empty', async () => {
    await act(async () => {
      render(
        <AuthProvider>
          <AuthConsumer />
        </AuthProvider>
      );
    });

    expect(screen.getByTestId('token').textContent).toBe('null');
    expect(screen.getByTestId('userId').textContent).toBe('null');
    expect(screen.getByTestId('isLoaded').textContent).toBe('yes');
  });

  it('login persists to localStorage and updates state', async () => {
    await act(async () => {
      render(
        <AuthProvider>
          <AuthConsumer />
        </AuthProvider>
      );
    });

    await act(async () => {
      screen.getByTestId('login').click();
    });

    expect(screen.getByTestId('token').textContent).toBe('tok-123');
    expect(screen.getByTestId('userId').textContent).toBe('usr-456');
    expect(localStorage.getItem('omnicare_token')).toBe('tok-123');
    expect(localStorage.getItem('omnicare_user_id')).toBe('usr-456');
  });

  it('logout clears localStorage and state', async () => {
    localStorage.setItem('omnicare_token', 'tok');
    localStorage.setItem('omnicare_user_id', 'usr');

    await act(async () => {
      render(
        <AuthProvider>
          <AuthConsumer />
        </AuthProvider>
      );
    });

    await act(async () => {
      screen.getByTestId('login').click();
    });

    await act(async () => {
      screen.getByTestId('logout').click();
    });

    expect(screen.getByTestId('token').textContent).toBe('null');
    expect(screen.getByTestId('userId').textContent).toBe('null');
    expect(localStorage.getItem('omnicare_token')).toBeNull();
    expect(localStorage.getItem('omnicare_user_id')).toBeNull();
  });

  it('overwrites existing values on login', async () => {
    localStorage.setItem('omnicare_token', 'old-tok');
    localStorage.setItem('omnicare_user_id', 'old-usr');

    await act(async () => {
      render(
        <AuthProvider>
          <AuthConsumer />
        </AuthProvider>
      );
    });

    await act(async () => {
      screen.getByTestId('login').click();
    });

    expect(localStorage.getItem('omnicare_token')).toBe('tok-123');
    expect(localStorage.getItem('omnicare_user_id')).toBe('usr-456');
  });

  it('throws when useAuth is used outside provider', () => {
    const BadConsumer = () => {
      useAuth();
      return null;
    };

    expect(() => {
      render(<BadConsumer />);
    }).toThrow('useAuth must be used within an AuthProvider');
  });
});
