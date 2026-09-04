/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ['echarts', 'zrender'],
  // CIDR(192.168.50.0/24) 미지원. 와일드카드 시도; 동작 안 하면 사용할 IP를 개별 추가.
  allowedDevOrigins: ['localhost', '127.0.0.1', '192.168.50.*', '192.168.50.220'],
};

export default nextConfig;
