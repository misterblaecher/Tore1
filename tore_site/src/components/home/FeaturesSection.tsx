import { motion } from "framer-motion";
import { Archive, MapPin, Music2, Users, Dice5, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

type ModuleKey = "discovery" | "rooms" | "committee" | "map" | "memory";

const modules: Array<{
  key: ModuleKey;
  icon: LucideIcon;
  title: string;
  description: string;
}> = [
  {
    key: "discovery",
    icon: MapPin,
    title: "Découverte des soirées",
    description:
      "Soirées autour de soi dans le Carré, soirées à venir, filtres par bar, comité, type, date et proximité.",
  },
  {
    key: "rooms",
    icon: Dice5,
    title: "Soirées vivantes",
    description:
      "Rooms locales ou globales, défis, mini-jeux, classements, cadeaux P2P et live feed quand ça sert l’ambiance.",
  },
  {
    key: "committee",
    icon: Users,
    title: "Vie comité & folklore",
    description:
      "Forum, infos nouveaux, traditions, archives, organisation interne et guides de guindaille selon permissions.",
  },
  {
    key: "map",
    icon: Music2,
    title: "Ambiance bar contextualisée",
    description:
      "Quand tu entres dans un bar, TORÈ peut adapter logo, couleurs, fond dynamique et modules actifs du lieu.",
  },
  {
    key: "memory",
    icon: Archive,
    title: "Mémoire guindaille",
    description:
      "Profil, historique de soirées, badges, événements vécus et appartenances à comités, régionales ou ordres.",
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
          <h2 className="text-3xl md:text-4xl font-bold mb-3">L’écosystème qu’on teste à Liège</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            TORÈ se construit en conditions réelles : découvrir, rejoindre, vivre, organiser, archiver.
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
