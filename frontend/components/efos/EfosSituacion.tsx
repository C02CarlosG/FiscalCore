import { Badge } from "@/components/ui/badge";

const RIESGO: Record<string, "alto" | "critico" | "informativo"> = {
  Presunto: "alto",
  Definitivo: "critico",
  Desvirtuado: "informativo",
  "Sentencia Favorable": "informativo",
};

const VARIANTE = { critico: "destructive", alto: "default", informativo: "outline" } as const;

/** Insignia de la situación de un RFC en la lista 69-B (riesgo alto / crítico / informativo). */
export function EfosSituacion({ situacion }: { situacion: string | null | undefined }) {
  if (!situacion) return <span className="text-muted-foreground">—</span>;
  const riesgo = RIESGO[situacion] ?? "informativo";
  return (
    <Badge variant={VARIANTE[riesgo]} data-riesgo={riesgo}>
      {situacion}
    </Badge>
  );
}
