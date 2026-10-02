import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
      <AlertCircle className="mt-0.5 h-4 w-4 flex-none" />
      <div className="space-y-2">
        <p className="font-medium">{message}</p>
      {onRetry && (
        <Button type="button" onClick={onRetry} variant="outline" size="sm" className="border-destructive/30 text-destructive hover:bg-destructive/10">
          Reintentar
        </Button>
      )}
      </div>
    </div>
  );
}
