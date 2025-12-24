/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['storage.googleapis.com', 'firebasestorage.googleapis.com'],
  },
  async rewrites() {
    return [
      {
        source: '/core/:path*',
        destination: 'http://localhost:3010/:path*',
      },
    ]
  },
}

module.exports = nextConfig
