import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ForumPage from "@/pages/Forum";

const structure = {
  id: 7,
  slug: "cercle-des-sources",
  name: "Cercle des Sources",
  type: "CIRCLE",
  city: "Liège",
  description: "Une structure active",
  logoUrl: "https://example.test/logo.png",
  bannerUrl: "https://example.test/banner.jpg",
  primaryColor: "#123456",
  secondaryColor: "#fedcba",
  memberCount: 12,
  nextPublicEvent: {
    id: 19,
    name: "Bal des Sources",
    startsAt: "2030-10-18T20:00:00Z",
    venue: "Salle académique",
    city: "Liège",
  },
};

describe("Forum structure directory", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("renders branded cards and the next public event returned by the backend", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(new Response(JSON.stringify({
      items: [structure], page: 1, pageSize: 12, total: 1, totalPages: 1,
    }), { status: 200, headers: { "Content-Type": "application/json" } }));

    render(<MemoryRouter><ForumPage /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText("Cercle des Sources")).toBeInTheDocument());
    expect(screen.getByText("12 membres")).toBeInTheDocument();
    expect(screen.getByText("Bal des Sources")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Logo de Cercle des Sources" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/forum/structures"), expect.anything());
  });

  it("sends name, type, city and pagination filters to the backend", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(new Response(JSON.stringify({
      items: [], page: 2, pageSize: 12, total: 0, totalPages: 0,
    }), { status: 200, headers: { "Content-Type": "application/json" } }));

    render(<MemoryRouter initialEntries={["/forum/structures?q=Sources&type=CIRCLE&city=Li%C3%A8ge&page=2"]}><ForumPage /></MemoryRouter>);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("q=Sources");
    expect(url).toContain("type=CIRCLE");
    expect(url).toContain("city=Li%C3%A8ge");
    expect(url).toContain("page=2");
    expect(url).toContain("page_size=12");
    expect(screen.getByRole("button", { name: "Comité" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cercle" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ordre" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Association" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Partenaire" })).toBeInTheDocument();
  });

  it("requests the next server page instead of filtering a full client-side dataset", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(new Response(JSON.stringify({
      items: [structure], page: 1, pageSize: 12, total: 25, totalPages: 3,
    }), { status: 200, headers: { "Content-Type": "application/json" } }));

    render(<MemoryRouter><ForumPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole("button", { name: "Page suivante" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Page suivante" }));

    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(1));
    const url = String(fetchMock.mock.calls[fetchMock.mock.calls.length - 1][0]);
    expect(url).toContain("page=2");
    expect(url).toContain("page_size=12");
  });

  it("shows a dedicated loading state", () => {
    vi.spyOn(global, "fetch").mockImplementation(() => new Promise<Response>(() => {}));
    render(<MemoryRouter><ForumPage /></MemoryRouter>);
    expect(screen.getByLabelText("Chargement des structures")).toBeInTheDocument();
  });

  it("shows retry and empty states", async () => {
    const fetchMock = vi.spyOn(global, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "temporary" }), { status: 503, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [], page: 1, pageSize: 12, total: 0, totalPages: 0 }), { status: 200, headers: { "Content-Type": "application/json" } }));

    render(<MemoryRouter><ForumPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("Le répertoire n’a pas pu être chargé.")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    await waitFor(() => expect(screen.getByText("Aucune structure publique ne correspond à votre recherche.")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
