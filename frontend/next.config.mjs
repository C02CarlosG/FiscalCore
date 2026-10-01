/** @type {import('next').NextConfig} */
const nextConfig = {
  // En Vercel el frontend y la API se sirven bajo el mismo dominio (ver
  // vercel.json), así que la API se llama con rutas relativas salvo que
  // NEXT_PUBLIC_API_URL indique otro backend.
  env:
    process.env.VERCEL && !process.env.NEXT_PUBLIC_API_URL
      ? { NEXT_PUBLIC_API_URL: "/" }
      : {},
};

export default nextConfig;
