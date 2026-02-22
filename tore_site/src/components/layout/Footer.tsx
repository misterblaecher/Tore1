import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="border-t border-border/50 bg-background">
      <div className="container py-8 md:py-10 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <p className="text-sm text-muted-foreground">© {new Date().getFullYear()} TORÈ — OS Numérique Territorial.</p>
        <nav className="flex items-center gap-6 text-sm">
          <Link to="/#roadmap" className="text-muted-foreground hover:text-foreground transition-colors">
            Roadmap
          </Link>
          <Link to="/#delivery" className="text-muted-foreground hover:text-foreground transition-colors">
            Méthode
          </Link>
          <Link to="/#extensions" className="text-muted-foreground hover:text-foreground transition-colors">
            Extensions
          </Link>
          <Link to="/#contact" className="text-muted-foreground hover:text-foreground transition-colors">
            Contact
          </Link>
          <Link to="/legal/privacy" className="text-muted-foreground hover:text-foreground transition-colors">
            Privacy
          </Link>
        </nav>
      </div>
    </footer>
  );
}
