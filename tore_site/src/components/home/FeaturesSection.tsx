import { motion } from "framer-motion";
import { BarChart3, MapPin, Music2, Package, Dice5, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

type ModuleKey = "music" | "bets" | "dashboard" | "map" | "inventory";

const modules: Array<{
  key: ModuleKey;
  icon: LucideIcon;
  title: string;
  description: string;
}> = [
  {
    key: "music",
    icon: Music2,
    title: "Contrôle musique (pré-soirée + live)",
    description:
      "Les étudiants définissent leurs goûts avant l’event. Le comité/DJ voit un résumé clair + votes simples en live.",
  },
  {
    key: "bets",
    icon: Dice5,
    title: "Paris fun pendant la soirée",
    description:
      "Des mini-paris sur la soirée (entrées, ambiance, défis). Crédits internes. Pas besoin d’être collé au téléphone.",
  },
  {
    key: "dashboard",
    icon: BarChart3,
    title: "Dashboard comité (terrain)",
    description:
      "Entrées en live, capacité, stats de rush, export. Un cockpit simple pour gérer une all‑in sans stress.",
  },
  {
    key: "map",
    icon: MapPin,
    title: "Map de la salle pour se retrouver",
    description:
      "Une carte simple (bar, toilettes, DJ, fumoir…). Les gens indiquent où ils sont — sans tracking automatique.",
  },
  {
    key: "inventory",
    icon: Package,
    title: "Inventaire pré / post soirée",
    description:
      "Checklist matériel (barrières, pompes, toilettes…), stock (fûts, soft, gobelets) et rapport fin de soirée.",
  },
];

function bumpInterest(key: ModuleKey) {
  try {
    const raw = localStorage.getItem("tore_interest") || "{}";
    const data = JSON.parse(raw) as Record<string, number>;
    data[key] = (data[key] || 0) + 1;
    localStorage.setItem("tore_interest", JSON.stringify(data));
    localStorage.setItem("tore_waitlist_module", key);
  } catch {
    // ignore
  }
}

export function FeaturesSection() {
  return (
    <section id="modules" className="py-20 md:py-28">
      <div className="container">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold mb-3">Les modules qu’on teste à Liège</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            TORÈ se construit en conditions réelles : 1 module → 1 soirée test → feedback → amélioration.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 md:gap-6">
          {modules.map((m, index) => (
            <motion.div
              key={m.key}
              className="group p-6 rounded-xl bg-card/60 border border-border/40 hover:border-foreground/20 transition-all duration-300 relative overflow-hidden"
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.06, duration: 0.35 }}
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg border border-border/50 flex items-center justify-center shrink-0">
                  <m.icon className="text-foreground/80" size={18} />
                </div>
                <div className="min-w-0">
                  <h3 className="text-base font-semibold leading-snug">{m.title}</h3>
                  <p className="text-sm text-muted-foreground mt-2 leading-relaxed">{m.description}</p>
                </div>
              </div>

              <div className="mt-5 flex items-center justify-between gap-3">
                <span className="text-xs text-muted-foreground">Bientôt en test à Liège</span>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    bumpInterest(m.key);
                    document.getElementById("waitlist")?.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  Ça m’intéresse
                </Button>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
