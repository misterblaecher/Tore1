import { motion } from "framer-motion";
import { CalendarDays, CheckCircle2 } from "lucide-react";

const steps = [
  {
    title: "Soirée test 1",
    subtitle: "Découverte • Live • Dashboard",
    note: "On valide le terrain. QR contextuel, rooms encadrées et credits activables selon besoin.",
  },
  {
    title: "Soirée test 2",
    subtitle: "+ Musique V0",
    note: "Vote simple (A/B/C) + override staff. On mesure la friction avec le DJ.",
  },
  {
    title: "Soirée test 3",
    subtitle: "+ Map de la salle",
    note: "Les gens se retrouvent sans spammer Messenger. Position volontaire.",
  },
  {
    title: "Soirée test 4",
    subtitle: "+ Paris (crédits internes)",
    note: "Engagement ponctuel. Résolution simple. Aucun cash-out.",
  },
];

export function TeaserSection() {
  return (
    <section id="tests" className="py-20 md:py-28 border-t border-border/40">
      <div className="container">
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border/50 text-sm text-muted-foreground mb-4">
            <CalendarDays size={16} />
            Build → Test → Observer → Ajuster
          </div>
          <h2 className="text-3xl md:text-4xl font-bold">Soirées test modulaires</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto mt-3">
            On ne lance pas 12 features d’un coup. On avance module par module, et c’est le terrain qui décide.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-5 max-w-5xl mx-auto">
          {steps.map((s, idx) => (
            <motion.div
              key={s.title}
              className="p-6 rounded-xl bg-card/60 border border-border/40"
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.06, duration: 0.35 }}
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg border border-border/50 flex items-center justify-center shrink-0">
                  <CheckCircle2 size={18} className="text-foreground/80" />
                </div>
                <div>
                  <h3 className="text-base font-semibold">{s.title}</h3>
                  <p className="text-sm text-foreground/80 mt-1">{s.subtitle}</p>
                  <p className="text-sm text-muted-foreground mt-2 leading-relaxed">{s.note}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
