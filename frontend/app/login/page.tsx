"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLogin } from "@/hooks/useLogin";
import { ApiError } from "@/lib/api-client";
import { ArrowRight, Building2, FileText, GitBranch, Landmark } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    if (!email || !password) {
      setFormError("Correo y contraseña son obligatorios");
      return;
    }

    try {
      await login.mutateAsync({ email, password });
      router.replace("/empresas");
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("No se pudo iniciar sesión, intenta de nuevo");
      }
    }
  }

  return (
    <main className="grid min-h-[100dvh] bg-background lg:grid-cols-[1.05fr_0.95fr]">
      <section className="relative hidden min-h-[100dvh] flex-col justify-between overflow-hidden bg-foreground px-12 py-10 text-background lg:flex xl:px-16">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(65%_55%_at_82%_-5%,hsl(var(--brand)/0.45),transparent_68%)]"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -left-24 bottom-4 h-80 w-80 rounded-full bg-[radial-gradient(circle,hsl(var(--brand-contrast)/0.30),transparent_70%)] blur-2xl"
        />
        <div className="relative z-10 flex items-center gap-3 font-display text-lg font-bold">
          <span className="flex h-10 w-10 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Landmark className="h-5 w-5" />
          </span>
          FiscalCore
        </div>
        <div className="relative z-10 max-w-xl pb-8">
          <p className="mb-5 text-xs font-bold uppercase text-primary-foreground/65">Plataforma fiscal</p>
          <h1 className="font-display text-4xl font-bold leading-tight xl:text-5xl">
            Visibilidad clara para cada obligación.
          </h1>
          <p className="mt-5 max-w-md text-base leading-7 text-background/70">
            Accede a la información de tus empresas en un espacio de trabajo seguro.
          </p>
          <div className="mt-10 grid max-w-lg grid-cols-3 divide-x divide-background/15 border-y border-background/15 py-5">
            <div className="flex items-center gap-2 px-3 first:pl-0">
              <Building2 className="h-4 w-4 text-primary-foreground/80" />
              <span className="text-xs font-medium">Empresas</span>
            </div>
            <div className="flex items-center gap-2 px-3">
              <FileText className="h-4 w-4 text-primary-foreground/80" />
              <span className="text-xs font-medium">CFDI</span>
            </div>
            <div className="flex items-center gap-2 px-3">
              <GitBranch className="h-4 w-4 text-primary-foreground/80" />
              <span className="text-xs font-medium">Conciliación</span>
            </div>
          </div>
        </div>
        <p className="text-xs text-background/50">FiscalCore · Información fiscal organizada</p>
        <div aria-hidden="true" className="absolute -bottom-28 -right-28 h-96 w-96 rounded-full border border-background/10" />
        <div aria-hidden="true" className="absolute -bottom-16 -right-16 h-72 w-72 rounded-full border border-background/10" />
      </section>

      <section className="flex min-h-[100dvh] items-center justify-center px-5 py-10 sm:px-10 lg:px-12">
        <div className="w-full max-w-[420px]">
          <div className="mb-10 flex items-center gap-2.5 font-display text-base font-bold lg:hidden">
            <span className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Landmark className="h-4 w-4" />
            </span>
            FiscalCore
          </div>
          <div className="mb-8">
            <p className="mb-2 text-xs font-bold uppercase text-primary">Acceso a cuenta</p>
            <h2 className="font-display text-3xl font-bold">Bienvenido</h2>
            <p className="mt-2 text-sm text-muted-foreground">Inicia sesión para continuar.</p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="email">Correo</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Contraseña</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {formError && (
              <p role="alert" className="text-sm text-status-error">
                {formError}
              </p>
            )}

            <Button type="submit" className="h-11 w-full" disabled={login.isPending}>
              {login.isPending ? "Entrando..." : "Entrar"}
              {!login.isPending && <ArrowRight className="h-4 w-4" />}
            </Button>
          </form>
          <p className="mt-8 border-t pt-5 text-xs leading-5 text-muted-foreground">
            El acceso está protegido y vinculado a tu cuenta de FiscalCore.
          </p>
        </div>
      </section>
    </main>
  );
}
