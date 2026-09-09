import { CircleUserRound, Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { getToken } from "@/lib/auth";

const forumLinks = [
  { label: "Accueil", href: "/forum" },
  { label: "Structures", href: "/forum/structures" },
];

export function ForumHeader() {
  const [isOpen, setIsOpen] = useState(false);
  const [authenticated, setAuthenticated] = useState(() => Boolean(getToken()));
  const location = useLocation();

  useEffect(() => {
    setAuthenticated(Boolean(getToken()));
  }, [location.pathname]);

  const isActive = (href: string) => href === "/forum"
    ? location.pathname === "/forum"
    : location.pathname === href || location.pathname.startsWith(`${href}/`);
  const accountHref = authenticated ? "/compte" : "/forum/login";

  return (
    <header className="forum-shell-header">
      <div className="forum-shell-header__inner">
        <Link className="forum-shell-brand" to="/forum" aria-label="TORÈ Forum">
          <span className="forum-shell-brand__mark">T</span>
          <span>
            <strong>TORÈ</strong>
            <small>Forum & structures</small>
          </span>
        </Link>

        <nav className="forum-shell-nav" aria-label="Navigation du Forum">
          {forumLinks.map((link) => (
            <Link
              key={link.href}
              to={link.href}
              className={isActive(link.href) ? "active" : undefined}
              aria-current={isActive(link.href) ? "page" : undefined}
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="forum-shell-actions">
          <Link className="forum-shell-return" to="/">
            Présentation TORÈ
          </Link>
          <Link className="forum-shell-account" to={accountHref} title={authenticated ? "Ouvrir mon profil" : "Se connecter"}>
            <CircleUserRound size={19} aria-hidden="true" />
            <span>{authenticated ? "Mon profil" : "Se connecter"}</span>
          </Link>
        </div>

        <button
          type="button"
          className="forum-shell-menu"
          onClick={() => setIsOpen((open) => !open)}
          aria-label={isOpen ? "Fermer le menu du Forum" : "Ouvrir le menu du Forum"}
          aria-expanded={isOpen}
        >
          {isOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {isOpen ? (
        <nav className="forum-shell-mobile" aria-label="Navigation mobile du Forum">
          {forumLinks.map((link) => (
            <Link key={link.href} to={link.href} onClick={() => setIsOpen(false)}>
              {link.label}
            </Link>
          ))}
          <Link to={accountHref} onClick={() => setIsOpen(false)}>
            <CircleUserRound size={18} aria-hidden="true" />
            {authenticated ? "Mon profil" : "Se connecter"}
          </Link>
          <Link to="/" onClick={() => setIsOpen(false)}>
            Retour à la présentation
          </Link>
        </nav>
      ) : null}
    </header>
  );
}
