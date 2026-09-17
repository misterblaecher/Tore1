import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ForumArchivesPage from "@/pages/ForumArchives";
import { apiFetch } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  class MockApiError extends Error { status?: number; constructor(message: string, status?: number) { super(message); this.status = status; } }
  return { apiFetch: vi.fn(), ApiError: MockApiError };
});

const archiveData = {
  structure: { id: 1, slug: "embuscade", name: "L’Embuscade" },
  filters: {
    years: [2026, 2025],
    mandates: [{ id: 8, label: "Bureau 2025-2026", role: "PRESIDENT", status: "LEFT", startsAt: "2025-09-01T00:00:00", endsAt: "2026-06-30T00:00:00", isAlumni: true, member: { displayName: "Alice" } }],
    events: [{ id: 42, name: "Bal 2026", startsAt: "2026-03-12T20:00:00" }],
    categories: ["ALBUM", "DOCUMENT", "EVENT", "PAGE"],
  },
  summary: { total: 4, filtered: 4, pastEvents: 1, officeTerms: 1 },
  items: [
    { key: "document:4", category: "DOCUMENT", objectId: 4, title: "PV de passation", subtitle: "Bureau", archivedAt: "2026-06-30T10:00:00", year: 2026, mandate: { id: 8, label: "Bureau 2025-2026", role: "PRESIDENT", status: "LEFT", startsAt: "2025-09-01T00:00:00", endsAt: "2026-06-30T00:00:00", isAlumni: true }, event: null, target: "/forum/structures/embuscade/documents", restorePath: "/forum/structures/embuscade/archives/documents/4/restore" },
    { key: "event:42", category: "EVENT", objectId: 42, title: "Bal 2026", subtitle: "Le Carré", archivedAt: "2026-03-13T02:00:00", year: 2026, mandate: null, event: { id: 42, name: "Bal 2026", startsAt: "2026-03-12T20:00:00" }, target: "/forum/structures/embuscade/events/42", restorePath: null },
  ],
  officeHistory: [{ id: 8, label: "Bureau 2025-2026", role: "PRESIDENT", status: "LEFT", startsAt: "2025-09-01T00:00:00", endsAt: "2026-06-30T00:00:00", isAlumni: true, member: { displayName: "Alice" } }],
  pastEvents: [{ id: 42, name: "Bal 2026", startsAt: "2026-03-12T20:00:00", venue: "Le Carré" }],
  links: { members: "/forum/structures/embuscade/members", alumni: "/forum/structures/embuscade/members?include_archived=true" },
};

function mount() {
  return render(<MemoryRouter initialEntries={["/forum/structures/embuscade/archives"]}><Routes><Route path="/forum/structures/:slug/archives" element={<ForumArchivesPage />} /></Routes></MemoryRouter>);
}

describe("Forum structured archives", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(apiFetch).mockImplementation(async (_path: string, init?: RequestInit) => init?.method === "POST" ? ({ ok: true } as never) : (archiveData as never));
  });
  afterEach(cleanup);

  it("renders the heritage timeline, office history and past events from the structured read model", async () => {
    mount();
    expect(await screen.findByRole("heading", { name: "Archives de L’Embuscade" })).toBeInTheDocument();
    expect(screen.getByText("PV de passation")).toBeInTheDocument();
    expect(screen.getAllByText("Bureau 2025-2026").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Bal 2026").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Voir les alumni" })).toHaveAttribute("href", "/forum/structures/embuscade/members?include_archived=true");
  });

  it("sends year, mandate, event and category filters to the backend", async () => {
    mount(); await screen.findByText("PV de passation");
    fireEvent.change(screen.getByLabelText("Année"), { target: { value: "2026" } });
    fireEvent.change(screen.getByLabelText("Mandat"), { target: { value: "Bureau 2025-2026" } });
    fireEvent.change(screen.getByLabelText("Event"), { target: { value: "42" } });
    fireEvent.change(screen.getByLabelText("Catégorie"), { target: { value: "DOCUMENT" } });
    fireEvent.change(screen.getByLabelText("Recherche"), { target: { value: "passation" } });
    fireEvent.submit(screen.getByRole("button", { name: "Filtrer" }).closest("form")!);
    await waitFor(() => expect(vi.mocked(apiFetch).mock.calls.some(([calledPath]) => String(calledPath).includes("?"))).toBe(true));
    const path = String([...vi.mocked(apiFetch).mock.calls].reverse().find(([calledPath]) => String(calledPath).includes("?"))?.[0]);
    const params = new URL(path, "https://tore.test").searchParams;
    expect(Object.fromEntries(params)).toEqual({ search: "passation", year: "2026", mandate: "Bureau 2025-2026", event_id: "42", category: "DOCUMENT" });
  });

  it("only exposes restore when the backend supplies a capability-backed restore path", async () => {
    mount(); await screen.findByText("PV de passation");
    const restore = screen.getByRole("button", { name: "Restaurer" });
    fireEvent.click(restore);
    await waitFor(() => expect(vi.mocked(apiFetch)).toHaveBeenCalledWith("/forum/structures/embuscade/archives/documents/4/restore", expect.objectContaining({ method: "POST" })));
    expect(screen.getAllByRole("button", { name: /Restaurer/ })).toHaveLength(1);
  });
});
