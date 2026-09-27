import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api";

describe("ApiError", () => {
  it("creates an error with status and code", () => {
    const error = new ApiError("Session expired", 401, "UNAUTHORIZED");
    expect(error.message).toBe("Session expired");
    expect(error.status).toBe(401);
    expect(error.code).toBe("UNAUTHORIZED");
    expect(error.name).toBe("ApiError");
  });

  it("creates an error without code", () => {
    const error = new ApiError("Something went wrong", 500);
    expect(error.status).toBe(500);
    expect(error.code).toBeUndefined();
  });
});
