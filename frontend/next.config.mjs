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

// Las pantallas Visor SAT y Nómina se reemplazaron por el listado único de CFDI.
nextConfig.redirects = async () => [
  { source: "/empresas/:empresaId/cfdi", destination: "/empresas/:empresaId/cfdi/emitidos", permanent: false },
  { source: "/empresas/:empresaId/cfdi/nomina", destination: "/empresas/:empresaId/cfdi/emitidos?tipo=N", permanent: false },
];

export default nextConfig;
