import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="border-t border-border/50 bg-background">
      <div className="container py-8 md:py-10 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <p className="text-sm text-muted-foreground">© {new Date().getFullYear()} TORÈ — OS Numérique Territorial.</p>
        <nav className="flex items-center gap-6 text-sm">
          <a href="#" className="text-muted-foreground hover:text-foreground transition-colors">
            Documentation
          </a>
          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            GitHub
          </a>
          <Link to="/#contact" className="text-muted-foreground hover:text-foreground transition-colors">
            Contact
          </Link>
        </nav>
      </div>
    </footer>
  );
}
