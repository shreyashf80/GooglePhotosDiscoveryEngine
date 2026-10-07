import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  if (!process.env.APP_PASSWORD || request.cookies.get('auth_token')?.value !== process.env.APP_PASSWORD) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  const url = new URL('/api/v1/signals/export', process.env.BACKEND_URL || 'http://localhost:8000');
  url.search = request.nextUrl.search;
  const response = await fetch(url, {
    headers: { 'X-API-Key': process.env.BACKEND_API_KEY || 'dev_key' },
    cache: 'no-store',
  });
  return new Response(response.body, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('Content-Type') || 'text/csv',
      'Content-Disposition': response.headers.get('Content-Disposition') || 'attachment; filename="signals.csv"',
      'Cache-Control': 'no-store',
    },
  });
}
