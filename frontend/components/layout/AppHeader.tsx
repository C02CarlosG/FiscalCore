"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearSession } from "@/lib/auth";

export function AppHeader() {
  const router = useRouter();

  function handleLogout() {
    clearSession();
    router.replace("/login");
  }

  return (
    <header className="border-b">
      <div className="mx-auto flex max-w-4xl items-center justify-between p-4 text-sm">
        <nav className="flex gap-4">
          <Link href="/empresas" className="text-blue-600 hover:underline">
            Empresas
          </Link>
          <Link href="/dashboard" className="text-blue-600 hover:underline">
            Dashboard
          </Link>
        </nav>
        <button
          type="button"
          onClick={handleLogout}
          className="font-medium underline"
        >
          Cerrar sesión
        </button>
      </div>
    </header>
  );
}
