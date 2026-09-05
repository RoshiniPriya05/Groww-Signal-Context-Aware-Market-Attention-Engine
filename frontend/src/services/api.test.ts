import { afterEach, describe, expect, it } from "vitest";
import { AxiosError, type InternalAxiosRequestConfig } from "axios";

import {
  DELAYED_BANNER_TEXT,
  apiClient,
  fetchAttentionWatchlist,
  isDelayedApiError,
} from "./api";

describe("watchlist API delayed-state handling", () => {
  const originalAdapter = apiClient.defaults.adapter;

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
  });

  it("converts a backend 500 into a delayed error without throwing an unhandled response", async () => {
    apiClient.defaults.adapter = async () => {
      throw new AxiosError("FastAPI unavailable", "ERR_BAD_RESPONSE", undefined, undefined, {
        status: 500,
        statusText: "Internal Server Error",
        headers: {},
        config: {} as InternalAxiosRequestConfig,
        data: { detail: "server unavailable" },
      });
    };

    const request = fetchAttentionWatchlist("demo-user");

    await expect(request).rejects.toMatchObject({
      isDelayed: true,
      userMessage: DELAYED_BANNER_TEXT,
    });

    try {
      await request;
    } catch (error) {
      if (!isDelayedApiError(error)) {
        throw new Error("Expected an ApiError marked as delayed");
      }
      expect(error.userMessage).toBe("⚠ DELAYED");
    }
  });
});
