import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ['three', 'react-force-graph-3d', '3d-force-graph', 'three-forcegraph', 'three-render-objects'],
  allowedDevOrigins: ['100.77.67.1'],
};

export default nextConfig;
