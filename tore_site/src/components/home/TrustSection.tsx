import { Shield, FileCheck, Lock } from "lucide-react";
import { motion } from "framer-motion";

const trustItems = [
  {
    icon: Shield,
    title: "QR signés & expiration",
    description: "Chaque QR sensible est signé cryptographiquement avec durée de vie limitée.",
  },
  {
    icon: FileCheck,
    title: "Ledger append-only",
    description: "Toutes les actions sont tracées dans un journal immuable. Audit complet garanti.",
  },
  {
    icon: Lock,
    title: "RGPD & privacy",
    description: "Consentements explicites, privacy toggles, rétention maîtrisée. Vous restez aux commandes.",
  },
];

export function TrustSection() {
  return (
    <section className="py-20 md:py-28 relative texture-grain">
      <div className="absolute inset-0" style={{ background: 'radial-gradient(ellipse at 50% 50%, hsl(0 60% 18% / 0.06) 0%, transparent 50%)' }} />
      
      <div className="container relative z-10">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="font-ritual text-3xl md:text-4xl font-bold mb-4 tracking-wide">
              Sécurité & <span className="text-gradient-gold">confiance</span>
            </h2>
            <p className="text-muted-foreground max-w-lg mx-auto">
              Pas de compromis sur la sécurité. Vos données, votre contrôle.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 md:gap-8">
            {trustItems.map((item, index) => (
              <motion.div 
                key={item.title} 
                className="text-center"
                initial={{ opacity: 0, y: 15 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1, duration: 0.5 }}
              >
                <div className="w-14 h-14 rounded-lg border border-accent/20 flex items-center justify-center mx-auto mb-4">
                  <item.icon className="text-accent" size={24} />
                </div>
                <h3 className="text-lg font-semibold mb-2">{item.title}</h3>
                <p className="text-sm text-muted-foreground">{item.description}</p>
              </motion.div>
            ))}
          </div>

          <motion.div 
            className="mt-12 p-6 rounded-lg border border-accent/10 bg-card/40 text-center"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
          >
            <p className="text-muted-foreground text-sm">
              <strong className="text-accent font-ritual tracking-wide">Philosophie "pas de police"</strong> — Warnings plutôt que blocages. 
              Modules désactivables. Vous gardez le contrôle.
            </p>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
