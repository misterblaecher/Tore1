import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import logoFull from "@/assets/logo-full.png";

const navLinks = [
  { label: "Problème", href: "/#probleme" },
  { label: "Solution", href: "/#solution" },
  { label: "Modules", href: "/#modules" },
  { label: "Roadmap", href: "/#roadmap" },
  { label: "Méthode", href: "/#delivery" },
  { label: "Extensions", href: "/#extensions" },
  { label: "Positionnement", href: "/#positionnement" },
  { label: "Contact", href: "/#contact" },
];

export function Header() {
  const [isOpen, setIsOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const isActive = (href: string) => {
    if (href.startsWith("/#")) return location.hash === href.replace("/", "");
    return location.pathname === href;
  };

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled ? "bg-background/90 backdrop-blur-lg border-b border-border/50" : "bg-transparent"
      }`}
    >
      <div className="container flex items-center justify-between h-16 md:h-20">
        <Link to="/" className="flex items-center gap-2 hover:opacity-90 transition-opacity">
          <img src={logoFull} alt="TORÈ" className="h-8 md:h-10 w-auto" />
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              to={link.href}
              className={`text-sm font-medium tracking-wide transition-colors hover:text-accent ${
                isActive(link.href) ? "text-accent" : "text-muted-foreground"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-4">
          <Link to="/bars">
            <Button size="sm" className="text-xs font-semibold">
              Accès Bar / Comité
            </Button>
          </Link>
        </div>

        <button
          onClick={() => setIsOpen(!isOpen)}
          className="md:hidden p-2 text-foreground hover:text-accent transition-colors"
          aria-label="Toggle menu"
        >
          {isOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {isOpen && (
        <div className="md:hidden absolute top-16 left-0 right-0 bg-background/95 backdrop-blur-lg border-b border-border animate-fade-in">
          <nav className="container py-6 flex flex-col gap-4">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                to={link.href}
                onClick={() => setIsOpen(false)}
                className={`text-lg font-medium py-2 transition-colors hover:text-accent ${
                  isActive(link.href) ? "text-accent" : "text-foreground"
                }`}
              >
                {link.label}
              </Link>
            ))}
            <div className="flex flex-col gap-3 pt-4 border-t border-border">
              <Link to="/bars" onClick={() => setIsOpen(false)}>
                <Button className="w-full font-semibold">Accès Bar / Comité</Button>
              </Link>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
