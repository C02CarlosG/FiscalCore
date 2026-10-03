import { redirect } from "next/navigation";

// El Visor SAT desapareció: "Emitidos" y "Recibidos" cubren todos los tipos.
export default function CfdiIndexPage({ params }: { params: { empresaId: string } }) {
  redirect(`/empresas/${params.empresaId}/cfdi/emitidos`);
}
