import ForkTsCheckerWebpackPlugin from 'fork-ts-checker-webpack-plugin';

/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.plugins.push(
        new ForkTsCheckerWebpackPlugin({
          async: true, // Run type checking synchronously to block the build
          typescript: {
            configOverwrite: {
              compilerOptions: {
                skipLibCheck: true,
              },
            },
          },
        })
      );
    }
    return config;
  },
  transpilePackages: ['echarts', 'zrender'],
  // CIDR(192.168.50.0/24) 미지원. 와일드카드 시도; 동작 안 하면 사용할 IP를 개별 추가.
  allowedDevOrigins: ['localhost', '127.0.0.1', '192.168.50.*', '192.168.50.220'],
};

export default nextConfig;