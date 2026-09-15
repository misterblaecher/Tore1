import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StructurePortalSettings from "@/pages/StructurePortalSettings";

const settings = {
  id: 7,
  slug: "embuscade",
  name: "L’Embuscade",
  type: "COMMITTEE",
  description: "Comité étudiant",
  city: "Liège",
  logoUrl: null,
  bannerUrl: null,
  primaryColor: "#BA1733",
  secondaryColor: "#F4C430",
};

function renderSettings() {
  return render(<MemoryRouter><StructurePortalSettings slug="embuscade" /></MemoryRouter>);
}

describe("StructurePortalSettings", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:preview") });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    vi.spyOn(global, "fetch").mockImplementation(async (_input, init) => {
      if (init?.method === "PATCH") return new Response(JSON.stringify(settings), { status: 200, headers: { "Content-Type": "application/json" } });
      return new Response(JSON.stringify(settings), { status: 200, headers: { "Content-Type": "application/json" } });
    });
  });

  it("shows upload, preview/crop controls and the legacy URL importer", async () => {
    renderSettings();
    await waitFor(() => expect(screen.getByText("Logo, bannière & branding")).toBeInTheDocument());

    expect(screen.getByLabelText("Importer un logo")).toBeInTheDocument();
    expect(screen.getByLabelText("Importer un bannière")).toBeInTheDocument();
    expect(screen.getAllByText("Importer depuis une URL")).toHaveLength(2);

    const logo = new File([new Uint8Array([1, 2, 3])], "logo.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Importer un logo"), { target: { files: [logo] } });
    expect(screen.getByAltText("Aperçu logo")).toHaveAttribute("src", "blob:preview");
    expect(screen.getByLabelText("Zoom logo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Recadrer et enregistrer/i })).toBeInTheDocument();
  });

  it("validates HEX values and falls back to the TORÈ accent when WCAG contrast is insufficient", async () => {
    renderSettings();
    await waitFor(() => expect(screen.getByLabelText("Couleur secondaire (HEX)")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Couleur secondaire (HEX)"), { target: { value: "#111111" } });
    expect(screen.getByText(/l’accent public utilise automatiquement le jaune TORÈ/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Couleur primaire (HEX)"), { target: { value: "#12" } });
    expect(screen.getByText(/Format HEX attendu/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Enregistrer les couleurs/i })).toBeDisabled();
  });

  it("updates the live preview before saving", async () => {
    renderSettings();
    await waitFor(() => expect(screen.getByTestId("branding-preview-button")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Couleur primaire (HEX)"), { target: { value: "#0055AA" } });
    expect(screen.getByTestId("branding-preview-button")).toHaveStyle({ background: "#0055AA" });
  });
});
