import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { Header, Footer } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { ANDROID_BETA_URL, IOS_BETA_URL, WAITLIST_URL, WHATSAPP_URL } from "@/lib/external-links";
import { API_BASE } from "@/lib/api";
import { getToken } from "@/lib/auth";

type AccountRole = "student" | "committee" | "bar" | "dj";
type AccountMode = "user" | "organizer" | "team";

const readUtmParams = () => {
  if (typeof window === "undefined") return undefined;
  const params = new URLSearchParams(window.location.search);
  const keys = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"];
  const utm = keys.reduce<Record<string, string>>((acc, key) => {
    const value = params.get(key);
    if (value) acc[key] = value;
    return acc;
  }, {});
  return Object.keys(utm).length ? utm : undefined;
};

const JoinPage = () => {
  const { toast } = useToast();
  const [accountLoading, setAccountLoading] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);
  const [accountSuccess, setAccountSuccess] = useState<string | null>(null);
  const [selectedRole, setSelectedRole] = useState<AccountRole | "">("");
  const [selectedAccountMode, setSelectedAccountMode] = useState<AccountMode>("user");
  const apiReady = Boolean(API_BASE && API_BASE.startsWith("http"));

  const safeParse = async (res: Response) => {
    const contentType = res.headers.get("content-type")?.toLowerCase() ?? "";
    const rawBody = await res.text();
    if (!contentType.includes("application/json")) {
      return { json: null, text: rawBody };
    }
    try {
      return { json: JSON.parse(rawBody), text: rawBody };
    } catch {
      return { json: null, text: rawBody };
    }
  };

  const resetAccountRequest = () => {
    setAccountSuccess(null);
    setAccountError(null);
    setSelectedRole("");
    setSelectedAccountMode("user");
  };

  const scrollToWaitlist = () => {
    document.getElementById("waitlist")?.scrollIntoView({ behavior: "smooth" });
  };


  const accountHref = getToken() ? "/compte" : "/login";
  return <div className="min-h-screen bg-background text-foreground">
    <Header />
    <main className="pt-28 md:pt-36">
      <header className="container space-y-4 pb-10">
        <p className="text-xs uppercase tracking-widest text-accent">Accès TORÈ</p>
        <h1 className="text-4xl md:text-5xl">Rejoindre l’aventure.</h1>
        <p className="max-w-2xl text-muted-foreground">Retrouvez les accès à la bêta, votre compte unique et les demandes d’accompagnement pour votre structure.</p>
        <nav aria-label="Accès rapides" className="flex flex-wrap gap-5 text-sm text-accent">
          <Link to="/rejoindre#beta">Installer la bêta</Link>
          <Link to="/rejoindre#account">Compte et accès pro</Link>
          <Link to="/forum">Accéder au Forum →</Link>
        </nav>
      </header>
        <section id="beta" className="py-16 md:py-24 border-b border-border/50 bg-card/20 section-ember-texture">
          <div className="container">
            <div className="grid gap-8 lg:grid-cols-2 lg:items-start">
              <div className="space-y-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Accès bêta</p>
                <h2 className="text-3xl md:text-5xl font-semibold tracking-tight">Télécharger TORÈ (Bêta)</h2>
                <p className="text-muted-foreground text-base md:text-lg leading-relaxed">
                  Déploiement progressif à Liège. Accès sur invitation pour bars et comités.
                </p>
                <p className="text-sm text-muted-foreground">
                  Si un lien n'est pas encore disponible, rejoignez la waitlist pour recevoir votre accès d'installation.
                </p>
                <Link to={accountHref} className="inline-flex text-sm text-accent hover:text-accent/90 transition-colors">
                  Créer ou ouvrir mon compte TORÈ →
                </Link>
              </div>
              <div className="rounded-2xl border border-border/60 bg-background/70 p-6 md:p-8 metal-edge-card space-y-4">
                <Button
                  asChild={Boolean(IOS_BETA_URL)}
                  onClick={IOS_BETA_URL ? undefined : scrollToWaitlist}
                  size="lg"
                  className="w-full h-12 font-semibold"
                >
                  {IOS_BETA_URL ? (
                    <a href={IOS_BETA_URL} target="_blank" rel="noreferrer">Télécharger iOS (Bêta)</a>
                  ) : (
                    <span>Télécharger iOS (Bêta)</span>
                  )}
                </Button>
                <Button
                  asChild={Boolean(ANDROID_BETA_URL)}
                  onClick={ANDROID_BETA_URL ? undefined : scrollToWaitlist}
                  size="lg"
                  variant="outline"
                  className="w-full h-12 font-semibold border-accent/40 hover:bg-accent/10"
                >
                  {ANDROID_BETA_URL ? (
                    <a href={ANDROID_BETA_URL} target="_blank" rel="noreferrer">Télécharger Android (Bêta)</a>
                  ) : (
                    <span>Télécharger Android (Bêta)</span>
                  )}
                </Button>
                {WAITLIST_URL ? (
                  <div className="pt-2">
                    <a href={WAITLIST_URL} target="_blank" rel="noreferrer" className="text-sm text-accent hover:text-accent/90 transition-colors">
                      Recevoir le lien d'installation →
                    </a>
                  </div>
                ) : (
                  <div className="pt-2 text-sm text-muted-foreground">Recevoir le lien d'installation via WhatsApp.</div>
                )}
              </div>
            </div>
          </div>
        </section>


        <section id="waitlist" className="py-16 md:py-24 border-b border-border/50 section-ember-texture">
          <div className="container">
            <div className="max-w-4xl rounded-2xl border border-border/60 bg-background/65 p-8 md:p-10 metal-edge-card space-y-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Rejoindre la bêta</p>
              <h2 className="text-2xl md:text-4xl font-semibold tracking-tight">Waitlist pilotes TORÈ</h2>
              <p className="text-muted-foreground">Profils ciblés : Étudiant, Bar, Comité, DJ. Décrivez votre rôle et votre besoin pilote.</p>
              <p className="text-sm text-muted-foreground">Ce qu'on mesure : intérêt module et demandes de tests terrain.</p>
              <Link to={accountHref} className="inline-flex text-sm text-accent hover:text-accent/90 transition-colors">
                Créer ou ouvrir mon compte TORÈ →
              </Link>
              {WAITLIST_URL ? (
                <Button asChild size="lg" className="h-12 px-7 text-sm sm:text-base font-semibold w-full sm:w-auto">
                  <a href={WAITLIST_URL} target="_blank" rel="noreferrer">Rejoindre la waitlist</a>
                </Button>
              ) : (
                <Button asChild size="lg" className="h-12 px-7 text-sm sm:text-base font-semibold w-full sm:w-auto">
                  <a href={WHATSAPP_URL} target="_blank" rel="noreferrer">Contact WhatsApp</a>
                </Button>
              )}
            </div>
          </div>
        </section>

        <section id="account" className="py-16 md:py-24 border-b border-border/50 bg-card/20 section-ember-texture">
          <div className="container">
            <div className="max-w-4xl rounded-2xl border border-accent/25 bg-[linear-gradient(145deg,rgba(255,179,71,0.06),rgba(11,11,11,0.92))] p-8 md:p-10 metal-edge-card space-y-5">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Compte unique</p>
              <h2 className="text-2xl md:text-4xl font-semibold tracking-tight">Un compte pour tout TORÈ</h2>
              <p className="text-muted-foreground">
                Le compte créé ici est le même que celui utilisé sur le Forum et dans l’application. Connecte-toi par email ou crée ton accès en quelques secondes.
              </p>

              <div className="flex flex-col gap-3 sm:flex-row">
                <Button asChild size="lg" className="h-11 px-6 text-sm font-semibold">
                  <Link to={accountHref}>Créer ou ouvrir mon compte</Link>
                </Button>
                <Button asChild variant="outline" size="lg" className="h-11 px-6 text-sm font-semibold">
                  <Link to="/forum/structures">Explorer les structures</Link>
                </Button>
              </div>

              <div className="border-t border-border/50 pt-6">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Accompagnement professionnel</p>
                <h3 className="mt-2 text-xl font-semibold tracking-tight">Besoin d’un accès comité, bar ou DJ ?</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  Cette demande ne crée pas un second compte : elle transmet ton besoin à l’équipe TORÈ pour activer les bons rôles et permissions.
                </p>
              </div>

              <form
                className="grid gap-4 md:grid-cols-2"
                aria-disabled={Boolean(accountSuccess)}
                onSubmit={async (event: FormEvent<HTMLFormElement>) => {
                  event.preventDefault();
                  const form = event.currentTarget;
                  if (accountLoading || accountSuccess) {
                    return;
                  }
                  setAccountError(null);
                  setAccountSuccess(null);
                  setAccountLoading(true);

                  if (!API_BASE || !API_BASE.startsWith("http")) {
                    const message = "Backend non configuré.";
                    setAccountError(message);
                    toast({ title: "Erreur", description: "Backend non configuré.", variant: "destructive", duration: 3200 });
                    setAccountLoading(false);
                    return;
                  }

                  const accountRequestUrl = `${API_BASE.replace(/\/+$/, "")}/public/account-request`;
                  const formData = new FormData(form);
                  const role = String(formData.get("role") || "") as AccountRole;
                  const payload = {
                    name: String(formData.get("name") || "").trim(),
                    email: String(formData.get("email") || "").trim(),
                    phone: String(formData.get("phone") || "").trim().replace(/\s+/g, ""),
                    is_whatsapp: formData.get("is_whatsapp") === "on",
                    role,
                    committee_name: role === "committee" ? String(formData.get("committee_name") || "").trim() || null : null,
                    source: "tore_site",
                    account_mode: selectedAccountMode,
                    utm: readUtmParams(),
                  };
                  console.debug("Account request payload", payload);

                  try {
                    const res = await fetch(accountRequestUrl, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(payload),
                    });
                    const { json, text } = await safeParse(res);
                    console.debug("Account request response", { status: res.status, body: json ?? text });

                    if (res.ok && json?.ok === true) {
                      const successMessage = typeof json.id === "number" ? `Demande envoyée (ID ${json.id}).` : "Demande envoyée.";
                      setAccountSuccess(successMessage);
                      setAccountError(null);
                      form.reset();
                      setSelectedRole("");
                      setSelectedAccountMode("user");
                      toast({ title: "Demande envoyée", description: "Ta demande a bien été enregistrée.", duration: 3200 });
                      return;
                    }

                    if (res.ok) {
                      const message = "Réponse inattendue du serveur.";
                      setAccountError(message);
                      console.error("Unexpected account request response", { json, text });
                      toast({ title: "Erreur", description: message, variant: "destructive", duration: 3200 });
                      return;
                    }

                    const retryAfterFromBody =
                      json && typeof json === "object" && "retry_after_seconds" in json
                        ? Number(json.retry_after_seconds)
                        : null;
                    const retryAfterFromHeader = Number(res.headers.get("retry-after") || "");
                    const retryAfterSeconds = Number.isFinite(retryAfterFromBody)
                      ? Math.max(1, Math.floor(retryAfterFromBody as number))
                      : Number.isFinite(retryAfterFromHeader)
                        ? Math.max(1, Math.floor(retryAfterFromHeader))
                        : null;

                    const messageByStatus: Record<number, string> = {
                      400: "Vérifie les champs.",
                      422: "Vérifie les champs.",
                      429: retryAfterSeconds
                        ? `Trop de tentatives. Réessaie dans ${retryAfterSeconds} secondes.`
                        : "Trop de tentatives. Réessaie plus tard.",
                    };
                    const baseMessage = messageByStatus[res.status] || "Erreur serveur. Réessaie.";
                    const detail =
                      json && typeof json === "object" && "detail" in json && typeof json.detail === "string" ? json.detail : "";
                    const message = detail ? `${baseMessage} ${detail}` : baseMessage;
                    setAccountError(message);
                    toast({ title: "Erreur", description: message, variant: "destructive", duration: 3200 });
                  } catch (err) {
                    if (accountSuccess) {
                      return;
                    }
                    const message = "Erreur réseau. Réessaie dans un instant.";
                    console.error("Account request failed", err);
                    setAccountError(message);
                    toast({ title: "Erreur", description: message, variant: "destructive", duration: 3200 });
                  } finally {
                    setAccountLoading(false);
                  }
                }}
              >
                <label className="space-y-2 text-sm">
                  <span className="text-foreground/90">Nom</span>
                  <input name="name" required disabled={Boolean(accountSuccess)} className="w-full rounded-md border border-border/70 bg-background/70 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70" />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-foreground/90">Email</span>
                  <input type="email" name="email" required disabled={Boolean(accountSuccess)} className="w-full rounded-md border border-border/70 bg-background/70 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70" />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-foreground/90">Téléphone</span>
                  <input type="tel" name="phone" required disabled={Boolean(accountSuccess)} className="w-full rounded-md border border-border/70 bg-background/70 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70" />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-foreground/90">Rôle</span>
                  <select
                    name="role"
                    required
                    value={selectedRole}
                    onChange={(event) => setSelectedRole(event.target.value as AccountRole | "")}
                    disabled={Boolean(accountSuccess)}
                    className="w-full rounded-md border border-border/70 bg-background/70 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
                  >
                    <option value="">Sélectionner un rôle</option>
                    <option value="student">Étudiant</option>
                    <option value="committee">Comité</option>
                    <option value="bar">Bar</option>
                    <option value="dj">DJ</option>
                  </select>
                </label>
                <div className="md:col-span-2 space-y-2 text-sm">
                  <span className="text-foreground/90">Choisir ton mode</span>
                  <div className="grid gap-2 sm:grid-cols-3">
                    {[
                      { value: "user", label: "Mode Utilisateur", hint: "Découvrir et participer" },
                      { value: "organizer", label: "Mode Organisateur", hint: "Créer et piloter un event" },
                      { value: "team", label: "Mode Équipe", hint: "Scanner et check-in" },
                    ].map((mode) => {
                      const active = selectedAccountMode === mode.value;
                      return (
                        <button
                          type="button"
                          key={mode.value}
                          onClick={() => setSelectedAccountMode(mode.value as AccountMode)}
                          disabled={Boolean(accountSuccess)}
                          className={`rounded-xl border px-3 py-3 text-left transition ${
                            active ? "border-accent bg-accent/10" : "border-border/60 bg-background/50 hover:border-accent/50"
                          }`}
                        >
                          <p className="text-sm font-semibold">{mode.label}</p>
                          <p className="text-xs text-muted-foreground">{mode.hint}</p>
                        </button>
                      );
                    })}
                  </div>
                </div>
                {selectedRole === "committee" && (
                  <label className="md:col-span-2 space-y-2 text-sm">
                    <span className="text-foreground/90">Nom du comité</span>
                    <input name="committee_name" required={selectedRole === "committee"} disabled={Boolean(accountSuccess)} className="w-full rounded-md border border-border/70 bg-background/70 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70" />
                  </label>
                )}
                <label className="md:col-span-2 inline-flex items-center gap-2 text-sm text-muted-foreground">
                  <input type="checkbox" name="is_whatsapp" disabled={Boolean(accountSuccess)} className="h-4 w-4 rounded border-border bg-background/70 accent-[hsl(var(--accent))]" />
                  Ce numéro est WhatsApp
                </label>
                <div className="md:col-span-2 flex flex-col gap-2">
                  <Button type="submit" disabled={!apiReady || accountLoading || Boolean(accountSuccess)} size="lg" className="h-11 px-6 text-sm font-semibold w-full sm:w-auto">
                    {accountLoading ? "Envoi en cours..." : "Demander un accès pro"}
                  </Button>
                  {!apiReady && <span className="text-sm text-muted-foreground">Backend non configuré.</span>}
                  {accountSuccess && <p className="text-sm text-emerald-400">{accountSuccess}</p>}
                  {accountSuccess && (
                    <p className="text-sm text-muted-foreground">Validation nécessaire: on te recontacte rapidement pour finaliser l'accès.</p>
                  )}
                  {accountError && <p className="text-sm text-destructive">{accountError}</p>}
                  {accountSuccess && (
                    <Button type="button" variant="outline" onClick={resetAccountRequest} size="sm" className="w-full sm:w-auto">
                      Nouvelle demande
                    </Button>
                  )}
                </div>
              </form>

              <p className="text-sm text-muted-foreground">
                Données utilisées uniquement pour l'onboarding compte TORÈ, conservation limitée et suppression sur demande.
              </p>
            </div>
          </div>
        </section>


    </main>
    <Footer />
  </div>;
};
export default JoinPage;
