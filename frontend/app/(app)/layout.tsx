"use client";

import { useState } from "react";
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
        <div className="flex h-screen overflow-hidden bg-background">
          <Sidebar mobileOpen={mobileOpen} onMobileOpenChange={setMobileOpen} />
          <div className="flex min-w-0 flex-1 flex-col">
            <Header onMenuClick={() => setMobileOpen(true)} />
            <main className="flex-1 overflow-y-auto p-4 lg:p-6">
              {children}
            </main>
          </div>
        </div>
      </EmpresaProvider>
    </AuthGuard>
  );
}
