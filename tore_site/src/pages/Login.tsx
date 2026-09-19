import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Header, Footer } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";
import { setCachedMe, setToken } from "@/lib/auth";
import { getMe } from "@/lib/session";

type AuthOut = {
  access_token?: string;
  refresh_token?: string;
};

type EmailRequestOut = {
  ok: boolean;
  sent?: boolean;
  otp_debug?: string;
};

type LoginPageProps = {
  context?: "site" | "forum";
};

export default function LoginPage({ context = "site" }: LoginPageProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const isForum = context === "forum";
  const requestedFrom = (location.state as { from?: string } | undefined)?.from;
  const from = requestedFrom?.startsWith("/") && !requestedFrom.startsWith("//") ? requestedFrom : (isForum ? "/forum" : "/compte");
  const [mode, setMode] = useState<"register" | "login" | "email">("login");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [registerForm, setRegisterForm] = useState({
    firstName: "",
    lastName: "",
    nickname: "",
    email: "",
    password: "",
  });

  const [loginForm, setLoginForm] = useState({
    email: "",
    password: "",
  });
  const [emailCode, setEmailCode] = useState("");
  const [emailRequested, setEmailRequested] = useState(false);
  const [emailDevCode, setEmailDevCode] = useState<string | null>(null);

  async function finishAuth(data: AuthOut) {
    const accessToken = data.access_token;
    if (!accessToken) {
      throw new Error("missing access token");
    }
    setToken(accessToken);
    const me = await getMe(true);
    setCachedMe(me);
    navigate(from, { replace: true });
  }

  async function onRegisterSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    setError(null);

    try {
      const data = await apiFetch<AuthOut>("/auth/web/password/register", {
        method: "POST",
        body: JSON.stringify({
          email: registerForm.email,
          password: registerForm.password,
          first_name: registerForm.firstName,
          last_name: registerForm.lastName,
          nickname: registerForm.nickname || null,
        }),
      });
      await finishAuth(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("Un compte existe deja avec cet email.");
      } else {
        setError("Impossible de creer le compte pour le moment.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function onLoginSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    setError(null);

    try {
      const data = await apiFetch<AuthOut>("/auth/web/password/login", {
        method: "POST",
        body: JSON.stringify(loginForm),
      });
      setMessage("Connexion reussie.");
      await finishAuth(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Email ou mot de passe invalide.");
      } else {
        setError("Impossible de se connecter pour le moment.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function onEmailRequest(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    setError(null);

    try {
      const data = await apiFetch<EmailRequestOut>("/auth/email/request_otp", {
        method: "POST",
        body: JSON.stringify({ email: loginForm.email }),
      });
      setEmailRequested(true);
      setEmailDevCode(data.otp_debug ?? null);
      setMessage("Un code de connexion vient d’être envoyé à cette adresse.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError("Trop de demandes. Réessaie dans quelques instants.");
      } else {
        setError("Impossible d’envoyer le code par email pour le moment.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function onEmailVerify(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    setError(null);

    try {
      const data = await apiFetch<AuthOut>("/auth/web/email/verify_otp", {
        method: "POST",
        body: JSON.stringify({ email: loginForm.email, code: emailCode }),
      });
      await finishAuth(data);
    } catch {
      setError("Code invalide ou expiré.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={isForum ? "min-h-screen bg-[#080809] text-foreground" : "min-h-screen bg-background text-foreground"}>
      {!isForum ? <Header /> : null}
      <main className={isForum ? "forum-auth-page" : "pt-28 pb-20 section-ember-texture"}>
        <div className="container">
          <div className="mx-auto grid max-w-5xl gap-6 lg:grid-cols-[1.1fr_0.9fr]">
            <section className={isForum ? "forum-auth-card" : "rounded-2xl border border-accent/30 bg-[linear-gradient(145deg,rgba(255,179,71,0.08),rgba(11,11,11,0.94))] p-7 md:p-9 metal-edge-card"}>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">{isForum ? "TORÈ / Forum" : "Compte TORÈ"}</p>
              <h1 className="mt-3 text-3xl md:text-4xl font-semibold tracking-tight">{isForum ? "Créer ton accès au Forum" : "Creer ton acces web et forum"}</h1>
              <p className="mt-3 max-w-xl text-sm md:text-base text-muted-foreground leading-relaxed">
                Un seul compte pour le site, le forum et les futurs modules liés aux comités et événements. Tu peux utiliser un mot de passe ou recevoir un code par email.
              </p>

              <div className="mt-6 inline-flex rounded-full border border-border/70 bg-background/70 p-1">
                <button
                  type="button"
                  onClick={() => {
                    setMode("register");
                    setError(null);
                    setMessage(null);
                  }}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                    mode === "register" ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Creer un compte
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setMode("login");
                    setError(null);
                    setMessage(null);
                  }}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                    mode === "login" ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Se connecter
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setMode("email");
                    setEmailRequested(false);
                    setEmailDevCode(null);
                    setError(null);
                    setMessage(null);
                  }}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                    mode === "email" ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Email sécurisé
                </button>
              </div>

              {mode === "register" ? (
                <form onSubmit={onRegisterSubmit} className="mt-6 grid gap-4 md:grid-cols-2">
                  <label className="space-y-2 text-sm">
                    <span className="text-foreground/90">Prenom</span>
                    <input
                      required
                      value={registerForm.firstName}
                      onChange={(e) => setRegisterForm((prev) => ({ ...prev, firstName: e.target.value }))}
                      className="w-full rounded-md border border-border/70 bg-background/80 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
                    />
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className="text-foreground/90">Nom</span>
                    <input
                      required
                      value={registerForm.lastName}
                      onChange={(e) => setRegisterForm((prev) => ({ ...prev, lastName: e.target.value }))}
                      className="w-full rounded-md border border-border/70 bg-background/80 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
                    />
                  </label>
                  <label className="space-y-2 text-sm md:col-span-2">
                    <span className="text-foreground/90">Pseudo</span>
                    <input
                      value={registerForm.nickname}
                      onChange={(e) => setRegisterForm((prev) => ({ ...prev, nickname: e.target.value }))}
                      placeholder="Optionnel"
                      className="w-full rounded-md border border-border/70 bg-background/80 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
                    />
                  </label>
                  <label className="space-y-2 text-sm md:col-span-2">
                    <span className="text-foreground/90">Email</span>
                    <input
                      type="email"
                      required
                      value={registerForm.email}
                      onChange={(e) => setRegisterForm((prev) => ({ ...prev, email: e.target.value }))}
                      className="w-full rounded-md border border-border/70 bg-background/80 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
                    />
                  </label>
                  <label className="space-y-2 text-sm md:col-span-2">
                    <span className="text-foreground/90">Mot de passe</span>
                    <input
                      type="password"
                      required
                      minLength={6}
                      value={registerForm.password}
                      onChange={(e) => setRegisterForm((prev) => ({ ...prev, password: e.target.value }))}
                      className="w-full rounded-md border border-border/70 bg-background/80 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
                    />
                  </label>
                  <div className="md:col-span-2">
                    <Button type="submit" disabled={loading} className="h-11 w-full text-sm font-semibold">
                      {loading ? "Creation en cours..." : "Creer mon compte"}
                    </Button>
                  </div>
                </form>
              ) : mode === "login" ? (
                <form onSubmit={onLoginSubmit} className="mt-6 grid gap-4">
                  <label className="space-y-2 text-sm">
                    <span className="text-foreground/90">Email</span>
                    <input
                      type="email"
                      required
                      value={loginForm.email}
                      onChange={(e) => setLoginForm((prev) => ({ ...prev, email: e.target.value }))}
                      className="w-full rounded-md border border-border/70 bg-background/80 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
                    />
                  </label>
                  <label className="space-y-2 text-sm">
                    <span className="text-foreground/90">Mot de passe</span>
                    <input
                      type="password"
                      required
                      value={loginForm.password}
                      onChange={(e) => setLoginForm((prev) => ({ ...prev, password: e.target.value }))}
                      className="w-full rounded-md border border-border/70 bg-background/80 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
                    />
                  </label>
                  <Button type="submit" disabled={loading} className="h-11 w-full text-sm font-semibold">
                    {loading ? "Connexion..." : "Se connecter"}
                  </Button>
                </form>
              ) : (
                <form onSubmit={emailRequested ? onEmailVerify : onEmailRequest} className="mt-6 grid gap-4">
                  <label className="space-y-2 text-sm">
                    <span className="text-foreground/90">Email</span>
                    <input
                      type="email"
                      required
                      value={loginForm.email}
                      onChange={(e) => setLoginForm((prev) => ({ ...prev, email: e.target.value }))}
                      className="w-full rounded-md border border-border/70 bg-background/80 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
                    />
                  </label>
                  {emailRequested ? (
                    <label className="space-y-2 text-sm">
                      <span className="text-foreground/90">Code reçu par email</span>
                      <input
                        inputMode="numeric"
                        autoComplete="one-time-code"
                        required
                        maxLength={6}
                        value={emailCode}
                        onChange={(e) => setEmailCode(e.target.value.replace(/\D/g, ""))}
                        className="w-full rounded-md border border-border/70 bg-background/80 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
                      />
                    </label>
                  ) : null}
                  <Button type="submit" disabled={loading} className="h-11 w-full text-sm font-semibold">
                    {loading ? "Envoi..." : emailRequested ? "Valider le code" : "Recevoir un code"}
                  </Button>
                  {emailRequested ? (
                    <button type="button" className="text-left text-sm text-accent hover:underline" onClick={() => setEmailRequested(false)}>
                      Utiliser une autre adresse ou renvoyer le code
                    </button>
                  ) : null}
                  {emailDevCode ? <p className="text-xs text-amber-300">Code DEV local : {emailDevCode}</p> : null}
                </form>
              )}

              {message ? <p className="mt-4 text-sm text-emerald-400">{message}</p> : null}
              {error ? <p className="mt-4 text-sm text-destructive">{error}</p> : null}
            </section>

            <aside className={isForum ? "forum-auth-aside" : "rounded-2xl border border-border/60 bg-background/70 p-7 md:p-9 metal-edge-card"}>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">{isForum ? "Un compte, plusieurs espaces" : "Acces unifie"}</p>
              <div className="mt-4 space-y-4">
                <div className="rounded-2xl border border-border/60 bg-card/40 p-4">
                  <p className="text-sm font-semibold">Forum structures</p>
                  <p className="mt-1 text-sm text-muted-foreground">Creer un comite, demander un espace et gerer les discussions privees.</p>
                </div>
                <div className="rounded-2xl border border-border/60 bg-card/40 p-4">
                  <p className="text-sm font-semibold">Application TORÈ</p>
                  <p className="mt-1 text-sm text-muted-foreground">Lier ton compte aux outils TORÈ pour les evenements, les stats et les acces equipe.</p>
                </div>
                <div className="rounded-2xl border border-border/60 bg-card/40 p-4">
                  <p className="text-sm font-semibold">Profil evolutif</p>
                  <p className="mt-1 text-sm text-muted-foreground">Ton profil, tes rôles et tes oripeaux restent liés au même compte.</p>
                </div>
              </div>
            </aside>
          </div>
        </div>
      </main>
      {!isForum ? <Footer /> : null}
    </div>
  );
}
