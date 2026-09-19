import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type APIResponse, type Page } from "@playwright/test";

const API = "http://127.0.0.1:8001";
const TOKEN_KEY = "tore_site_access_token";
const PNG_1X1 = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==",
  "base64",
);

type Actor = { token: string; id: string };
type Structure = { id: number; slug: string; name: string; lifecycle: string; visibility: string };

const state: {
  owner?: Actor;
  outsider?: Actor;
  member?: Actor;
  treasurer?: Actor;
  aclAllowed?: Actor;
  aclDenied?: Actor;
  revoked?: Actor;
  structure?: Structure;
  eventId?: number;
  eventSlug?: string;
} = {};

let sequence = 0;
const runId = `${Date.now()}-${process.pid}`;
const auth = (actor: Actor, write = false) => ({
  Authorization: `Bearer ${actor.token}`,
  ...(write ? { "Idempotency-Key": `pw-${runId}-${++sequence}` } : {}),
});

async function json<T = Record<string, unknown>>(response: APIResponse, status: number | number[] = 200): Promise<T> {
  const allowed = Array.isArray(status) ? status : [status];
  expect(allowed, await response.text()).toContain(response.status());
  return (await response.json()) as T;
}

async function guest(request: APIRequestContext, name: string): Promise<Actor> {
  const created = await json<{ token: string }>(
    await request.post(`${API}/auth/guest`, { data: { display_name: `${name}-${runId}` } }),
  );
  const me = await json<{ id: string }>(
    await request.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${created.token}` } }),
  );
  return { token: created.token, id: me.id };
}

async function createStructure(request: APIRequestContext, owner: Actor, name: string): Promise<Structure> {
  const payload = await json<{ orga: Structure }>(
    await request.post(`${API}/orgas`, {
      headers: auth(owner, true),
      data: { name: `${name} ${runId}`, city: "Liège", org_type: "COMMITTEE" },
    }),
  );
  return payload.orga;
}

async function join(request: APIRequestContext, structure: Structure, actor: Actor): Promise<void> {
  await json(await request.post(`${API}/orgas/${structure.id}/join`, { headers: auth(actor, true) }));
}

async function loginPage(page: Page, actor: Actor): Promise<void> {
  await page.addInitScript(([key, token]) => localStorage.setItem(key, token), [TOKEN_KEY, actor.token]);
}

test.describe.serial("Forum security and product journeys", () => {
  test.beforeAll(async ({ request }) => {
    [state.owner, state.outsider, state.member, state.treasurer, state.aclAllowed, state.aclDenied, state.revoked] =
      await Promise.all([
        guest(request, "pw-owner"),
        guest(request, "pw-outsider"),
        guest(request, "pw-member"),
        guest(request, "pw-treasurer"),
        guest(request, "pw-acl-allowed"),
        guest(request, "pw-acl-denied"),
        guest(request, "pw-revoked"),
      ]);
  });

  test("01 - a newly created structure is private", async ({ request }) => {
    state.structure = await createStructure(request, state.owner!, "Playwright Security");
    expect(state.structure.lifecycle).toBe("SETUP");
    expect(state.structure.visibility).toBe("PRIVATE");
    expect((await request.get(`${API}/forum/structures/${state.structure.slug}`)).status()).toBe(404);
  });

  test("02 - publication is explicit", async ({ request }) => {
    const structure = state.structure!;
    const published = await json<{ published: boolean; visibility: string }>(
      await request.post(`${API}/forum/structures/${structure.slug}/publish`, {
        headers: auth(state.owner!, true),
        data: { reason: "Publication Playwright explicitement confirmée" },
      }),
    );
    expect(published.published).toBe(true);
    expect(published.visibility).toBe("PUBLIC");
    expect((await request.get(`${API}/forum/structures/${structure.slug}`)).status()).toBe(200);
  });

  test("03 - an outsider cannot enter the private dashboard", async ({ request }) => {
    const response = await request.get(`${API}/forum/structures/${state.structure!.slug}/dashboard`, {
      headers: auth(state.outsider!),
    });
    expect(response.status()).toBe(403);
  });

  test("04 - invitation by email creates a single pending invitation", async ({ request }) => {
    const invited = await json<{ email: string; status: string; inviteUrl: string }>(
      await request.post(`${API}/forum/structures/${state.structure!.slug}/invitations`, {
        headers: auth(state.owner!),
        data: { email: `playwright-${runId}@example.com`, invited_role: "MEMBER" },
      }),
      202,
    );
    expect(invited.status).toBe("PENDING");
    expect(invited.inviteUrl).toMatch(/^http/);
  });

  test("05 - a custom role grants only its declared permissions", async ({ request }) => {
    await join(request, state.structure!, state.member!);
    const role = await json<{ id: number }>(
      await request.post(`${API}/forum/structures/${state.structure!.slug}/roles`, {
        headers: auth(state.owner!),
        data: {
          name: "Responsable discussions E2E",
          code: `DISCUSSIONS_E2E_${Date.now()}`,
          capabilities: ["structure.read", "discussion.read", "discussion.write", "discussion.manage", "channel.create"],
        },
      }),
    );
    await json(
      await request.put(`${API}/forum/structures/${state.structure!.slug}/members/${state.member!.id}/roles`, {
        headers: auth(state.owner!),
        data: { role_ids: [role.id] },
      }),
    );
    const workspace = await json<{ capabilities: string[] }>(
      await request.get(`${API}/forum/structures/${state.structure!.slug}/workspace`, { headers: auth(state.member!) }),
    );
    expect(workspace.capabilities).toContain("discussion.manage");
    expect(workspace.capabilities).not.toContain("finance.read");
  });

  test("06 - channel ACL filters feeds, direct access and search", async ({ request }) => {
    await join(request, state.structure!, state.aclAllowed!);
    await join(request, state.structure!, state.aclDenied!);
    const channel = await json<{ id: number }>(
      await request.post(`${API}/forum/structures/${state.structure!.slug}/channels`, {
        headers: auth(state.owner!, true),
        data: { name: "Salon secret E2E", visibility: "STRUCTURE_MEMBERS" },
      }),
    );
    const post = await json<{ id: number }>(
      await request.post(`${API}/forum/structures/${state.structure!.slug}/discussions`, {
        headers: auth(state.owner!, true),
        data: { title: `secret-${runId}`, body: "Contenu réservé par ACL", channel_id: channel.id },
      }),
    );
    await json(
      await request.put(`${API}/forum/structures/${state.structure!.slug}/channels/${channel.id}/acl`, {
        headers: auth(state.owner!, true),
        data: { enabled: true, role_ids: [], capabilities: [], member_user_ids: [state.aclAllowed!.id] },
      }),
    );
    const allowed = await json<{ posts: { id: number }[] }>(
      await request.get(`${API}/forum/structures/${state.structure!.slug}/discussions?search=secret-${runId}`, { headers: auth(state.aclAllowed!) }),
    );
    const denied = await json<{ posts: { id: number }[] }>(
      await request.get(`${API}/forum/structures/${state.structure!.slug}/discussions?search=secret-${runId}`, { headers: auth(state.aclDenied!) }),
    );
    expect(allowed.posts.map((item) => item.id)).toContain(post.id);
    expect(denied.posts).toEqual([]);
    expect((await request.patch(`${API}/forum/structures/${state.structure!.slug}/discussions/${post.id}`, {
      headers: auth(state.aclDenied!, true), data: { emoji: "👍", active: true },
    })).status()).toBe(404);
  });

  test("07 - a public event can be created", async ({ request }) => {
    const startsAt = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
    const endsAt = new Date(Date.now() - 60 * 60 * 1000).toISOString();
    const event = await json<{ id: number; publicationStatus: string }>(
      await request.post(`${API}/forum/structures/${state.structure!.slug}/events`, {
        headers: auth(state.owner!, true),
        data: { name: "Recap Night E2E", starts_at: startsAt, ends_at: endsAt, venue: "Le Carré", city: "Liège", description: "Événement public E2E", visibility: "PUBLIC", publication_status: "PUBLISHED" },
      }),
    );
    state.eventId = event.id;
    state.eventSlug = `recap-night-e2e-${event.id}`;
    expect(event.publicationStatus).toBe("PUBLISHED");
  });

  test("08 - the public event page is reachable without authentication", async ({ request }) => {
    const response = await request.get(`${API}/forum/events/${state.eventSlug}`);
    const event = await json<{ title: string; recap: null }>(response);
    expect(event.title).toBe("Recap Night E2E");
    expect(event.recap).toBeNull();
  });

  test("09 - recap remains private until explicit publication", async ({ request }) => {
    const base = `${API}/forum/structures/${state.structure!.slug}/events/${state.eventId}/recap`;
    const draft = await json<{ recap: { status: string } }>(
      await request.put(base, {
        headers: auth(state.owner!, true),
        data: { summary: "Récapitulatif validé en E2E", stats: [{ label: "Entrées", value: "420" }] },
      }),
    );
    expect(draft.recap.status).toBe("RECAP_DRAFT");
    expect((await json<{ recap: null }>(await request.get(`${API}/forum/events/${state.eventSlug}`))).recap).toBeNull();
    const published = await json<{ recap: { status: string } }>(
      await request.post(`${base}/publish`, { headers: auth(state.owner!, true), data: { confirm_publish: true } }),
    );
    expect(published.recap.status).toBe("RECAP_PUBLISHED");
  });

  test("10 - album media upload stays private then is explicitly published", async ({ request }) => {
    const uploaded = await json<{ id: string; visibility: string }>(
      await request.post(`${API}/forum/structures/${state.structure!.slug}/files`, {
        headers: auth(state.owner!),
        multipart: { purpose: "ALBUM_MEDIA", file: { name: "photo.png", mimeType: "image/png", buffer: PNG_1X1 } },
      }),
      201,
    );
    expect(uploaded.visibility).toBe("PRIVATE");
    const publicFile = await json<{ visibility: string }>(
      await request.patch(`${API}/forum/structures/${state.structure!.slug}/files/${uploaded.id}/visibility`, {
        headers: auth(state.owner!), data: { visibility: "PUBLIC", confirm_public: true },
      }),
    );
    expect(publicFile.visibility).toBe("PUBLIC");
    const album = await json<{ id: number; status: string }>(
      await request.post(`${API}/forum/structures/${state.structure!.slug}/albums`, {
        headers: auth(state.owner!, true), data: { title: "Album E2E", visibility: "PUBLIC" },
      }),
    );
    expect(album.status).toBe("DRAFT");
    await json(await request.post(`${API}/forum/structures/${state.structure!.slug}/albums/${album.id}/media`, {
      headers: auth(state.owner!, true), data: { media_url: `${API}/forum/public/files/${uploaded.id}`, media_type: "IMAGE" },
    }));
    const published = await json<{ status: string }>(await request.patch(`${API}/forum/structures/${state.structure!.slug}/albums/${album.id}`, {
      headers: auth(state.owner!, true), data: { status: "PUBLISHED", reason: "Publication E2E" },
    }));
    expect(published.status).toBe("PUBLISHED");
  });

  test("11 - private and public documents preserve their visibility", async ({ request }) => {
    const privateDoc = await json<{ visibility: string }>(await request.post(`${API}/forum/structures/${state.structure!.slug}/documents`, {
      headers: auth(state.owner!, true), data: { title: "PV privé E2E", file_url: "https://files.example/private.pdf", visibility: "STRUCTURE_MEMBERS" },
    }));
    const publicDoc = await json<{ visibility: string }>(await request.post(`${API}/forum/structures/${state.structure!.slug}/documents`, {
      headers: auth(state.owner!, true), data: { title: "Charte publique E2E", file_url: "https://files.example/public.pdf", visibility: "PUBLIC" },
    }));
    expect(privateDoc.visibility).toBe("STRUCTURE_MEMBERS");
    expect(publicDoc.visibility).toBe("PUBLIC");
    expect((await request.get(`${API}/forum/structures/${state.structure!.slug}/documents`, { headers: auth(state.outsider!) })).status()).toBe(403);
  });

  test("12 - an ordinary member is denied finance access", async ({ request }) => {
    const response = await request.get(`${API}/forum/structures/${state.structure!.slug}/accounting-summary`, { headers: auth(state.aclAllowed!) });
    expect(response.status()).toBe(403);
  });

  test("13 - a treasurer can access finance without ownership powers", async ({ request }) => {
    await join(request, state.structure!, state.treasurer!);
    const roles = await json<{ items: { id: number; code: string }[] }>(await request.get(`${API}/forum/structures/${state.structure!.slug}/roles`, { headers: auth(state.owner!) }));
    const treasurerRole = roles.items.find((role) => role.code === "TREASURER")!;
    await json(await request.put(`${API}/forum/structures/${state.structure!.slug}/members/${state.treasurer!.id}/roles`, {
      headers: auth(state.owner!), data: { role_ids: [treasurerRole.id] },
    }));
    const workspace = await json<{ capabilities: string[] }>(await request.get(`${API}/forum/structures/${state.structure!.slug}/workspace`, { headers: auth(state.treasurer!) }));
    expect(workspace.capabilities).toContain("finance.read");
    expect(workspace.capabilities).not.toContain("ownership.transfer");
    expect((await request.get(`${API}/forum/structures/${state.structure!.slug}/accounting-summary`, { headers: auth(state.treasurer!) })).status()).toBe(200);
  });

  test("14 - ownership transfer requires confirmation by the target", async ({ request }) => {
    const oldOwner = await guest(request, "pw-transfer-owner");
    const target = await guest(request, "pw-transfer-target");
    const structure = await createStructure(request, oldOwner, "Transfer E2E");
    await join(request, structure, target);
    const transfer = await json<{ id: number; status: string }>(await request.post(`${API}/forum/structures/${structure.slug}/ownership/transfers`, {
      headers: auth(oldOwner), data: { to_user_id: target.id },
    }));
    expect(transfer.status).toBe("REQUESTED");
    const completed = await json<{ status: string; primaryOwnerUserId: string }>(await request.post(`${API}/forum/structures/${structure.slug}/ownership/transfers/${transfer.id}/confirm`, { headers: auth(target) }));
    expect(completed.status).toBe("COMPLETED");
    expect(completed.primaryOwnerUserId).toBe(target.id);
  });

  test("15 - recovery is limited to the configured recovery owner", async ({ request }) => {
    const owner = await guest(request, "pw-recovery-owner");
    const recovery = await guest(request, "pw-recovery-target");
    const structure = await createStructure(request, owner, "Recovery E2E");
    await join(request, structure, recovery);
    await json(await request.get(`${API}/forum/structures/${structure.slug}/ownership`, { headers: auth(owner) }));
    await json(await request.put(`${API}/forum/structures/${structure.slug}/ownership/recovery-owner`, { headers: auth(owner), data: { user_id: recovery.id } }));
    const requested = await json<{ id: number; status: string }>(await request.post(`${API}/forum/structures/${structure.slug}/ownership/recovery`, {
      headers: auth(recovery), data: { reason: "Perte d'accès confirmée par le test E2E" },
    }));
    expect(requested.status).toBe("REQUESTED");
    const approved = await json<{ status: string }>(await request.post(`${API}/forum/structures/${structure.slug}/ownership/recoveries/${requested.id}/approve`, { headers: auth(owner) }));
    expect(approved.status).toBe("APPROVED");
  });

  test("16 - a closed mandate immediately loses access", async ({ request }) => {
    await join(request, state.structure!, state.revoked!);
    expect((await request.get(`${API}/forum/structures/${state.structure!.slug}/dashboard`, { headers: auth(state.revoked!) })).status()).toBe(200);
    await json(await request.delete(`${API}/forum/structures/${state.structure!.slug}/members/${state.revoked!.id}?reason=fin%20de%20mandat`, { headers: auth(state.owner!, true) }));
    expect((await request.get(`${API}/forum/structures/${state.structure!.slug}/dashboard`, { headers: auth(state.revoked!) })).status()).toBe(403);
  });

  test("17 - global search finds page content without leaking ACL content", async ({ request }) => {
    await json(await request.post(`${API}/forum/structures/${state.structure!.slug}/pages`, {
      headers: auth(state.owner!, true),
      data: { title: "Mémoire E2E", content: `needle-page-${runId}`, visibility: "STRUCTURE_MEMBERS", category: "HISTORY", published: true },
    }));
    const ownerResults = await json<{ results: { category: string; title: string }[] }>(await request.get(`${API}/forum/structures/${state.structure!.slug}/search?q=needle-page-${runId}`, { headers: auth(state.owner!) }));
    expect(ownerResults.results.some((item) => item.category === "folklore" && item.title === "Mémoire E2E")).toBe(true);
    const deniedResults = await json<{ results: { title: string }[] }>(await request.get(`${API}/forum/structures/${state.structure!.slug}/search?q=secret-${runId}`, { headers: auth(state.aclDenied!) }));
    expect(deniedResults.results.some((item) => item.title.includes(`secret-${runId}`))).toBe(false);
  });

  test("18 - notifications can be listed and marked read", async ({ request }) => {
    const listing = await json<{ items: unknown[]; unreadCount: number }>(await request.get(`${API}/forum/structures/${state.structure!.slug}/notifications`, { headers: auth(state.owner!) }));
    expect(Array.isArray(listing.items)).toBe(true);
    expect(listing.unreadCount).toBeGreaterThanOrEqual(0);
    expect((await json<{ ok: boolean }>(await request.post(`${API}/forum/structures/${state.structure!.slug}/notifications/read-all`, { headers: auth(state.owner!) }))).ok).toBe(true);
  });

  test("19 - an authorized owner can export accounting", async ({ request }) => {
    const response = await request.get(`${API}/forum/structures/${state.structure!.slug}/accounting/export.csv`, { headers: auth(state.owner!) });
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("text/csv");
  });

  test("20 - an ordinary member cannot export accounting", async ({ request }) => {
    expect((await request.get(`${API}/forum/structures/${state.structure!.slug}/accounting/export.csv`, { headers: auth(state.aclDenied!) })).status()).toBe(403);
  });

  test("21 - forum navigation is keyboard reachable", async ({ page }) => {
    await page.goto("/forum");
    await page.keyboard.press("Tab");
    const focused = page.locator(":focus");
    await expect(focused).toBeVisible();
    await expect(focused).toHaveJSProperty("tabIndex", 0);
  });

  test("22 - forum public page does not overflow on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/forum/structures/${state.structure!.slug}`);
    await expect(page.locator("body")).toBeVisible();
    const overflows = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(overflows).toBe(false);
  });

  test("23 - an invalid MIME upload is rejected", async ({ request }) => {
    const response = await request.post(`${API}/forum/structures/${state.structure!.slug}/files`, {
      headers: auth(state.owner!),
      multipart: { purpose: "DOCUMENT", file: { name: "payload.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ malware") } },
    });
    expect(response.status()).toBe(415);
    expect((await response.json()).detail.reason).toBe("MIME_NOT_ALLOWED");
  });

  for (const [name, route, authenticated] of [
    ["Forum home", "/forum", false],
    ["directory", "/forum/structures", false],
    ["public structure", () => `/forum/structures/${state.structure!.slug}`, false],
    ["Structure dashboard", () => `/forum/structures/${state.structure!.slug}/dashboard`, true],
    ["discussions", () => `/forum/structures/${state.structure!.slug}/discussions`, true],
    ["Event", () => `/forum/events/${state.eventSlug}`, false],
    ["documents", () => `/forum/structures/${state.structure!.slug}/documents`, true],
    ["accounting", () => `/forum/structures/${state.structure!.slug}/accounting`, true],
  ] as const) {
    test(`axe - no critical violation on ${name}`, async ({ page }) => {
      if (authenticated) await loginPage(page, state.owner!);
      await page.goto(typeof route === "function" ? route() : route);
      await expect(page.locator("body")).toBeVisible();
      const result = await new AxeBuilder({ page }).analyze();
      const critical = result.violations.filter((violation) => violation.impact === "critical");
      expect(critical, JSON.stringify(critical, null, 2)).toEqual([]);
    });
  }
});
