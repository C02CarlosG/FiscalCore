// src/lib/cfdiParser.js
import { NS4, NSTFD } from "./constants.js";

export function parseCFDI(xmlText, filename) {
  try {
    const doc = new DOMParser().parseFromString(xmlText, "application/xml");
    if (doc.querySelector("parsererror")) return null;
    const comp = doc.documentElement;
    const a  = (el, k) => el?.getAttribute(k) ?? "";
    const nf = (el, k) => parseFloat(el?.getAttribute(k) ?? "0") || 0;
    const emisor    = doc.getElementsByTagNameNS(NS4,   "Emisor")[0];
    const receptor  = doc.getElementsByTagNameNS(NS4,   "Receptor")[0];
    const tfd       = doc.getElementsByTagNameNS(NSTFD, "TimbreFiscalDigital")[0];
    const infGlobal = doc.getElementsByTagNameNS(NS4,   "InformacionGlobal")[0];
    const allImp    = [...doc.getElementsByTagNameNS(NS4, "Impuestos")];
    const rootImp   = allImp.find(el => el.parentNode === comp) ?? null;
    const traslados = rootImp
      ? [...rootImp.getElementsByTagNameNS(NS4,"Traslado")].filter(t=>a(t,"Impuesto")==="002"&&a(t,"TipoFactor")==="Tasa")
      : [];
    const iva16=traslados.reduce((s,t)=>s+nf(t,"Importe"),0);
    const baseIva16=traslados.reduce((s,t)=>s+nf(t,"Base"),0);
    const rets=rootImp?[...rootImp.getElementsByTagNameNS(NS4,"Retencion")]:[];
    const isrRet=rets.filter(r=>a(r,"Impuesto")==="001").reduce((s,r)=>s+nf(r,"Importe"),0);
    const ivaRet=rets.filter(r=>a(r,"Impuesto")==="002").reduce((s,r)=>s+nf(r,"Importe"),0);
    // CfdiRelacionados (anticipos, notas de crédito, etc.)
    const cfdiRelacionados = [];
    doc.querySelectorAll("CfdiRelacionados").forEach(nodo => {
      const tipo = nodo.getAttribute("TipoRelacion") ?? "";
      const uuids = [...nodo.querySelectorAll("CfdiRelacionado")]
        .map(r => r.getAttribute("UUID")).filter(Boolean);
      if (uuids.length) cfdiRelacionados.push({ tipo_relacion: tipo, uuids });
    });
    return {
      filename, tipo:a(comp,"TipoDeComprobante"), fecha:a(comp,"Fecha"),
      uuid:a(tfd,"UUID"), rfcEmisor:a(emisor,"Rfc"), nombreEmisor:a(emisor,"Nombre"),
      rfcReceptor:a(receptor,"Rfc"), nombreReceptor:a(receptor,"Nombre"),
      subtotal:nf(comp,"SubTotal"), total:nf(comp,"Total"), moneda:a(comp,"Moneda"),
      baseIva16, iva16, isrRet, ivaRet,
      metodoPago:a(comp,"MetodoPago"), formaPago:a(comp,"FormaPago"),
      esGlobal:!!infGlobal,
      globalPeriodicidad:a(infGlobal,"Periodicidad"),globalMeses:a(infGlobal,"Meses"),globalAno:a(infGlobal,"Año"),
      esPublicoGeneral:a(receptor,"Rfc")==="XAXX010101000",
      cfdiRelacionados,
    };
  } catch(_){ return null; }
}
