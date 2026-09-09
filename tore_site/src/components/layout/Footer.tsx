import { Link, useLocation } from "react-router-dom";
import { getToken } from "@/lib/auth";

export function Footer() {
  const location = useLocation();
  const isForumShell = location.pathname.startsWith("/forum") || location.pathname === "/compte";
  const accountHref = getToken() ? "/compte" : isForumShell ? "/forum/login" : "/login";
  if (isForumShell) {
    return <footer className="forum-account-footer"><span>© {new Date().getFullYear()} TORÈ — OS Numérique Territorial.</span><nav><Link to={accountHref}>Compte</Link><Link to="/forum">Forum</Link><Link to="/contact">Contact</Link><Link to="/legal/privacy">Confidentialité</Link></nav></footer>;
  }
  return (
    <footer className="border-t border-border/50 bg-background">
      <div className="container py-8 md:py-10 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <p className="text-sm text-muted-foreground">© {new Date().getFullYear()} TORÈ — OS Numérique Territorial.</p>
        <nav aria-label="Liens utiles" className="flex flex-wrap items-center gap-6 text-sm">
          <Link to="/produit" className="text-muted-foreground hover:text-foreground">Application</Link>
          <Link to="/rejoindre" className="text-muted-foreground hover:text-foreground">Rejoindre la bêta</Link>
          <Link to={accountHref} className="text-muted-foreground hover:text-foreground transition-colors">
            Compte
          </Link>
          <Link to="/forum" className="text-muted-foreground hover:text-foreground transition-colors">
            Forum
          </Link>
          <Link to="/contact" className="text-muted-foreground hover:text-foreground transition-colors">
            Contact
          </Link>
          <Link to="/legal/privacy" className="text-muted-foreground hover:text-foreground transition-colors">
            Confidentialité
          </Link>
        </nav>
      </div>
    </footer>
  );
}
