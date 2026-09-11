import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import StructureDiscussions from "@/components/StructureDiscussions";
import { apiFetch } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));
const feed = {
  categories: [{ id: 1, name: "Salons internes" }],
  channels: [{ id: 1, name: "Bureau", categoryId: 1, visibility: "OFFICE" }, { id: 2, name: "Bar", categoryId: 1, visibility: "STRUCTURE_MEMBERS" }],
  posts: [{ id: 10, channelId: 1, channelName: "Bureau", title: "Ordre du jour", body: "Préparer la passation", authorName: "Alice", authorId: "alice", createdAt: "2026-09-09T12:00:00", pinned: true, documents: [], reactions: [] }],
};
function mount(manager = true) { return render(<MemoryRouter><StructureDiscussions slug="exemple" canManage={manager} /></MemoryRouter>); }
describe("Discussions workspace", () => {
  beforeEach(() => { vi.mocked(apiFetch).mockImplementation(async (path, init) => {
    if (init?.method) return { id: 3 };
    if (String(path).endsWith("/members")) return { items: [{ id: 1, userId: "alice", displayName: "Alice", role: "PRESIDENT", status: "ACTIVE" }] };
    if (String(path).endsWith("/documents")) return { items: [] };
    return feed;
  }); });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  it("opens Bureau, keeps channel drafts and sends a structure-scoped message", async () => {
    mount();
    await screen.findByRole("heading", { name: "Bureau", level: 1 });
    fireEvent.change(screen.getByRole("textbox", { name: "Message dans Bureau" }), { target: { value: "Mon brouillon" } });
    fireEvent.click(screen.getByRole("button", { name: "Bar" }));
    expect(screen.getByRole("textbox", { name: "Message dans Bar" })).toHaveValue("");
    fireEvent.click(screen.getByRole("button", { name: "Bureau" }));
    expect(screen.getByRole("textbox", { name: "Message dans Bureau" })).toHaveValue("Mon brouillon");
    fireEvent.click(screen.getByRole("button", { name: "Envoyer le message" }));
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith("/forum/structures/exemple/discussions", expect.objectContaining({ method: "POST", body: expect.stringContaining('"channel_id":1') })));
  });
  it("restricts management controls and opens a real thread reply form", async () => {
    mount(false);
    await screen.findByRole("heading", { name: "Bureau", level: 1 });
    expect(screen.queryByRole("button", { name: "Nouveau salon" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Désépingler" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Répondre" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Votre réponse" }), { target: { value: "Je prépare le dossier" } });
    fireEvent.submit(screen.getByRole("textbox", { name: "Votre réponse" }).closest("form")!);
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith("/forum/structures/exemple/discussions", expect.objectContaining({ body: expect.stringContaining('"parent_id":10') })));
  });
});

