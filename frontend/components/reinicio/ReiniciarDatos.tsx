"use client";

import { FormEvent, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/shared/LoadingState";
import { useUsuariosEmpresa } from "@/hooks/useCuenta";
import { useConfirmarReinicio, usePrevisualizarReinicio } from "@/hooks/useReinicio";
import { ApiError } from "@/lib/api-client";
import { formatearInstante } from "@/lib/formato";
import { ETIQUETA_TABLA, type ResultadoReinicio, type VistaPreviaReinicio } from "./tipos";

const ENTERO = new Intl.NumberFormat("es-MX");
const mensajeDe = (err: unknown, otro: string) => (err instanceof ApiError ? err.message : otro);

function Conteos({ conteos, titulo }: { conteos: Record<string, number>; titulo: string }) {
  return (
    <table aria-label={titulo} className="w-full text-sm">
      <tbody className="divide-y divide-border">
        {Object.entries(ETIQUETA_TABLA).map(([tabla, etiqueta]) => (
          <tr key={tabla}>
            <td className="py-1.5">{etiqueta}</td>
            <td className="py-1.5 text-right font-medium">{ENTERO.format(conteos[tabla] ?? 0)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * «Reiniciar datos»: borra los datos operativos de la empresa con doble confirmación (vista
 * previa con token de un solo uso, frase con el RFC y contraseña). Solo administradores.
 */
export function ReiniciarDatos({ empresaId }: { empresaId: string }) {
  const usuarios = useUsuariosEmpresa(empresaId);
  const previsualizar = usePrevisualizarReinicio(empresaId);
  const confirmar = useConfirmarReinicio(empresaId);
  const [vista, setVista] = useState<VistaPreviaReinicio | null>(null);
  const [frase, setFrase] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ResultadoReinicio | null>(null);

  if (usuarios.isLoading) return <LoadingState label="Consultando permisos" />;
  if (!usuarios.data?.puede_administrar) {
    return (
      <p className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">
        Solo un administrador de la empresa puede reiniciar sus datos.
      </p>
    );
  }

  async function handleVista() {
    setError(null);
    setResultado(null);
    try {
      setVista(await previsualizar.mutateAsync());
      setFrase("");
      setContrasena("");
    } catch (err) {
      setError(mensajeDe(err, "No se pudo calcular qué se borraría"));
    }
  }

  async function handleConfirmar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!vista) return;
    setError(null);
    try {
      setResultado(await confirmar.mutateAsync({ token: vista.token, frase, contrasena }));
      setVista(null);
    } catch (err) {
      setError(mensajeDe(err, "No se pudo reiniciar"));
    } finally {
      setContrasena("");
    }
  }

  return (
    <Card>
      <CardHeader className="px-5 py-5 sm:px-6">
        <CardTitle className="font-display text-base">Reiniciar datos de la empresa</CardTitle>
        <CardDescription>
          Borra los CFDI, pagos, movimientos bancarios, conciliaciones, ajustes y DIOT de esta empresa para volver a
          descargarlos o cargarlos. Se conservan la empresa, sus usuarios, la e.firma, la configuración, los
          documentos fiscales, las declaraciones, los proveedores y la auditoría. No se puede deshacer.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5 px-5 pb-5 sm:px-6">
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {resultado && (
          <div role="status" className="space-y-2 rounded-md border border-border p-4 text-sm">
            <p className="font-semibold">Datos reiniciados.</p>
            <Conteos conteos={resultado.borrados} titulo="Registros borrados" />
            {resultado.sincronizacion_pausada && (
              <p>La descarga automática del SAT quedó pausada: reactívala en «Conexión SAT» cuando quieras volver a descargar.</p>
            )}
          </div>
        )}
        {!vista ? (
          <Button type="button" variant="outline" disabled={previsualizar.isPending} onClick={handleVista}>
            Ver qué se borraría
          </Button>
        ) : (
          <form aria-label="Confirmar reinicio" onSubmit={handleConfirmar} className="space-y-4" noValidate>
            <Conteos conteos={vista.conteos} titulo="Registros que se borrarán" />
            <p className="flex items-start gap-2 rounded-md border border-destructive/40 p-3 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" />
              Esta acción borra {ENTERO.format(vista.total_cfdi)} CFDI y todo lo que depende de ellos. Para confirmar,
              escribe «{vista.frase}» y tu contraseña antes de las {formatearInstante(vista.expira_en)}.
            </p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="reinicio-frase">Frase de confirmación</Label>
                <Input id="reinicio-frase" autoComplete="off" value={frase} placeholder={vista.frase}
                       onChange={(e) => setFrase(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reinicio-contrasena">Tu contraseña</Label>
                <Input id="reinicio-contrasena" type="password" autoComplete="current-password" value={contrasena}
                       onChange={(e) => setContrasena(e.target.value)} />
              </div>
            </div>
            <div className="flex gap-2">
              <Button type="submit" variant="destructive"
                      disabled={confirmar.isPending || frase.trim() !== vista.frase || !contrasena}>
                Reiniciar datos
              </Button>
              <Button type="button" variant="outline" onClick={() => setVista(null)}>
                Cancelar
              </Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
