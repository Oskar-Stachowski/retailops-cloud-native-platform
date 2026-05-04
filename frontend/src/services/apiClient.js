const DEFAULT_API_BASE_URL = "http://localhost:8000";

function readViteEnv() {
  try {
    return import.meta.env || {};
  } catch {
    return {};
  }
}

export function getConfiguredApiBaseUrl() {
  const viteEnv = readViteEnv();
  const fromVite = viteEnv.VITE_API_BASE_URL;
  const fromNode = globalThis.process?.env?.VITE_API_BASE_URL;

  return sanitizeBaseUrl(fromVite || fromNode || DEFAULT_API_BASE_URL);
}

export const API_BASE_URL = getConfiguredApiBaseUrl();

export class ApiError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = "ApiError";
    this.status = details.status;
    this.code = details.code;
    this.path = details.path;
    this.body = details.body;
  }
}

export function sanitizeBaseUrl(baseUrl) {
  if (!baseUrl || typeof baseUrl !== "string") {
    return DEFAULT_API_BASE_URL;
  }

  return baseUrl.replace(/\/+$/, "");
}

export function normalizeApiPath(path) {
  if (!path || typeof path !== "string") {
    throw new Error("API path must be a non-empty string.");
  }

  return path.startsWith("/") ? path : `/${path}`;
}

export function toApiUrl(path, baseUrl = API_BASE_URL) {
  return `${sanitizeBaseUrl(baseUrl)}${normalizeApiPath(path)}`;
}

async function parseResponseBody(response) {
  const text = await response.text();

  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function getApiErrorMessage(body, response) {
  if (body?.error?.message) {
    return body.error.message;
  }

  if (typeof body === "string" && body.trim()) {
    return body;
  }

  return `API request failed with HTTP ${response.status}.`;
}

function getApiErrorCode(body, response) {
  return body?.error?.code || `http_${response.status}`;
}

export async function apiGet(path, options = {}) {
  const url = toApiUrl(path, options.baseUrl);

  let response;

  try {
    response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
      signal: options.signal,
    });
  } catch (error) {
    throw new ApiError("Backend API is not reachable.", {
      code: "network_error",
      path,
      body: error,
    });
  }

  const body = await parseResponseBody(response);

  if (!response.ok) {
    throw new ApiError(getApiErrorMessage(body, response), {
      status: response.status,
      code: getApiErrorCode(body, response),
      path,
      body,
    });
  }

  return body;
}

export async function apiPost(path, body = {}, options = {}) {
  const url = toApiUrl(path, options.baseUrl);

  let response;

  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      body: JSON.stringify(body || {}),
      signal: options.signal,
    });
  } catch (error) {
    throw new ApiError("Backend API is not reachable.", {
      code: "network_error",
      path,
      body: error,
    });
  }

  const responseBody = await parseResponseBody(response);

  if (!response.ok) {
    throw new ApiError(getApiErrorMessage(responseBody, response), {
      status: response.status,
      code: getApiErrorCode(responseBody, response),
      path,
      body: responseBody,
    });
  }

  return responseBody;
}

export async function apiGetOptional(paths, options = {}) {
  const candidatePaths = Array.isArray(paths) ? paths : [paths];
  const errors = [];

  for (const path of candidatePaths) {
    try {
      const data = await apiGet(path, options);
      return {
        ok: true,
        path,
        data,
        error: null,
      };
    } catch (error) {
      errors.push(error);
    }
  }

  const lastError = errors.at(-1);

  return {
    ok: false,
    path: candidatePaths.join(" | "),
    data: null,
    error: lastError || new ApiError("No API path was tested."),
  };
}
