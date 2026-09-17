import { afterEach, describe, expect, it, vi } from "vitest";
import handler from "../../api/seo";

function responseRecorder() {
  const headers: Record<string, string> = {};
  const state = { status: 200, body: "" };
  const res = {
    setHeader(name: string, value: string) { headers[name.toLowerCase()] = value; },
    status(code: number) { state.status = code; return res; },
    send(body: string) { state.body = body; return res; },
  };
  return { res, state, headers };
}

describe("Vercel crawler SEO HTML", () => {
  afterEach(() => vi.restoreAllMocks());

  it("returns crawlable structure metadata in the initial HTML", async () => {
    vi.stubEnv("SEO_API_BASE_URL", "https://api.example.test");
    const fetchMock = vi.spyOn(globalThis, "fetch");
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({
      slug: "cercle-tore",
      name: "Cercle TORÈ",
      title: "Cercle TORÈ — TORÈ",
      description: "Le cercle officiel.",
      imageUrl: "https://cdn.example.test/cercle.jpg",
      indexable: true,
    }), { status: 200, headers: { "content-type": "application/json" } }));
    fetchMock.mockResolvedValueOnce(new Response('<!doctype html><html><head><title>TORÈ</title></head><body><div id="root"></div><script src="/assets/app.js"></script></body></html>', { status: 200 }));

    const { res, state } = responseRecorder();
    await handler({ query: { kind: "structure", slug: "cercle-tore" }, headers: { host: "tore.example.test", "x-forwarded-proto": "https" } }, res);

    expect(state.status).toBe(200);
    expect(state.body).toContain('<title>Cercle TORÈ — TORÈ</title>');
    expect(state.body).toContain('name="description" content="Le cercle officiel."');
    expect(state.body).toContain('rel="canonical" href="https://tore.example.test/forum/structures/cercle-tore"');
    expect(state.body).toContain('property="og:image" content="https://cdn.example.test/cercle.jpg"');
    expect(state.body).toContain('name="twitter:card" content="summary_large_image"');
    expect(state.body).toContain('name="robots" content="index,follow,max-image-preview:large"');
    expect(state.body).toContain('<noscript><main><h1>Cercle TORÈ</h1>');
  });

  it("returns a permanent redirect for an old structure slug", async () => {
    vi.stubEnv("SEO_API_BASE_URL", "https://api.example.test");
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify({ redirectTo: "nouveau-slug", permanent: true }), { status: 200 }));
    const { res, state, headers } = responseRecorder();
    await handler({ query: { kind: "structure", slug: "ancien-slug" }, headers: { host: "tore.example.test", "x-forwarded-proto": "https" } }, res);
    expect(state.status).toBe(301);
    expect(headers.location).toBe("https://tore.example.test/forum/structures/nouveau-slug");
  });

  it("generates an indexable structures sitemap", async () => {
    vi.stubEnv("SEO_API_BASE_URL", "https://api.example.test");
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ slug: "cercle-tore" }] }), { status: 200 }));
    const { res, state, headers } = responseRecorder();
    await handler({ query: { kind: "sitemap-structures" }, headers: { host: "tore.example.test", "x-forwarded-proto": "https" } }, res);
    expect(state.status).toBe(200);
    expect(headers["content-type"]).toContain("application/xml");
    expect(state.body).toContain("https://tore.example.test/forum/structures/cercle-tore");
  });
});
