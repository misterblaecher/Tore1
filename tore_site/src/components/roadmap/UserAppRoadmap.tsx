import {
  Smartphone,
  ScanLine,
  Home,
  Beer,
  Calendar,
  UserPlus,
  LayoutDashboard,
  UtensilsCrossed,
  Wallet,
  Radio,
  TrendingUp,
  Gamepad2,
  Trophy,
  Settings,
} from "lucide-react";

const screens = [
  { id: 1, name: "Splash / Boot", icon: Smartphone, description: "Logo TORÈ + animation glow rubis, loader, gestion offline." },
  { id: 2, name: "Home / Hub", icon: Home, description: "Scanner QR en action reine, cards Bars/Events/Wallet/Polymarket." },
  { id: 3, name: "QR Scanner", icon: ScanLine, description: "Plein écran caméra, cadre rubis, routing intelligent, auto-lampe." },
  { id: 4, name: "Bars", icon: Beer, description: "Grille compacte, statuts OPEN/LIVE/CLOSED, icônes modules actifs." },
  { id: 5, name: "Events (bar)", icon: Calendar, description: "Liste events d'un bar, filtres Live/Today/Upcoming, cards compactes." },
  { id: 6, name: "Join Event", icon: UserPlus, description: "Entrée via QR ou code, CTA JOIN, skip si QR déjà validé." },
  { id: 7, name: "Event Hub", icon: LayoutDashboard, description: "Modules visibles selon activation, banners pause/réseau." },
  { id: 8, name: "Menu Event", icon: UtensilsCrossed, description: "Filtres sticky, liste dense, panier bottom bar, CTA CONFIRMER." },
  { id: 9, name: "Wallet", icon: Wallet, description: "Solde en grand (mono), historique timeline, actions autorisées." },
  { id: 10, name: "Ticker Live", icon: Radio, description: "Feed temps réel (commandes/bets/gifts), filtres + mode pause." },
  { id: 11, name: "Polymarket Global", icon: TrendingUp, description: "Hub global hors soirée, marchés + filtres, charts + stats." },
  { id: 12, name: "Polymarket Event", icon: Gamepad2, description: "Bets liés à la soirée, création par users, résolution animée." },
  { id: 13, name: "Classement", icon: Trophy, description: "Top 3 en cards, liste dense, accessible via Hub/Ticker/Polymarket." },
  { id: 14, name: "Profil & Settings", icon: Settings, description: "Privacy, thème auto, accessibilité, contraste renforcé." },
];

export default function UserAppRoadmap() {
  return (
    <section className="py-16 md:py-24">
      <div className="container">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
              <Smartphone className="text-primary" size={18} />
              <span className="text-sm font-medium">App Mobile</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Roadmap <span className="text-primary neon-text">UI Utilisateur</span>
            </h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              14 écrans clés du parcours utilisateur — du lancement à la gamification.
              L'utilisateur ne voit que les modules activés.
            </p>
          </div>

          {/* Flow indicator */}
          <div className="flex items-center justify-center gap-2 mb-10 text-sm text-muted-foreground">
            <span>Boot</span>
            <span>→</span>
            <span>Home</span>
            <span>→</span>
            <span>Scanner</span>
            <span>→</span>
            <span>Event Hub</span>
            <span>→</span>
            <span>Menu / Wallet / Bets</span>
            <span>→</span>
            <span>Profil</span>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {screens.map((screen) => (
              <div
                key={screen.id}
                className="group p-5 rounded-2xl bg-card border border-border hover:border-primary/30 transition-all duration-300"
              >
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0 group-hover:bg-primary/20 transition-colors">
                    <screen.icon className="text-primary" size={20} />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs text-muted-foreground font-mono">{String(screen.id).padStart(2, "0")}</span>
                      <h3 className="font-semibold text-sm truncate">{screen.name}</h3>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">{screen.description}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Design principles */}
          <div className="mt-10 grid sm:grid-cols-3 gap-4">
            {[
              { label: "Modules ON/OFF", desc: "L'user ne voit que ce qui est activé" },
              { label: "Scanner QR central", desc: "Action reine, routing intelligent" },
              { label: "Lisibilité premium", desc: "Densité contrôlée, animations courtes" },
            ].map((p) => (
              <div key={p.label} className="p-4 rounded-xl bg-muted/10 border border-border text-center">
                <p className="font-semibold text-sm text-primary mb-1">{p.label}</p>
                <p className="text-xs text-muted-foreground">{p.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
