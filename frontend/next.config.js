/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || '',
    NEXT_PUBLIC_STRATEGY_URL: process.env.NEXT_PUBLIC_STRATEGY_URL || '',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8081/ws',
  },
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || 'http://backend:8080';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        // Strategy calls go through the Go backend, which validates the
        // session and injects the server-side AUTH_TOKEN (never the browser).
        source: '/strategy-api/:path*',
        destination: `${backendUrl}/strategy-api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
