"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken, clearSession } from "@/lib/auth";
import { apiFetch, ApiError } from "@/lib/api-client";
import { AppHeader } from "@/components/layout/AppHeader";

type GuardStatus = "checking" | "authorized" | "unauthorized";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [status, setStatus] = useState<GuardStatus>("checking");

  useEffect(() => {
    let active = true;

    async function verify() {
      const token = getToken();
      if (!token) {
        setStatus("unauthorized");
        router.replace("/login");
        return;
      }
      try {
        await apiFetch("/api/v1/auth/me");
        if (active) setStatus("authorized");
      } catch (err) {
        if (active) {
          if (err instanceof ApiError && err.status === 401) {
            clearSession();
          }
          setStatus("unauthorized");
          router.replace("/login");
        }
      }
    }

    verify();
    return () => {
      active = false;
    };
  }, [router]);

  if (status !== "authorized") {
    return null;
  }

  return (
    <>
      <AppHeader />
      {children}
    </>
  );
}
