export type PuntoTendencia = { periodo: string; score: number };

export type ScoreDelPeriodo = {
  score: number | null;
  /** Cambio contra el periodo anterior de la tendencia; null si no hay uno. */
  delta: { puntos: number; contra: string } | null;
};

/**
 * Score del periodo elegido. Antes el dashboard mostraba el último de la tendencia
 * sin importar el periodo: ver agosto enseñaba el score de septiembre.
 */
export function scoreDelPeriodo(tendencia: PuntoTendencia[], periodo: string): ScoreDelPeriodo {
  const ordenada = [...tendencia].sort((a, b) => a.periodo.localeCompare(b.periodo));
  const i = ordenada.findIndex((p) => p.periodo === periodo);
  if (i === -1) return { score: null, delta: null };

  const actual = ordenada[i];
  const anterior = i > 0 ? ordenada[i - 1] : null;
  return {
    score: actual.score,
    delta: anterior ? { puntos: actual.score - anterior.score, contra: anterior.periodo } : null,
  };
}
