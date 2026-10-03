"use client";

import { Suspense, useState } from "react";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { EmpresaProvider } from "@/components/providers/EmpresaProvider";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <AuthGuard>
      <EmpresaProvider>
        <Suspense fallback={null}>
        <div className="flex min-h-screen bg-background">
          <Sidebar mobileOpen={mobileOpen} onMobileOpenChange={setMobileOpen} />
          <div className="flex min-h-screen min-w-0 flex-1 flex-col">
            <Header onMenuClick={() => setMobileOpen(true)} />
            <div className="flex-1 px-4 pb-8 pt-6 sm:px-6 lg:px-8 lg:pt-8">
              <div className="mx-auto w-full max-w-[1480px]">{children}</div>
            </div>
          </div>
        </div>
        </Suspense>
      </EmpresaProvider>
    </AuthGuard>
  );
}
