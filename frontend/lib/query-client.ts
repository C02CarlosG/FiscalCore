import { QueryCache, QueryClient } from "@tanstack/react-query";
import { ApiError } from "./api-client";
import { clearSession } from "./auth";

export function createQueryClient(onUnauthorized: () => void): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearSession();
          onUnauthorized();
        }
      },
    }),
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
    },
  });
}
