import { Skeleton } from "@/components/ui/skeleton";

export function LoadingState({ label }: { label: string }) {
  return (
    <div role="status" aria-label={label} className="space-y-4 py-1">
      <span className="sr-only">{label}</span>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-28 rounded-md" />
        ))}
      </div>
      <Skeleton className="h-64 rounded-md" />
    </div>
  );
}