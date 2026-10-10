"use client";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Validacion } from "@/hooks/useCierre";
import { CheckCircle2, AlertCircle } from "lucide-react";

interface ModalValidacionesYCierreProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  validaciones: Validacion[];
  onConfirm: () => void;
  loading?: boolean;
}

export function ModalValidacionesYCierre({
  open,
  onOpenChange,
  validaciones,
  onConfirm,
  loading = false,
}: ModalValidacionesYCierreProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Confirmar cierre del período</DialogTitle>
          <DialogDescription>
            Revisa las validaciones antes de confirmar el cierre. Esta acción no se puede deshacer fácilmente.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2 py-4 max-h-96 overflow-y-auto">
          {validaciones.map((v) => (
            <div
              key={v.nombre}
              className={`rounded-md p-3 flex items-start gap-2 ${
                v.pasó
                  ? "bg-green-50 border border-green-200"
                  : v.bloquea
                    ? "bg-red-50 border border-red-200"
                    : "bg-amber-50 border border-amber-200"
              }`}
            >
              <div className="flex-shrink-0 pt-0.5">
                {v.pasó ? (
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-amber-600" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm">{v.nombre}</p>
                <p className="text-xs text-muted-foreground">{v.mensaje}</p>
              </div>
            </div>
          ))}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={loading}
          >
            Cancelar
          </Button>
          <Button
            type="button"
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? "Cerrando..." : "Cerrar período"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
