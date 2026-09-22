"use client";

import { useParams } from "next/navigation";
import { CfdiUploadForm } from "@/components/ingesta/CfdiUploadForm";
import { BancoUploadForm } from "@/components/ingesta/BancoUploadForm";

export default function IngestaPage() {
  const params = useParams<{ empresaId: string }>();

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Ingesta</h1>
      <CfdiUploadForm empresaId={params.empresaId} />
      <BancoUploadForm empresaId={params.empresaId} />
    </main>
  );
}
