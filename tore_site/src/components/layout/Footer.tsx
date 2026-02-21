import { Link } from "react-router-dom";
import { Mail, Instagram, Linkedin, Twitter } from "lucide-react";
import logoFull from "@/assets/logo-full.png";

const footerLinks = {
  produit: [
    { label: "Fonctionnalités", href: "/produit" },
    { label: "Pour les bars", href: "/bars" },
    { label: "Pour les comités", href: "/comites" },
    { label: "Roadmap", href: "/roadmap" },
  ],
  ressources: [
    { label: "Pricing", href: "/pricing" },
    { label: "Sécurité & RGPD", href: "/trust" },
    { label: "Contact", href: "/contact" },
    { label: "FAQ", href: "/contact#faq" },
  ],
  legal: [
    { label: "Privacy Policy", href: "/legal/privacy" },
    { label: "Terms of Service", href: "/legal/terms" },
    { label: "Cookies", href: "/legal/cookies" },
  ],
};

const socialLinks = [
  { icon: Instagram, href: "#", label: "Instagram" },
  { icon: Twitter, href: "#", label: "Twitter" },
  { icon: Linkedin, href: "#", label: "LinkedIn" },
];

export function Footer() {
  return (
    <footer className="relative bg-background border-t border-border/30 texture-grain">
      {/* Top ember glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-1/2 h-px bg-gradient-to-r from-transparent via-ember/40 to-transparent" />
      
      <div className="container relative z-10 py-12 md:py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12">
          {/* Brand */}
          <div className="col-span-2 md:col-span-1">
            <Link to="/" className="inline-block mb-4">
              <img src={logoFull} alt="TORÈ" className="h-8 w-auto" />
            </Link>
            <p className="text-sm text-muted-foreground mb-4 max-w-xs">
              Le QR universel des soirées étudiantes. Conçu pour le terrain.
            </p>
            <a
              href="mailto:contact@tore.app"
              className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-accent transition-colors"
            >
              <Mail size={16} />
              contact@tore.app
            </a>
          </div>

          {/* Produit */}
          <div>
            <h4 className="font-ritual text-sm font-semibold text-accent tracking-wider mb-4">Produit</h4>
            <ul className="space-y-3">
              {footerLinks.produit.map((link) => (
                <li key={link.href}>
                  <Link to={link.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Ressources */}
          <div>
            <h4 className="font-ritual text-sm font-semibold text-accent tracking-wider mb-4">Ressources</h4>
            <ul className="space-y-3">
              {footerLinks.ressources.map((link) => (
                <li key={link.href}>
                  <Link to={link.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="font-ritual text-sm font-semibold text-accent tracking-wider mb-4">Légal</h4>
            <ul className="space-y-3">
              {footerLinks.legal.map((link) => (
                <li key={link.href}>
                  <Link to={link.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom */}
        <div className="mt-12 pt-8 border-t border-border/30 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} TORÈ. Tous droits réservés.
          </p>

          {/* Social */}
          <div className="flex items-center gap-4">
            {socialLinks.map((social) => (
              <a
                key={social.label}
                href={social.href}
                aria-label={social.label}
                className="p-2 rounded-full border border-border/50 text-muted-foreground hover:border-accent hover:text-accent transition-all duration-300"
              >
                <social.icon size={16} />
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
