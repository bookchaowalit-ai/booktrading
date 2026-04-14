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
    const strategyUrl = process.env.STRATEGY_URL || 'http://strategy:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: '/strategy-api/:path*',
        destination: `${strategyUrl}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
