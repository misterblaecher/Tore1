import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ForumPage from "@/pages/Forum";

describe("Forum structure directory", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("renders structures returned by the backend", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(new Response(JSON.stringify({
      items: [{ id: 7, slug: "cercle-des-sources", name: "Cercle des Sources", type: "CIRCLE", city: "Liège", description: "Une structure active", memberCount: 12 }],
    }), { status: 200, headers: { "Content-Type": "application/json" } }));

    render(<MemoryRouter><ForumPage /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText("Cercle des Sources")).toBeInTheDocument());
    expect(screen.getByText("12 membres")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/forum/structures"), expect.anything());
  });

  it("shows an empty state when no public structure is returned", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response(JSON.stringify({ items: [] }), { status: 200 }));

    render(<MemoryRouter><ForumPage /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText("Aucune structure publique ne correspond à votre recherche.")).toBeInTheDocument());
  });
});
