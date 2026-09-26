const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || 'dev_key';

export async function fetchApi<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = new URL(`/api/v1${path}`, BACKEND_URL);
  
  // Forward query params if they exist in a server context (optional abstraction)
  
  const headers = new Headers(options.headers);
  headers.set('X-API-Key', BACKEND_API_KEY);
  headers.set('Content-Type', 'application/json');

  const res = await fetch(url.toString(), {
    ...options,
    headers,
    cache: 'no-store' // We always want fresh data for this PM tool
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}
