import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { ChevronDown, Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { WAITLIST_URL, WHATSAPP_URL } from "@/lib/external-links";
import logoFull from "@/assets/logo-full.png";

const mainNavLinks = [
  { label: "Plateforme", href: "/#solution" },
  { label: "Modules", href: "/#modules" },
  { label: "Roadmap", href: "/#roadmap" },
  { label: "Contact", href: "/#contact" },
];

const sectionLinks = [
  { label: "Méthode", href: "/#delivery" },
  { label: "Extensions", href: "/#extensions" },
  { label: "Positionnement", href: "/#positioning" },
  { label: "Bêta", href: "/#beta" },
  { label: "Compte", href: "/#account" },
  { label: "Feedback", href: "/#feedback" },
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

        <nav className="hidden md:flex items-center gap-6">
          {mainNavLinks.map((link) => (
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
          <DropdownMenu>
            <DropdownMenuTrigger className="inline-flex items-center gap-1 text-sm font-medium tracking-wide text-muted-foreground transition-colors hover:text-accent outline-none">
              Sections <ChevronDown size={16} />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52 border-border/80 bg-card/95 backdrop-blur-lg">
              {sectionLinks.map((link) => (
                <DropdownMenuItem key={link.href} asChild>
                  <Link to={link.href}>{link.label}</Link>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <a href={WHATSAPP_URL} target="_blank" rel="noreferrer">
            <Button size="sm" className="text-xs font-semibold">
              Accès Bar / Comité
            </Button>
          </a>
          <a href={WAITLIST_URL || "/#waitlist"} target={WAITLIST_URL ? "_blank" : undefined} rel={WAITLIST_URL ? "noreferrer" : undefined}>
            <Button size="sm" variant="outline" className="text-xs font-semibold border-accent/40 hover:bg-accent/10">
              Rejoindre la bêta
            </Button>
          </a>
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
            {[...mainNavLinks, ...sectionLinks].map((link) => (
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
            <div className="pt-4 border-t border-border">
              <a href={WHATSAPP_URL} target="_blank" rel="noreferrer" onClick={() => setIsOpen(false)}>
                <Button className="w-full font-semibold">Accès Bar / Comité</Button>
              </a>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
