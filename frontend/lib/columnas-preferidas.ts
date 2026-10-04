// Orden y visibilidad de columnas: el catálogo del servidor dice qué existe y cómo se
// ve por defecto; la preferencia del usuario solo reordena y oculta. Por eso se
// resuelve en el cliente: una columna que ya no existe se ignora y una nueva aparece
// al final con su visibilidad por defecto.

export type ColumnaPreferida = { clave: string; visible: boolean };

type Catalogo = { clave: string; visible_por_defecto: boolean };

/** Todas las columnas del catálogo, en el orden del usuario, cada una con su visibilidad. */
export function resolverColumnas<T extends Catalogo>(
  catalogo: T[],
  preferencia: ColumnaPreferida[] | null | undefined,
): (T & { visible: boolean })[] {
  if (!preferencia) return catalogo.map((c) => ({ ...c, visible: c.visible_por_defecto }));

  const porClave = new Map(catalogo.map((c) => [c.clave, c]));
  const vistas = new Set<string>();
  const resultado: (T & { visible: boolean })[] = [];

  for (const { clave, visible } of preferencia) {
    const columna = porClave.get(clave);
    if (!columna || vistas.has(clave)) continue;
    vistas.add(clave);
    resultado.push({ ...columna, visible });
  }
  for (const columna of catalogo) {
    if (!vistas.has(columna.clave)) resultado.push({ ...columna, visible: columna.visible_por_defecto });
  }
  return resultado;
}

/** Solo las columnas visibles, en orden. */
export function columnasVisibles<T extends Catalogo>(
  catalogo: T[],
  preferencia: ColumnaPreferida[] | null | undefined,
): T[] {
  return resolverColumnas(catalogo, preferencia)
    .filter((c) => c.visible)
    .map(({ visible: _visible, ...columna }) => columna as unknown as T);
}
