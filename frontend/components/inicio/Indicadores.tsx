import { ArrowDownRight, ArrowUpRight, Receipt, Wallet } from "lucide-react";
import { StatCard } from "@/components/shared/StatCard";
import { formatearMoneda } from "@/lib/formato";
import type { InicioResumen } from "@/types/api";

/** Ingresos y gastos netos del periodo y del ejercicio (lo facturado, sin IVA). */
export function Indicadores({ resumen }: { resumen: InicioResumen }) {
  const { ingresos, gastos } = resumen;

  return (
    <section aria-label="Ingresos y gastos" className="space-y-3">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Ingresos netos del periodo" value={formatearMoneda(ingresos.periodo.neto)} icon={ArrowUpRight} tone="ok" />
        <StatCard label="Ingresos netos del ejercicio" value={formatearMoneda(ingresos.acumulado.neto)} icon={Wallet} tone="ok" />
        <StatCard label="Gastos netos del periodo" value={formatearMoneda(gastos.periodo.neto)} icon={ArrowDownRight} tone="alto" />
        <StatCard label="Gastos netos del ejercicio" value={formatearMoneda(gastos.acumulado.neto)} icon={Receipt} tone="alto" />
      </div>
      <p className="text-xs text-muted-foreground">
        <span>{`${ingresos.periodo.cfdi} CFDI de ingreso y notas de crédito`}</span>
        {gastos.periodo.nomina > 0 && (
          <span>{` · Nómina del periodo: ${formatearMoneda(gastos.periodo.nomina)} (no incluida en los gastos netos)`}</span>
        )}
      </p>
    </section>
  );
}
