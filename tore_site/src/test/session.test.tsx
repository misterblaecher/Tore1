import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, webLogout } from "@/lib/api";
import { clearToken, getCachedMe, getToken, setCachedMe, setToken } from "@/lib/auth";
import { getMe } from "@/lib/session";
import ProtectedRoute from "@/components/ProtectedRoute";

describe("Account session resilience", () => {
  beforeEach(() => { clearToken(); });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); clearToken(); });
  it("preserves the session on network or service failure and offers retry", async () => {
    setToken("session-a");
    const fetcher = vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(new Response(JSON.stringify({ id: "a", display_name: "Alice" })));
    render(<MemoryRouter><ProtectedRoute><p>Espace privé chargé</p></ProtectedRoute></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de vérifier votre session");
    expect(getToken()).toBe("session-a");
    fireEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(await screen.findByText("Espace privé chargé")).toBeInTheDocument();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it("does not reuse one account profile after switching tokens", async () => {
    setToken("session-a"); setCachedMe({ id: "a", display_name: "Alice" });
    setToken("session-b");
    expect(getCachedMe()).toBeNull();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ id: "b", display_name: "Bob" })));
    expect((await getMe()).id).toBe("b");
  });
  it("does not clear the new account when an old request returns 401", async () => {
    setToken("session-a");
    let complete!: (response: Response) => void;
    vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(resolve => { complete = resolve; }));
    const request = apiFetch("/me/profile");
    setToken("session-b"); complete(new Response("{}", { status: 401 }));
    await expect(request).rejects.toMatchObject({ status: 401 });
    expect(getToken()).toBe("session-b");
  });
  it("does not clear local credentials when server logout fails", async () => {
    setToken("session-a");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 503 }));
    await expect(webLogout()).rejects.toMatchObject({ status: 503 });
    expect(getToken()).toBe("session-a");
  });

  it("clears credentials only after successful server logout", async () => {
    setToken("session-a");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await expect(webLogout()).resolves.toBeUndefined();
    expect(getToken()).toBeNull();
  });

  it("clears only expired credentials and accepts successful empty responses", async () => {
    setToken("session-a");
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("{}", { status: 401 }))
      .mockResolvedValueOnce(new Response("{}", { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(getMe(true)).rejects.toMatchObject({ status: 401 });
    expect(getToken()).toBeNull();
    await expect(apiFetch("/resource", { method: "DELETE" })).resolves.toBeUndefined();
  });
});
