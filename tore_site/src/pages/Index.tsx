import { Link, Navigate, useLocation } from "react-router-dom";
import { ArrowRight, Building2, CalendarDays, MessageSquare, Smartphone, UserRound } from "lucide-react";
import { Header, Footer } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { getToken } from "@/lib/auth";
import { legacySiteAnchors } from "@/lib/site-navigation";

const paths = [
  { number: "01", icon: Smartphone, title: "Découvrir l’application", description: "Comprendre TORÈ, ses fonctionnalités et l’expérience en soirée.", href: "/produit", action: "Voir l’application" },
  { number: "02", icon: Building2, title: "Organiser avec son comité", description: "Découvrir les outils pour préparer vos événements et faire vivre votre collectif.", href: "/comites", action: "Découvrir les outils" },
  { number: "03", icon: MessageSquare, title: "Retrouver sa communauté", description: "Ouvrir le Forum, explorer les structures ou retrouver votre espace membre.", href: "/forum", action: "Accéder au Forum" },
];

export default function Index() {
  const location = useLocation();
  const destination = legacySiteAnchors[location.hash];
  if (destination) {
    const [pathname, hash] = destination.split("#");
    return <Navigate replace to={{ pathname, search: location.search, hash: hash ? `#${hash}` : "" }} />;
  }
  return <div className="site-home min-h-screen bg-background text-foreground">
    <Header />
    <main>
      <section className="site-home__hero section-ember-texture">
        <div className="container">
          <p className="site-kicker">TORÈ · La vie étudiante, ensemble</p>
          <h1>Vos soirées.<br />Votre comité.<br /><span>Un même univers.</span></h1>
          <p className="site-home__intro">Une application pour vivre les soirées. Un Forum pour organiser, échanger et transmettre. Un seul compte pour retrouver votre place dans TORÈ.</p>
          <div className="site-home__actions">
            <Button asChild size="lg"><Link to="/produit">Découvrir l’application <ArrowRight size={17} /></Link></Button>
            <Button asChild variant="outline" size="lg"><Link to="/forum">Accéder au Forum <MessageSquare size={17} /></Link></Button>
          </div>
          <Link className="site-home__beta" to="/rejoindre">Déjà convaincu ? Rejoindre la bêta →</Link>
        </div>
      </section>
      <section className="container site-home__paths" aria-labelledby="paths-title">
        <div className="site-home__section-heading"><div><p className="site-kicker">À chacun son entrée</p><h2 id="paths-title">Que souhaitez-vous faire ?</h2></div><p>Choisissez votre point de départ.<br />Votre compte reste le même.</p></div>
        <div className="site-home__grid">{paths.map(({ number, icon: Icon, title, description, href, action }) => <Link className="site-path" to={href} key={href}><div className="site-path__top"><Icon size={25} /><span>{number}</span></div><h3>{title}</h3><p>{description}</p><span className="site-path__action">{action}<ArrowRight size={17} /></span></Link>)}</div>
      </section>
      <section className="container site-home__continuity">
        <div><p className="site-kicker">Du site à votre espace</p><h2>Un compte.<br />Toutes vos appartenances.</h2><p>Votre profil, vos rôles et vos oripeaux vous suivent entre l’application et le Forum. Le site présente TORÈ ; le Forum est votre espace de communauté.</p><Button asChild variant="outline"><Link to={getToken() ? "/compte" : "/login"}><UserRound size={16} />{getToken() ? "Retrouver mon profil" : "Créer ou ouvrir mon compte"}</Link></Button></div>
        <aside><CalendarDays size={25} /><p className="site-kicker">La suite de TORÈ</p><h3>Un projet qui se construit avec vous.</h3><p>Consultez les étapes de développement et les fonctionnalités prévues.</p><Link to="/roadmap">Consulter la roadmap <ArrowRight size={16} /></Link><Link to="/contact">Contacter l’équipe <ArrowRight size={16} /></Link></aside>
      </section>
    </main>
    <Footer />
  </div>;
}
