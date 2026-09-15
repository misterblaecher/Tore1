import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ForumMembersPage from "@/pages/ForumMembers";
import ForumInvitationPage from "@/pages/ForumInvitation";
import { apiFetch } from "@/lib/api";


vi.mock("@/lib/api", async () => {
  class MockApiError extends Error {
    status?: number;
    constructor(message: string, status?: number) { super(message); this.status = status; }
  }
  return { apiFetch: vi.fn(), ApiError: MockApiError };
});

const pending = {
  id: 10,
  email: "pending@example.com",
  invitedRole: "MEMBER",
  status: "PENDING",
  expiresAt: "2026-09-22T08:00:00",
  createdAt: "2026-09-15T08:00:00",
};
const accepted = {
  id: 11,
  email: "accepted@example.com",
  invitedRole: "TREASURER",
  status: "ACCEPTED",
  expiresAt: "2026-09-22T08:00:00",
  acceptedAt: "2026-09-15T09:00:00",
  createdAt: "2026-09-15T08:00:00",
};
const expired = {
  id: 12,
  email: "expired@example.com",
  invitedRole: "STAFF",
  status: "EXPIRED",
  expiresAt: "2026-09-14T08:00:00",
  createdAt: "2026-09-07T08:00:00",
};

function renderMembers() {
  return render(<MemoryRouter initialEntries={["/forum/structures/embuscade/members"]}><Routes><Route path="/forum/structures/:slug/members" element={<ForumMembersPage />} /></Routes></MemoryRouter>);
}

function renderInvitation() {
  return render(<MemoryRouter initialEntries={["/forum/invite/token-123"]}><Routes><Route path="/forum/invite/:token" element={<ForumInvitationPage />} /></Routes></MemoryRouter>);
}

describe("Forum member invitations", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: vi.fn().mockResolvedValue(undefined) } });
  });
  afterEach(cleanup);

  it("invites with an email and role, never a UUID, and renders lifecycle actions", async () => {
    vi.mocked(apiFetch).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.includes("/members?")) return { items: [{ id: 1, userId: "internal-user-id", displayName: "Président", email: "president@example.com", role: "PRESIDENT", status: "ACTIVE" }], canManage: true } as never;
      if (path.endsWith("/invitations") && (!init || !init.method || init.method === "GET")) return { items: [pending, accepted, expired], allowedRoles: ["MEMBER", "STAFF", "TREASURER", "PRESIDENT"] } as never;
      if (path.endsWith("/invitations") && init?.method === "POST") return { ...pending, id: 20, email: "prenom.nom@example.com", invitedRole: "STAFF", inviteUrl: "https://forum.tore.test/forum/invite/secret", qrSvgDataUri: "data:image/svg+xml;base64,PHN2Zy8+", deliveryStatus: "SENT" } as never;
      return { ok: true } as never;
    });

    renderMembers();
    expect(await screen.findByRole("heading", { name: "Membres & invitations" })).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/UUID/i)).not.toBeInTheDocument();
    expect(await screen.findByText("accepted@example.com")).toBeInTheDocument();
    expect(screen.getByText("expired@example.com")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Relancer/ }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Annuler/ })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: "Adresse e-mail" }), { target: { value: "prenom.nom@example.com" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Rôle" }), { target: { value: "STAFF" } });
    fireEvent.click(screen.getByRole("button", { name: "Envoyer l’invitation" }));

    await screen.findByTestId("invitation-share");
    expect(screen.getByRole("img", { name: "QR de l’invitation" }).getAttribute("src")).toContain("data:image/svg+xml;base64,");
    const call = vi.mocked(apiFetch).mock.calls.find(([path, init]) => path === "/forum/structures/embuscade/invitations" && init?.method === "POST");
    expect(call).toBeTruthy();
    const body = JSON.parse(String(call?.[1]?.body));
    expect(body).toEqual({ email: "prenom.nom@example.com", invited_role: "STAFF" });
    expect(body.user_id).toBeUndefined();
  });

  it("accepts an invitation from the link and routes to the structure", async () => {
    vi.mocked(apiFetch).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/forum/invitations/token-123" && !init?.method) return { structure: { name: "L’Embuscade", slug: "embuscade" }, emailMasked: "p***@example.com", invitedRole: "MEMBER", status: "PENDING", expiresAt: "2026-09-22T08:00:00" } as never;
      if (path.endsWith("/accept")) return { ok: true, status: "ACCEPTED", structure: { name: "L’Embuscade", slug: "embuscade" }, role: "MEMBER" } as never;
      return { ok: true } as never;
    });

    renderInvitation();
    expect(await screen.findByText(/Invitation pour/)).toHaveTextContent("p***@example.com");
    fireEvent.click(screen.getByRole("button", { name: "Accepter" }));
    await screen.findByText(/Vous avez rejoint L’Embuscade/);
    expect(screen.getByRole("link", { name: "Ouvrir l’espace structure" })).toHaveAttribute("href", "/forum/structures/embuscade/dashboard");
  });

  it("declines an invitation without requiring a member UUID", async () => {
    vi.mocked(apiFetch).mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/forum/invitations/token-123" && !init?.method) return { structure: { name: "L’Embuscade", slug: "embuscade" }, emailMasked: "p***@example.com", invitedRole: "MEMBER", status: "PENDING", expiresAt: "2026-09-22T08:00:00" } as never;
      if (path.endsWith("/decline")) return { ok: true, status: "DECLINED" } as never;
      return { ok: true } as never;
    });

    renderInvitation();
    await screen.findByRole("button", { name: "Refuser" });
    fireEvent.click(screen.getByRole("button", { name: "Refuser" }));
    await waitFor(() => expect(screen.getByText("Invitation refusée.")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Accepter" })).not.toBeInTheDocument();
  });
});
