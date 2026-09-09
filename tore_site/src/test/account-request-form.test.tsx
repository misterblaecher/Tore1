import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const toastSpy = vi.fn();

vi.mock("@/hooks/use-toast", () => ({
  useToast: () => ({ toast: toastSpy }),
}));

describe("account request form", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    vi.stubEnv("VITE_API_URL", "https://api.tore.test");
  });

  const fillAndSubmit = async () => {
    const { default: Index } = await import("@/pages/Join");
    render(
      <MemoryRouter>
        <Index />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Nom"), { target: { value: "Alice" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "alice@tore.dev" } });
    fireEvent.change(screen.getByLabelText("Téléphone"), { target: { value: "+32470001122" } });
    fireEvent.change(screen.getByLabelText("Rôle"), { target: { value: "student" } });

    fireEvent.click(screen.getByRole("button", { name: "Demander un accès pro" }));
  };

  it("does not show error toast when request succeeds", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true, id: 42 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;

    await fillAndSubmit();

    await waitFor(() => {
      expect(screen.getByText("Demande envoyée (ID 42).")).toBeInTheDocument();
    });
    expect(toastSpy).toHaveBeenCalledWith(expect.objectContaining({ title: "Demande envoyée" }));
    expect(toastSpy).not.toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Erreur",
      }),
    );
  });

  it("shows retry-after seconds on 429", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Slow down", retry_after_seconds: 17 }), {
        status: 429,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;

    await fillAndSubmit();

    await waitFor(() => {
      expect(screen.getByText(/Réessaie dans 17 secondes/)).toBeInTheDocument();
    });
    expect(toastSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Erreur",
        description: expect.stringContaining("17 secondes"),
      }),
    );
  });
});
