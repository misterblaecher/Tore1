import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ForumPublicPage from "@/pages/ForumPublic";
import { apiFetch } from "@/lib/api";
import type { PublicPortal } from "@/lib/structure-portal";
vi.mock("@/lib/api", async (importOriginal) => ({ ...await importOriginal<typeof import("@/lib/api")>(), apiFetch: vi.fn() }));

function payload(): PublicPortal {
  return {
    structure: { name: "Un cercle", slug: "un-cercle", type: "CIRCLE", websiteUrl: "javascript:alert(1)", portal: { about: "Présentation", hidden_blocks: ["gallery"] } },
    visibility: { description: "PUBLIC", events: "PUBLIC", members: "PRIVATE", albums: "PUBLIC", folklore: "PUBLIC", contact: "PUBLIC" },
    events: [{ id: 42, name: "Soirée du cercle", startsAt: "2027-01-01T19:00:00", description: "Programme public de la soirée" }],
    members: [], albums: [{ id: 1, title: "Album masqué" }], pages: [],
  };
}
function mount() { return render(<MemoryRouter initialEntries={["/forum/structures/un-cercle"]}><Routes><Route path="/forum/structures/:slug" element={<ForumPublicPage />} /></Routes></MemoryRouter>); }
describe("Structure public portal", () => {
  beforeEach(() => { vi.mocked(apiFetch).mockResolvedValue(payload()); });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  it("honors hidden blocks and private sections and rejects unsafe external URLs", async () => {
    mount();
    await screen.findByRole("heading", { name: "Un cercle" });
    expect(screen.queryByRole("heading", { name: "Galerie" })).not.toBeInTheDocument();
    expect(screen.queryByText("Album masqué")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Comité" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Site web/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Voir les événements" })).toHaveAttribute("href", "/forum/structures/un-cercle#events");
  });
  it("opens public event details and links to the supported app event route", async () => {
    mount();
    fireEvent.click(await screen.findByRole("button", { name: /Soirée du cercle/ }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Programme public de la soirée")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ouvrir la soirée dans TORÈ" })).toHaveAttribute("href", "tore://event/42");
    expect(screen.getByRole("link", { name: "Installer l’application" })).toHaveAttribute("href", "/rejoindre#beta");
  });
  it("keeps blocks private when their visibility is omitted", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ ...payload(), visibility: {} });
    mount();
    await screen.findByRole("heading", { name: "Un cercle" });
    expect(screen.queryByText("Présentation")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Soirée du cercle/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Informations pratiques" })).not.toBeInTheDocument();
  });
});
