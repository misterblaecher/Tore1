import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ForumEventPage from "@/pages/ForumEvent";
import ForumPublicPage from "@/pages/ForumPublic";

const publicEventPayload = {
  id: 42,
  slug: "recap-night-42",
  canonicalPath: "/forum/events/recap-night-42",
  title: "Recap Night",
  coverUrl: "https://images.example/cover.jpg",
  startsAt: "2026-09-12T20:00:00",
  endsAt: "2026-09-13T02:00:00",
  venue: "Le Carré",
  address: "Rue des Dominicains",
  city: "Liège",
  description: "La page publique de la soirée.",
  organizer: { id: 7, name: "Cercle TORÈ", slug: "cercle-tore", type: "CIRCLE" },
  cohosts: [{ id: 8, name: "Comité Ami", slug: "comite-ami", type: "COMMITTEE" }],
  structures: [],
  capacity: 500,
  entryPriceCents: 500,
  currency: "EUR",
  appCtaPath: "/rejoindre?event=42",
  appDeepLink: "tore://event/42",
  lifecycleStatus: "RECAP_PUBLISHED",
  recap: {
    status: "RECAP_PUBLISHED",
    summary: "Une édition mémorable.",
    stats: [{ label: "Entrées", value: "420" }],
    album: null,
    publishedAt: "2026-09-13T10:00:00",
    previousEdition: null,
    nextEdition: null,
  },
};

describe("Forum public event route", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  afterEach(() => cleanup());

  it("renders the canonical /forum/events/:slug page and keeps the app deep-link secondary CTA", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(publicEventPayload), { status: 200, headers: { "Content-Type": "application/json" } }),
    );

    render(
      <MemoryRouter initialEntries={["/forum/events/recap-night-42"]}>
        <Routes>
          <Route path="/forum/events/:slug" element={<ForumEventPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByRole("heading", { name: "Recap Night" })).toBeInTheDocument());
    expect(screen.getAllByText("Le Carré · Rue des Dominicains · Liège").length).toBeGreaterThan(0);
    expect(screen.getByText("Une édition mémorable.")).toBeInTheDocument();
    expect(screen.getByText("420")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Continuer dans TORÈ/i })).toHaveAttribute("href", "/rejoindre?event=42");
    expect(screen.getByRole("link", { name: /Ouvrir l’app/i })).toHaveAttribute("href", "tore://event/42");
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/forum/events/recap-night-42"), expect.anything());
  });

  it("links Structure events to their canonical page instead of keeping them as an inline-only detail", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        structure: {
          name: "Cercle TORÈ",
          slug: "cercle-tore",
          type: "CIRCLE",
          city: "Liège",
        },
        visibility: { page: "PUBLIC", events: "PUBLIC" },
        events: [{
          id: 42,
          name: "Recap Night",
          startsAt: "2026-09-20T20:00:00",
          venue: "Le Carré",
          description: "Soirée publique",
        }],
        members: [],
        albums: [],
        pages: [],
        stats: null,
      }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );

    render(
      <MemoryRouter initialEntries={["/forum/structures/cercle-tore"]}>
        <Routes>
          <Route path="/forum/structures/:slug" element={<ForumPublicPage />} />
        </Routes>
      </MemoryRouter>,
    );

    const eventLink = await screen.findByRole("link", { name: /Recap Night/i });
    expect(eventLink).toHaveAttribute("href", "/forum/events/recap-night-42");
  });
});
