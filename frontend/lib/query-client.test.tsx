import { describe, expect, it, vi } from "vitest";
import { createQueryClient } from "./query-client";
import { ApiError } from "./api-client";
import { saveSession, getToken } from "./auth";
import type { LoginResponse } from "@/types/api";

const loginResponse: LoginResponse = {
  access_token: "token-123",
  token_type: "bearer",
  user_id: "u1",
  email: "test@example.com",
  nombre: "Test",
  empresas: [],
};

describe("createQueryClient", () => {
  it("clears the session and calls onUnauthorized on a 401 ApiError", async () => {
    saveSession(loginResponse);
    const onUnauthorized = vi.fn();
    const queryClient = createQueryClient(onUnauthorized);

    await queryClient
      .fetchQuery({
        queryKey: ["boom"],
        queryFn: () => {
          throw new ApiError(401, "no autorizado");
        },
      })
      .catch(() => undefined);

    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(getToken()).toBeNull();
  });

  it("does not call onUnauthorized for non-401 errors", async () => {
    const onUnauthorized = vi.fn();
    const queryClient = createQueryClient(onUnauthorized);

    await queryClient
      .fetchQuery({
        queryKey: ["boom-500"],
        queryFn: () => {
          throw new ApiError(500, "error de servidor");
        },
      })
      .catch(() => undefined);

    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});

describe("createQueryClient mutations", () => {
  it("clears the session and calls onUnauthorized on a 401 ApiError from a mutation", async () => {
    saveSession(loginResponse);
    const onUnauthorized = vi.fn();
    const queryClient = createQueryClient(onUnauthorized);

    const mutation = queryClient.getMutationCache().build(queryClient, {
      mutationFn: () => {
        throw new ApiError(401, "no autorizado");
      },
    });

    await mutation.execute(undefined).catch(() => undefined);

    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(getToken()).toBeNull();
  });

  it("does not call onUnauthorized for non-401 mutation errors", async () => {
    const onUnauthorized = vi.fn();
    const queryClient = createQueryClient(onUnauthorized);

    const mutation = queryClient.getMutationCache().build(queryClient, {
      mutationFn: () => {
        throw new ApiError(500, "error de servidor");
      },
    });

    await mutation.execute(undefined).catch(() => undefined);

    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
