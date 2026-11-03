import type { CurrentUser } from "@/lib/types";

/**
 * Base URL of the FastAPI backend as seen by the browser. Development uses
 * localhost; deployments set NEXT_PUBLIC_API_URL.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * The access token lives in memory only. A page reload restores the session
 * through the HttpOnly refresh cookie, so long-lived credentials are never
 * readable from JavaScript.
 */
let accessToken: string | null = null;

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;
  if (
    init.body !== undefined &&
    !isFormData &&
    !(init.body instanceof URLSearchParams) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken !== null) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  return fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
}

async function responseError(response: Response): Promise<ApiError> {
  let detail = `Request failed with status ${response.status}`;
  try {
    const body: unknown = await response.json();
    if (
      typeof body === "object" &&
      body !== null &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      detail = body.detail;
    }
  } catch {
    // Keep the generic message when the body is not JSON.
  }
  return new ApiError(detail, response.status);
}

/**
 * Send an API request with the current access token. A 401 triggers one
 * refresh attempt and a single retry, so callers never see an expired token.
 */
export async function apiRequest(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  let response = await send(path, init);
  if (response.status !== 401 || path === "/api/auth/login") {
    return response;
  }

  if (!(await refreshAccessToken())) {
    return response;
  }
  response = await send(path, init);
  return response;
}

/** Send a request and decode a JSON response, raising ``ApiError`` on failure. */
export async function apiJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await apiRequest(path, init);
  if (!response.ok) {
    throw await responseError(response);
  }
  return (await response.json()) as T;
}

/** Send a request and discard the body. */
export async function apiVoid(
  path: string,
  init: RequestInit = {},
): Promise<void> {
  const response = await apiRequest(path, init);
  if (!response.ok) {
    throw await responseError(response);
  }
}

/** Rotate the refresh cookie into a new in-memory access token. */
export async function refreshAccessToken(): Promise<boolean> {
  const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) {
    accessToken = null;
    return false;
  }

  const body = (await response.json()) as { access_token?: unknown };
  if (typeof body.access_token !== "string") {
    accessToken = null;
    return false;
  }
  accessToken = body.access_token;
  return true;
}

export async function loginRequest(
  email: string,
  password: string,
): Promise<void> {
  const response = await send("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw await responseError(response);
  }

  const body = (await response.json()) as { access_token?: unknown };
  if (typeof body.access_token !== "string") {
    throw new ApiError("Login response did not include an access token", 502);
  }
  accessToken = body.access_token;
}

export async function logoutRequest(): Promise<void> {
  try {
    await send("/api/auth/logout", { method: "POST" });
  } finally {
    accessToken = null;
  }
}

export async function fetchCurrentUser(): Promise<CurrentUser> {
  const response = await apiRequest("/api/auth/me");
  if (!response.ok) {
    throw await responseError(response);
  }
  return (await response.json()) as CurrentUser;
}
