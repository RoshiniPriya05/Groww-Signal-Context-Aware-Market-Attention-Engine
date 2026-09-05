import axios, { AxiosError, AxiosInstance } from "axios";

const DEFAULT_API_URL = "http://localhost:8000/api/v1";
export const DELAYED_BANNER_TEXT = "⚠ DELAYED";

export type AttentionSignal = {
  symbol: string;
  company_name: string;
  price: number;
  price_delta_pct: number;
  mci_score: number;
  priority: string;
  breakdown: Record<string, number>;
  summary: string;
};

export type AttentionWatchlistResponse = {
  user_id: string;
  time_away: string;
  critical_count: number;
  moderate_count: number;
  unchanged_count: number;
  stocks: AttentionSignal[];
};

export type ChangeStory = {
  headline: string;
  why_it_matters: string;
  what_changed_summary: string[];
  action_context: string;
  grounding?: {
    source: string;
    numbers_from_payload_only: boolean;
  };
};

export type ChangeStoryResponse = {
  headline: string;
  why_it_matters: string;
  what_changed: string[];
  what_changed_summary?: string[];
  what_didnt: string[];
  ai_explanation: string;
};

export type CatchMeUpResponse = {
  user_id?: string;
  summary?: string;
  critical_changes?: Array<{
    symbol: string;
    headline?: string;
    reason?: string;
    mci?: number;
    change?: string;
  }>;
  [key: string]: unknown;
};

export class ApiError extends Error {
  readonly status?: number;
  readonly code: string;
  readonly isDelayed: boolean;
  readonly userMessage: string;

  constructor(
    message: string,
    options: {
      status?: number;
      code: string;
      isDelayed: boolean;
      userMessage: string;
    },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.isDelayed = options.isDelayed;
    this.userMessage = options.userMessage;
  }
}

function getApiBaseUrl() {
  const configuredUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!configuredUrl) return DEFAULT_API_URL;

  const normalizedUrl = configuredUrl.replace(/\/$/, "");
  return normalizedUrl.endsWith("/api/v1")
    ? normalizedUrl
    : `${normalizedUrl}/api/v1`;
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 5000,
  headers: {
    Accept: "application/json",
    "Content-Type": "application/json",
  },
});

function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;

  if (error instanceof AxiosError) {
    const status = error.response?.status;
    const responseDetail = error.response?.data?.detail;
    const isDelayed = !error.response || (status !== undefined && status >= 500);

    return new ApiError(error.message, {
      status,
      code: error.code ?? (isDelayed ? "BACKEND_UNREACHABLE" : "API_ERROR"),
      isDelayed,
      userMessage: isDelayed
        ? DELAYED_BANNER_TEXT
        : typeof responseDetail === "string"
          ? responseDetail
          : "The request could not be completed.",
    });
  }

  return new ApiError("Unexpected API error", {
    code: "UNKNOWN_API_ERROR",
    isDelayed: true,
    userMessage: DELAYED_BANNER_TEXT,
  });
}

async function request<T>(requestPromise: Promise<{ data: T }>): Promise<T> {
  try {
    const response = await requestPromise;
    return response.data;
  } catch (error) {
    throw toApiError(error);
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function isDelayedApiError(error: unknown): error is ApiError {
  return isApiError(error) && error.isDelayed;
}

export function fetchAttentionWatchlist(userId: string) {
  return request<AttentionWatchlistResponse>(
    apiClient.get("/watchlist/attention", {
      params: { user_id: userId },
    }),
  );
}

export function fetchChangeStory(symbol: string) {
  return request<ChangeStoryResponse>(
    apiClient.get(`/watchlist/story/${encodeURIComponent(symbol)}`),
  );
}

export function fetchCatchMeUp(userId: string) {
  return request<CatchMeUpResponse>(
    apiClient.get("/watchlist/summary", {
      params: { user_id: userId },
    }),
  );
}

export function registerNotificationToken(token: string) {
  return request<{ registered: boolean }>(
    apiClient.post("/notifications/register", { token }),
  );
}
