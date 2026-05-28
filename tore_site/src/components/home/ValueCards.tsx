import { CalendarSearch, Sparkles, BookOpen } from "lucide-react";
import { motion } from "framer-motion";

const valueCards = [
  {
    icon: CalendarSearch,
    title: "Découverte d’abord",
    description: "Soirées proches, à venir, filtrées par lieu, comité, type, date et proximité.",
  },
  {
    icon: Sparkles,
    title: "Expérience live",
    description: "Défis, marchés, interactions sociales et modules activés selon l’ambiance de la soirée.",
  },
  {
    icon: BookOpen,
    title: "Mémoire collective",
    description: "Comités, archives, traditions, badges et historique personnel de guindaille.",
  },
];

export function ValueCards() {
  return (
    <section className="py-20 md:py-28 relative">
      <div className="container">
        <div className="text-center mb-12">
          <h2 className="font-ritual text-3xl md:text-4xl font-bold mb-4 tracking-wide">
            Pourquoi <span className="text-gradient-gold">TORÈ</span> ?
          </h2>
          <p className="text-muted-foreground max-w-lg mx-auto">
            Une app pensée pour la vie nocturne liégeoise : sociale, utile, vivante et fiable.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6 md:gap-8">
          {valueCards.map((card, index) => (
            <motion.div
              key={card.title}
              className="group p-6 md:p-8 rounded-lg bg-card border border-border/50 hover:border-accent/30 transition-all duration-500 relative overflow-hidden"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1, duration: 0.5 }}
            >
              {/* Hover ember glow */}
              <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700"
                style={{ background: 'radial-gradient(circle at 50% 0%, hsl(8 80% 48% / 0.06) 0%, transparent 60%)' }}
              />
              <div className="relative">
                <div className="w-12 h-12 rounded-lg border border-accent/20 flex items-center justify-center mb-4 group-hover:border-accent/40 transition-colors duration-500">
                  <card.icon className="text-accent" size={22} />
                </div>
                <h3 className="text-xl font-bold mb-2 text-foreground">{card.title}</h3>
                <p className="text-muted-foreground text-sm">{card.description}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
