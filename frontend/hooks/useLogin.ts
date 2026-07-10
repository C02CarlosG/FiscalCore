"use client";

import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { saveSession } from "@/lib/auth";
import type { LoginResponse } from "@/types/api";

interface LoginInput {
  email: string;
  password: string;
}

export function useLogin() {
  return useMutation({
    mutationFn: async (input: LoginInput) => {
      const response = await apiFetch<LoginResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(input),
      });
      saveSession(response);
      return response;
    },
  });
}
