import { 
  QrCode, 
  Clock, 
  Users, 
  TrendingUp, 
  UtensilsCrossed, 
  UserCog 
} from "lucide-react";
import { motion } from "framer-motion";

const features = [
  {
    icon: QrCode,
    title: "QR universel + routing",
    description: "Un seul QR qui route vers menu, event, entrée, staff selon le contexte. Fallback intelligent.",
  },
  {
    icon: Clock,
    title: "Création event en 60s",
    description: "Templates prêts, pack QR imprimable, tout est prêt pour votre prochaine soirée.",
  },
  {
    icon: Users,
    title: "Entrée & comptage",
    description: "Comptage temps réel avec mode estimation. Alertes capacité. Historique complet.",
  },
  {
    icon: TrendingUp,
    title: "Rentabilité live",
    description: "Suivez recettes vs coûts en temps réel. Rapport fin de soirée en un clic.",
  },
  {
    icon: UtensilsCrossed,
    title: "Menu QR + zones",
    description: "Menu digital par zone avec tracking des scans, vues items, ajouts panier.",
  },
  {
    icon: UserCog,
    title: "Rôles staff via QR",
    description: "Attribuez permissions sans app. Révocation instantanée. Audit complet.",
  },
];

export function FeaturesSection() {
  return (
    <section className="py-20 md:py-28 relative">
      <div className="container">
        <div className="text-center mb-12">
          <h2 className="font-ritual text-3xl md:text-4xl font-bold mb-4 tracking-wide">
            Les <span className="text-gradient-gold">modules</span> TORÈ
          </h2>
          <p className="text-muted-foreground max-w-lg mx-auto">
            Tout ce qu'il faut pour régner sur bars et events.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 md:gap-6">
          {features.map((feature, index) => (
            <motion.div 
              key={feature.title}
              className="group p-6 rounded-lg bg-card/60 border border-border/30 hover:border-ember/20 transition-all duration-500 relative overflow-hidden"
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.07, duration: 0.4 }}
            >
              {/* Subtle glow on hover */}
              <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-3/4 h-px bg-gradient-to-r from-transparent via-ember/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
              
              <div className="w-10 h-10 rounded-md border border-accent/15 flex items-center justify-center mb-4 group-hover:border-accent/30 transition-colors duration-500">
                <feature.icon className="text-accent/80 group-hover:text-accent transition-colors duration-300" size={18} />
              </div>
              <h3 className="text-base font-semibold mb-2">{feature.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
