import { ArrowRight, Building2, LockKeyhole, UserRound } from "lucide-react";
import { Link, useOutletContext } from "react-router-dom";
import { getToken } from "@/lib/auth";
import { ForumNavigationContext, structurePath } from "@/lib/forum-navigation";
import "@/styles/forum.css";

export default function ForumHome() {
  const { workspace, loading, error } = useOutletContext<ForumNavigationContext>();
  const authenticated = Boolean(getToken());
  const primaryHref = workspace ? structurePath(workspace.slug) : "/forum/structures";
  const createHref = "/forum/structures?creer=1#create-structure";
  return <main className="forum-page"><div className="forum-container">
    <header className="forum-landing-head forum-home-hero">
      <div><span className="forum-eyebrow">Vous êtes dans le Forum TORÈ</span><h1>{workspace ? "Votre communauté, votre espace." : "Bienvenue dans la communauté."}</h1><p>{workspace ? `Retrouvez le tableau de bord de ${workspace.name}, vos discussions et les outils de votre structure.` : "Explorez les structures étudiantes ou connectez-vous pour retrouver votre comité. Ici, on échange, on organise et on transmet."}</p></div>
      <Link className="forum-button forum-button--primary" to={primaryHref}>{workspace ? "Reprendre mon espace" : "Explorer les structures"}<ArrowRight size={16} /></Link>
    </header>
    <section className="forum-home-grid" aria-label="Destinations du Forum">
      <Link className="forum-home-card" to={primaryHref}><span className="forum-eyebrow">{workspace ? "Votre structure" : "Annuaire public"}</span><Building2 size={22} /><h2>{workspace?.name ?? "Explorer les structures"}</h2><p>{workspace ? "Ouvrez directement votre tableau de bord. Changez de comité depuis le sélecteur à gauche." : "Découvrez les pages officielles des comités, cercles et ordres, accessibles sans connexion."}</p><span className="forum-home-card__link">{workspace ? "Ouvrir le tableau de bord" : "Consulter l’annuaire"}<ArrowRight size={15} /></span></Link>
      <Link className="forum-home-card" to={authenticated ? "/compte" : "/forum/login"} state={authenticated ? undefined : { from: "/forum" }}><span className="forum-eyebrow">Compte unique TORÈ</span><UserRound size={22} /><h2>{authenticated ? "Mon profil" : "Retrouver mon comité"}</h2><p>{authenticated ? "Consultez votre profil, vos appartenances et vos mandats. Les accès du comité sont distincts de vos informations personnelles." : "Connectez-vous avec le compte de l’application. Vos structures et leurs accès seront retrouvés automatiquement."}</p><span className="forum-home-card__link">{authenticated ? "Modifier mon profil" : "Se connecter"}<ArrowRight size={15} /></span></Link>
      <Link className="forum-home-card" to={authenticated ? createHref : "/forum/login"} state={authenticated ? undefined : { from: createHref }}><span className="forum-eyebrow">Nouveau collectif</span><LockKeyhole size={22} /><h2>Créer une structure</h2><p>Votre comité n’a pas encore d’espace ? Créez sa structure puis configurez ses membres et sa page publique.</p><span className="forum-home-card__link">{authenticated ? "Commencer la création" : "Se connecter pour créer"}<ArrowRight size={15} /></span></Link>
    </section>
    {authenticated && !loading && !workspace ? <section className="forum-home-note"><div><span className="forum-eyebrow">Vos accès</span><h2>{error ? "Vos structures sont indisponibles." : "Pas encore d’espace actif."}</h2></div><p>{error ? "Réessayez depuis le sélecteur à gauche. L’annuaire public reste accessible." : "Un ancien mandat ne donne pas accès à la gestion. Demandez à un responsable de votre structure de vous inviter ou de vérifier vos accès actuels."}</p></section> : null}
    <div className="forum-home-note"><div><span className="forum-eyebrow">Vous cherchiez l’application ?</span><h2>Le site présente. Le Forum rassemble.</h2></div><Link className="forum-button forum-button--ghost" to="/produit">Découvrir l’application<ArrowRight size={16} /></Link></div>
  </div></main>;
}
