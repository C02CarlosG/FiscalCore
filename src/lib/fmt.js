export const fmtMXN = (n) =>
  new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", minimumFractionDigits: 2 }).format(n);

export const fmtN = (n) => new Intl.NumberFormat("es-MX").format(n);
