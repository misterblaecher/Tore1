import {
  Smartphone,
  Compass,
  Home,
  Beer,
  Calendar,
  UserPlus,
  LayoutDashboard,
  UtensilsCrossed,
  WalletCards,
  Radio,
  TrendingUp,
  Gamepad2,
  Trophy,
  Settings,
} from "lucide-react";

const screens = [
  { id: 1, name: "Splash / Boot", icon: Smartphone, description: "Logo TORÈ + animation glow rubis, loader, gestion offline." },
  { id: 2, name: "Découverte", icon: Compass, description: "Soirées autour de soi, à venir, filtres bar/comité/type/date/proximité." },
  { id: 3, name: "Détail soirée", icon: Calendar, description: "Description, organisateur, lieu, modules actifs, infos pratiques, rejoindre." },
  { id: 4, name: "Bars", icon: Beer, description: "Identité du lieu, ambiance visuelle, événements et modules actifs." },
  { id: 5, name: "Events (bar)", icon: Calendar, description: "Liste events d'un bar, filtres Live/Today/Upcoming, cards compactes." },
  { id: 6, name: "Rejoindre", icon: UserPlus, description: "Étape détail obligatoire, puis rejoindre par bouton, code ou QR contextuel." },
  { id: 7, name: "Hub soirée", icon: LayoutDashboard, description: "Modules visibles selon activation, états discrets côté utilisateur." },
  { id: 8, name: "Menu Event", icon: UtensilsCrossed, description: "Filtres sticky, liste dense, panier bottom bar, CTA CONFIRMER." },
  { id: 9, name: "Credits & rewards", icon: WalletCards, description: "Credits, rewards, historique timeline, actions autorisées." },
  { id: 10, name: "Ticker Live", icon: Radio, description: "Feed temps réel (commandes/rooms/gifts), filtres + mode pause." },
  { id: 11, name: "Rooms globales", icon: TrendingUp, description: "Hub global hors soirée, rooms + filtres, charts + stats." },
  { id: 12, name: "Rooms soirée", icon: Gamepad2, description: "Prédictions liées à la soirée, création par users, résolution animée." },
  { id: 13, name: "Classement", icon: Trophy, description: "Top 3 en cards, liste dense, accessible via Hub/Ticker/Rooms." },
  { id: 14, name: "Profil & mémoire", icon: Settings, description: "Historique, badges, appartenances, privacy et accessibilité." },
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
              14 écrans clés du parcours utilisateur — découverte, live, comités et mémoire.
              L'utilisateur ne voit que les modules activés.
            </p>
          </div>

          {/* Flow indicator */}
          <div className="flex items-center justify-center gap-2 mb-10 text-sm text-muted-foreground">
            <span>Boot</span>
            <span>→</span>
            <span>Home</span>
            <span>→</span>
            <span>Découverte</span>
            <span>→</span>
            <span>Détail soirée</span>
            <span>→</span>
            <span>Menu / Credits / Rooms</span>
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
              { label: "Découverte-first", desc: "Soirées proches et détail avant join" },
              { label: "QR contextuel", desc: "Join rapide, entrée, actions sensibles" },
              { label: "Mémoire guindaille", desc: "Profil, badges, comités, archives" },
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
