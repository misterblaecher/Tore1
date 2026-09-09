import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { ArrowUpRight, CircleUserRound, Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getToken } from "@/lib/auth";
import { siteNavigation } from "@/lib/site-navigation";
import logoFull from "@/assets/logo-full.png";
import "@/styles/site-navigation.css";

export function Header() {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();
  const authenticated = Boolean(getToken());
  useEffect(() => { setIsOpen(false); }, [location.pathname, location.hash]);
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setIsOpen(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  return <header className="site-header">
    <div className="container site-header__inner">
      <Link className="site-header__brand" to="/" aria-label="TORÈ — Accueil"><img src={logoFull} alt="" /><span>TORÈ<small>Le projet</small></span></Link>
      <nav aria-label="Navigation du site" className="site-header__desktop">
        {siteNavigation.map(({ href, label }) => <NavLink key={href} to={href} end>{label}</NavLink>)}
      </nav>
      <div className="site-header__actions">
        <Link className="site-header__account" to={authenticated ? "/compte" : "/login"} aria-label={authenticated ? "Ouvrir mon profil" : "Se connecter"}><CircleUserRound size={19} /><span>{authenticated ? "Mon compte" : "Connexion"}</span></Link>
        <Button asChild size="sm"><Link to="/forum">Forum <ArrowUpRight size={16} /></Link></Button>
        <button className="site-header__toggle" aria-label={isOpen ? "Fermer le menu" : "Ouvrir le menu"} aria-expanded={isOpen} aria-controls="site-mobile-menu" onClick={() => setIsOpen(!isOpen)}>{isOpen ? <X size={22} /> : <Menu size={22} />}</button>
      </div>
    </div>
    {isOpen ? <nav id="site-mobile-menu" className="site-header__mobile" aria-label="Navigation mobile">
      {siteNavigation.map(({ href, label }) => <NavLink key={href} to={href} end onClick={() => setIsOpen(false)}>{label}</NavLink>)}
      <Link to="/rejoindre" onClick={() => setIsOpen(false)}>Rejoindre la bêta</Link>
      <Link to={authenticated ? "/compte" : "/login"} onClick={() => setIsOpen(false)}>{authenticated ? "Mon compte" : "Se connecter"}</Link>
    </nav> : null}
  </header>;
}
