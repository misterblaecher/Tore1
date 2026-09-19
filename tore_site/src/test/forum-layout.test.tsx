import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ForumLayout from "@/components/layout/ForumLayout";
import { apiFetch } from "@/lib/api";
import { ACCESS_TOKEN_KEY } from "@/lib/auth";
import { getMe } from "@/lib/session";
import { ForumWorkspace } from "@/lib/forum-navigation";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));
vi.mock("@/lib/session", () => ({ getMe: vi.fn() }));

const committees: ForumWorkspace[] = [
  { id: 1, slug: "embuscade", name: "L’Embuscade", type: "COMMITTEE", city: "Liège", logoUrl: "/embuscade.png", role: "PRESIDENT", canManage: true, canReadFinance: true },
  { id: 2, slug: "sources", name: "Cercle des Sources", type: "CIRCLE", city: "Namur", logoUrl: "/sources.png", role: "MEMBER", canManage: false, canReadFinance: false },
];

function Page() {
  const location = useLocation();
  return <main><h1>Page de test</h1><output data-testid="route">{location.pathname}{location.search}</output><Link to="/compte">Accéder au compte</Link></main>;
}
function openPage(path = "/forum") {
  return render(<MemoryRouter initialEntries={[path]}><Routes><Route element={<ForumLayout />}><Route path="*" element={<Page />} /></Route></Routes></MemoryRouter>);
}
function navigation() { return within(screen.getByRole("navigation", { name: "Navigation du Forum" })); }

describe("Forum shared navigation", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear(); sessionStorage.clear();
    sessionStorage.setItem(ACCESS_TOKEN_KEY, "test-session");
    vi.mocked(getMe).mockResolvedValue({ id: "user-1", display_name: "Thomas", avatar_url: "/thomas.png" });
    vi.mocked(apiFetch).mockResolvedValue({ items: committees });
  });
  afterEach(cleanup);

  it("shows the managed committee and its real logo on the Forum home", async () => {
    openPage();
    const selector = await screen.findByRole("button", { name: "Changer de structure" });
    await waitFor(() => expect(selector).toHaveTextContent("L’Embuscade"));
    expect(within(selector).getByRole("img")).toHaveAttribute("src", "/embuscade.png");
    expect(selector).toHaveTextContent("Comité · Liège");
    expect(navigation().getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/forum/structures/embuscade/dashboard");
    expect(screen.queryByText("Découvrir TORÈ")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: "Accéder au compte" }));
    await waitFor(() => expect(screen.getByTestId("route")).toHaveTextContent("/compte"));
    expect(navigation().getByRole("link", { name: "Documents" })).toHaveAttribute("href", "/forum/structures/embuscade/documents");
  });

  it("switches all committee links, logo and permissions together, and remembers the choice", async () => {
    openPage();
    const selector = screen.getByRole("button", { name: "Changer de structure" });
    await waitFor(() => expect(selector).toHaveTextContent("L’Embuscade"));
    fireEvent.keyDown(selector, { key: "Enter", code: "Enter" });
    fireEvent.click(await screen.findByRole("menuitem", { name: /Cercle des Sources/ }));
    await waitFor(() => expect(screen.getByTestId("route")).toHaveTextContent("/forum/structures/sources/dashboard"));
    expect(selector).toHaveTextContent("Cercle des Sources");
    expect(within(selector).getByRole("img")).toHaveAttribute("src", "/sources.png");
    expect(navigation().getByRole("link", { name: "Discussions" })).toHaveAttribute("href", "/forum/structures/sources/discussions");
    expect(navigation().queryByRole("link", { name: "Comptabilité" })).not.toBeInTheDocument();
    expect(navigation().getByText("Comptabilité").closest("[aria-disabled]")).toHaveAttribute("aria-disabled", "true");
    expect(screen.queryByRole("link", { name: "Créer un événement" })).not.toBeInTheDocument();
    await waitFor(() => expect(localStorage.getItem("tore.forum.structure.user-1")).toBe("sources"));
    cleanup();
    openPage("/forum/structures");
    await waitFor(() => expect(screen.getByRole("button", { name: "Changer de structure" })).toHaveTextContent("Cercle des Sources"));
  });

  it("uses the structure in a direct URL instead of a previously selected committee", async () => {
    localStorage.setItem("tore.forum.structure.user-1", "embuscade");
    openPage("/forum/structures/sources/members");
    await waitFor(() => expect(screen.getByRole("button", { name: "Changer de structure" })).toHaveTextContent("Cercle des Sources"));
    expect(navigation().getByRole("link", { name: "Membres" })).toHaveAttribute("aria-current", "page");
  });

  it("does not restore expired access from storage", async () => {
    localStorage.setItem("tore.forum.structure.user-1", "embuscade");
    vi.mocked(apiFetch).mockResolvedValue({ items: [] });
    openPage();
    await screen.findByText(/Aucun accès actif à un comité/);
    expect(navigation().queryByRole("link", { name: "Dashboard" })).not.toBeInTheDocument();
    expect(navigation().getByRole("link", { name: "Toutes les structures" })).toHaveAttribute("href", "/forum/structures");
    await waitFor(() => expect(localStorage.getItem("tore.forum.structure.user-1")).toBeNull());
  });

  it("keeps the public navigation for visitors without fetching private structures", () => {
    sessionStorage.removeItem(ACCESS_TOKEN_KEY);
    openPage("/forum/login");
    expect(navigation().getByRole("link", { name: "Accueil du Forum" })).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
    expect(screen.getByText(/Connectez-vous pour retrouver les rubriques/)).toBeInTheDocument();
  });

  it("sends the topbar search to the structure-scoped global search", async () => {
    openPage();
    await screen.findByRole("button", { name: "Changer de structure" });
    fireEvent.change(screen.getByRole("textbox", { name: "Recherche globale" }), { target: { value: "Liège" } });
    fireEvent.click(screen.getByRole("button", { name: "Lancer la recherche" }));
    await waitFor(() => expect(vi.mocked(apiFetch).mock.calls.some(([path]) => String(path).includes("/forum/structures/embuscade/search?q=Li%C3%A8ge"))).toBe(true));
  });
});
