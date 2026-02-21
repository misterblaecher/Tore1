import { Link } from "react-router-dom";
import { ArrowRight, Map, CreditCard } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";

export function TeaserSection() {
  return (
    <section className="py-20 md:py-28">
      <div className="container">
        <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {/* Roadmap Teaser */}
          <motion.div
            className="group p-8 rounded-lg bg-card border border-ember/15 hover:border-ember/30 transition-all duration-500 relative overflow-hidden"
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
          >
            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700"
              style={{ background: 'radial-gradient(circle at 30% 30%, hsl(8 80% 48% / 0.05) 0%, transparent 60%)' }}
            />
            <div className="relative">
              <div className="w-12 h-12 rounded-md border border-ember/20 flex items-center justify-center mb-4">
                <Map className="text-primary" size={22} />
              </div>
              <h3 className="font-ritual text-2xl font-bold mb-3 tracking-wide">Roadmap</h3>
              <p className="text-muted-foreground text-sm mb-6">
                MVP → Ops comité → Musique → Map → Tickets. Une roadmap testée sur le terrain.
              </p>
              <Link to="/roadmap">
                <Button variant="ghost" className="group/btn text-primary hover:text-primary px-0">
                  Voir la roadmap
                  <ArrowRight size={16} className="ml-2 group-hover/btn:translate-x-1 transition-transform" />
                </Button>
              </Link>
            </div>
          </motion.div>

          {/* Pricing Teaser */}
          <motion.div
            className="group p-8 rounded-lg bg-card border border-border/30 hover:border-accent/20 transition-all duration-500 relative overflow-hidden"
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
          >
            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700"
              style={{ background: 'radial-gradient(circle at 70% 30%, hsl(40 70% 50% / 0.04) 0%, transparent 60%)' }}
            />
            <div className="relative">
              <div className="w-12 h-12 rounded-md border border-accent/15 flex items-center justify-center mb-4">
                <CreditCard className="text-accent/80" size={22} />
              </div>
              <h3 className="font-ritual text-2xl font-bold mb-3 tracking-wide">Pricing</h3>
              <p className="text-muted-foreground text-sm mb-6">
                Formule Free pour démarrer, Pro pour aller plus loin. Transparence totale.
              </p>
              <Link to="/pricing">
                <Button variant="ghost" className="group/btn text-accent hover:text-accent px-0">
                  Voir les tarifs
                  <ArrowRight size={16} className="ml-2 group-hover/btn:translate-x-1 transition-transform" />
                </Button>
              </Link>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
