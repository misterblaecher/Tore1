import { Link } from "react-router-dom";
import { Beer, Users, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";

export function ForWhoSection() {
  return (
    <section className="py-20 md:py-28 relative texture-grain">
      {/* Subtle ember ambient */}
      <div className="absolute inset-0" style={{ background: 'radial-gradient(ellipse at 50% 50%, hsl(0 60% 18% / 0.08) 0%, transparent 60%)' }} />
      
      <div className="container relative z-10">
        <div className="text-center mb-12">
          <h2 className="font-ritual text-3xl md:text-4xl font-bold mb-4 tracking-wide">Pour qui ?</h2>
          <p className="text-muted-foreground max-w-lg mx-auto">
            TORÈ relie les étudiants, les bars, les comités et les organisateurs sans réduire l’expérience à un scan.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6 md:gap-8 max-w-4xl mx-auto">
          {[
            {
              icon: Beer,
              title: "Bars & Restaurants",
              items: [
                "Page lieu avec identité visuelle, ambiance et soirées en cours",
                "Modules bar activables : menu, commandes, wallet, événements",
                "Actions QR contextuelles pour entrée, staff ou accès sensible",
                "Analytics et exports côté portail, pas de bruit côté utilisateur",
              ],
              href: "/bars",
            },
            {
              icon: Users,
              title: "Comités & Organisateurs",
              items: [
                "Créer, publier et animer une soirée avec détail avant join",
                "Forum, archives, annonces et passation comité",
                "Défis, Polymarket, ticker et classements selon modules actifs",
                "Mémoire annuelle, badges et historique exploitable",
              ],
              href: "/comites",
            },
          ].map((card, index) => (
            <motion.div
              key={card.title}
              className="group relative p-8 md:p-10 rounded-lg bg-card border border-border/50 hover:border-accent/30 transition-all duration-500 overflow-hidden"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.15, duration: 0.5 }}
            >
              <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-accent/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
              
              <div className="relative">
                <div className="w-14 h-14 rounded-lg border border-accent/20 flex items-center justify-center mb-6">
                  <card.icon className="text-accent" size={26} />
                </div>
                
                <h3 className="font-ritual text-2xl font-bold mb-4 tracking-wide">{card.title}</h3>
                
                <ul className="space-y-2 mb-6 text-muted-foreground text-sm">
                  {card.items.map((item) => (
                    <li key={item} className="flex items-start gap-2">
                      <span className="text-accent mt-0.5 text-xs">◆</span>
                      {item}
                    </li>
                  ))}
                </ul>
                
                <Link to={card.href}>
                  <Button variant="ghost" className="group/btn text-accent hover:text-accent px-0">
                    En savoir plus
                    <ArrowRight size={16} className="ml-2 group-hover/btn:translate-x-1 transition-transform" />
                  </Button>
                </Link>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
