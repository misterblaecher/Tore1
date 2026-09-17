const SITE_NAME = 'TORÈ';
const FALLBACK_API_BASE = 'https://tore-backend.onrender.com';

function apiBase() {
  return (process.env.SEO_API_BASE_URL || process.env.VITE_API_BASE_URL || process.env.VITE_API_URL || FALLBACK_API_BASE).replace(/\/+$/, '');
}

function esc(value: unknown) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function absolute(origin: string, value?: string | null) {
  if (!value) return `${origin}/logo_full.png`;
  try { return new URL(value, origin).toString(); } catch { return `${origin}/logo_full.png`; }
}

async function api(path: string) {
  const response = await fetch(`${apiBase()}${path}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    const error = new Error(`API ${response.status}`) as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function metadata(origin: string, canonicalPath: string, item: Record<string, any>) {
  const title = item.title || SITE_NAME;
  const description = item.description || 'Page officielle TORÈ.';
  const canonical = `${origin}${canonicalPath}`;
  const image = absolute(origin, item.imageUrl || item.coverUrl);
  const robots = item.indexable ? 'index,follow,max-image-preview:large' : 'noindex,nofollow';
  return `
<title>${esc(title)}</title>
<meta name="description" content="${esc(description)}" />
<link rel="canonical" href="${esc(canonical)}" />
<meta name="robots" content="${robots}" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="${SITE_NAME}" />
<meta property="og:title" content="${esc(title)}" />
<meta property="og:description" content="${esc(description)}" />
<meta property="og:url" content="${esc(canonical)}" />
<meta property="og:image" content="${esc(image)}" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="${esc(title)}" />
<meta name="twitter:description" content="${esc(description)}" />
<meta name="twitter:image" content="${esc(image)}" />`;
}

function inject(shell: string, head: string, fallback: string) {
  const cleaned = shell
    .replace(/<title>[\s\S]*?<\/title>/i, '')
    .replace(/<meta\s+name=["']description["'][^>]*>/i, '')
    .replace(/<meta\s+name=["']robots["'][^>]*>/i, '')
    .replace(/<link\s+rel=["']canonical["'][^>]*>/i, '')
    .replace(/<meta\s+property=["']og:[^"']+["'][^>]*>/gi, '')
    .replace(/<meta\s+name=["']twitter:[^"']+["'][^>]*>/gi, '');
  return cleaned
    .replace('</head>', `${head}\n</head>`)
    .replace('<div id="root"></div>', `<div id="root"></div><noscript>${fallback}</noscript>`);
}

function originFor(req: any) {
  const host = req.headers['x-forwarded-host'] || req.headers.host;
  const proto = req.headers['x-forwarded-proto'] || 'https';
  return `${proto}://${host}`;
}

async function shell(origin: string) {
  const response = await fetch(`${origin}/index.html`, { headers: { 'x-seo-shell': '1' } });
  if (!response.ok) throw new Error(`Unable to load Vite shell (${response.status})`);
  return response.text();
}

function xml(items: { loc: string }[]) {
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${items.map((item) => `\n  <url><loc>${esc(item.loc)}</loc></url>`).join('')}\n</urlset>`;
}

export default async function handler(req: any, res: any) {
  const origin = originFor(req);
  const kind = String(req.query.kind || '');
  const slug = String(req.query.slug || '');

  try {
    if (kind === 'sitemap-structures') {
      const payload = await api('/forum/seo/structures');
      res.setHeader('Content-Type', 'application/xml; charset=utf-8');
      res.setHeader('Cache-Control', 'public, s-maxage=300, stale-while-revalidate=3600');
      return res.status(200).send(xml((payload.items || []).map((item: any) => ({ loc: `${origin}/forum/structures/${encodeURIComponent(item.slug)}` }))));
    }
    if (kind === 'sitemap-events') {
      const payload = await api('/forum/seo/events');
      res.setHeader('Content-Type', 'application/xml; charset=utf-8');
      res.setHeader('Cache-Control', 'public, s-maxage=300, stale-while-revalidate=3600');
      return res.status(200).send(xml((payload.items || []).map((item: any) => ({ loc: `${origin}/forum/events/${encodeURIComponent(item.slug)}` }))));
    }

    const endpoint = kind === 'event'
      ? `/forum/seo/events/${encodeURIComponent(slug)}`
      : `/forum/seo/structures/${encodeURIComponent(slug)}`;
    const item = await api(endpoint);

    if (item.redirectTo) {
      res.setHeader('Location', `${origin}/forum/structures/${encodeURIComponent(item.redirectTo)}`);
      return res.status(301).send('Moved permanently');
    }

    const canonicalPath = kind === 'event' ? `/forum/events/${item.slug}` : `/forum/structures/${item.slug}`;
    const description = item.description || (kind === 'event'
      ? `Informations publiques de ${item.title} sur TORÈ.`
      : `${item.name}, page officielle sur TORÈ.`);
    const title = item.title || `${item.name} — TORÈ`;
    const html = inject(
      await shell(origin),
      metadata(origin, canonicalPath, { ...item, title, description }),
      `<main><h1>${esc(item.title || item.name)}</h1><p>${esc(description)}</p></main>`,
    );
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.setHeader('Cache-Control', 'public, s-maxage=60, stale-while-revalidate=600');
    return res.status(200).send(html);
  } catch (error: any) {
    const status = error?.status === 404 ? 404 : 502;
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.setHeader('X-Robots-Tag', 'noindex, nofollow');
    return res.status(status).send('<!doctype html><html lang="fr"><head><title>TORÈ</title><meta name="robots" content="noindex,nofollow"></head><body><main><h1>Page indisponible</h1></main></body></html>');
  }
}
