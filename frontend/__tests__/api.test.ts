import { describe, it, expect, vi, beforeEach } from 'vitest';
import { sendMessage, resetChat, getConversations, getConversationHistory } from '../src/lib/api';

// Set NEXT_PUBLIC_API_URL for tests
process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000';

const mockFetch = vi.fn();

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubGlobal('fetch', mockFetch);
});

const TOKEN = 'test-jwt-token';

describe('sendMessage', () => {
  it('sends POST to /api/v1/chat with correct body and headers', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        response: 'Water damage is covered.',
        sources: ['policy.md'],
        tool_calls: [],
      }),
    });

    const result = await sendMessage(TOKEN, 'What is covered?');

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/chat');
    expect(options.method).toBe('POST');
    expect(options.credentials).toBe('include');
    const body = JSON.parse(options.body);
    expect(body.message).toBe('What is covered?');
    expect(options.headers['Authorization']).toBe(`Bearer ${TOKEN}`);
    expect(options.headers['Content-Type']).toBe('application/json');
    expect(typeof options.headers['Idempotency-Key']).toBe('string');
    expect(result.response).toBe('Water damage is covered.');
  });

  it('uses NEXT_PUBLIC_API_URL when set', async () => {
    const original = process.env.NEXT_PUBLIC_API_URL;
    process.env.NEXT_PUBLIC_API_URL = 'https://api.example.com';

    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ response: 'OK', sources: [], tool_calls: [] }),
    });

    await sendMessage(TOKEN, 'Hello');

    expect(mockFetch).toHaveBeenCalledWith(
      'https://api.example.com/api/v1/chat',
      expect.any(Object)
    );

    process.env.NEXT_PUBLIC_API_URL = original;
  });

  it('falls back to localhost when NEXT_PUBLIC_API_URL is not set', async () => {
    const original = process.env.NEXT_PUBLIC_API_URL;
    delete process.env.NEXT_PUBLIC_API_URL;

    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ response: 'OK', sources: [], tool_calls: [] }),
    });

    await sendMessage(TOKEN, 'Hello');

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/chat',
      expect.any(Object)
    );

    process.env.NEXT_PUBLIC_API_URL = original;
  });

  it('throws with parsed error message on 400', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error: { message: 'Bad request' } }),
    });

    await expect(sendMessage(TOKEN, 'Hello')).rejects.toThrow('Bad request');
  });

  it('throws with detail message on 500', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Server crashed' }),
    });

    await expect(sendMessage(TOKEN, 'Hello')).rejects.toThrow('Server crashed');
  });

  it('throws with generic message when response is not JSON', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => { throw new Error('Not JSON'); },
    });

    await expect(sendMessage(TOKEN, 'Hello')).rejects.toThrow(
      'Failed to send message. Please try again.'
    );
  });

  it('does not include Authorization header when token is null', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ response: 'OK', sources: [], tool_calls: [] }),
    });

    await sendMessage(null, 'Hello');

    const [, options] = mockFetch.mock.calls[0];
    expect(options.headers['Authorization']).toBeUndefined();
  });

  it('generates different idempotency keys on each call', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ response: 'OK', sources: [], tool_calls: [] }),
    });

    await sendMessage(TOKEN, 'Hello');
    await sendMessage(TOKEN, 'Hello');

    const key1 = mockFetch.mock.calls[0][1].headers['Idempotency-Key'];
    const key2 = mockFetch.mock.calls[1][1].headers['Idempotency-Key'];
    expect(key1).not.toBe(key2);
  });
});

describe('resetChat', () => {
  it('sends POST to /api/v1/chat/reset', async () => {
    mockFetch.mockResolvedValue({ ok: true });

    await resetChat(TOKEN);

    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/chat/reset');
    expect(options.method).toBe('POST');
    expect(options.credentials).toBe('include');
    expect(options.headers['Authorization']).toBe(`Bearer ${TOKEN}`);
  });

  it('does not include Authorization when token is null', async () => {
    mockFetch.mockResolvedValue({ ok: true });

    await resetChat(null);

    const [, options] = mockFetch.mock.calls[0];
    expect(options.headers['Authorization']).toBeUndefined();
  });
});

describe('getConversations', () => {
  it('fetches conversations list with auth header', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ conversations: [] }),
    });

    await getConversations(TOKEN);

    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/chat/conversations');
    expect(options.headers['Authorization']).toBe(`Bearer ${TOKEN}`);
  });

  it('throws on non-ok response', async () => {
    mockFetch.mockResolvedValue({ ok: false });

    await expect(getConversations(TOKEN)).rejects.toThrow('Failed to load conversations');
  });
});

describe('getConversationHistory', () => {
  it('fetches history for given conversation id', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ id: '123', messages: [] }),
    });

    await getConversationHistory(TOKEN, 'conv-123');

    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe('http://localhost:8000/api/v1/chat/conversations/conv-123');
  });

  it('throws on non-ok response', async () => {
    mockFetch.mockResolvedValue({ ok: false });

    await expect(getConversationHistory(TOKEN, 'conv-123')).rejects.toThrow(
      'Failed to load conversation history'
    );
  });
});
