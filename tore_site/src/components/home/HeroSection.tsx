import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import appIcon from "@/assets/app-icon.png";

function EmberParticles() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {Array.from({ length: 20 }).map((_, i) => (
        <div
          key={i}
          className="absolute w-1 h-1 rounded-full bg-ember-glow"
          style={{
            left: `${10 + Math.random() * 80}%`,
            bottom: `${Math.random() * 30}%`,
            opacity: 0,
            animation: `particleDrift ${4 + Math.random() * 6}s ease-out infinite`,
            animationDelay: `${Math.random() * 5}s`,
          }}
        />
      ))}
    </div>
  );
}

export function HeroSection() {
  return (
    <section className="relative min-h-screen flex items-center justify-center pt-20 pb-32 overflow-hidden texture-grain">
      {/* Deep red radial background */}
      <div className="absolute inset-0 bg-background" />
      <div className="absolute inset-0 gradient-hero-ritual" />
      
      {/* Circular ember halo behind logo */}
      <div className="absolute left-1/2 top-[40%] -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] md:w-[700px] md:h-[700px]">
        <div className="absolute inset-0 rounded-full bg-gradient-radial from-ember/20 via-ember-deep/10 to-transparent animate-ember-breathe" 
          style={{ background: 'radial-gradient(circle, hsl(8 80% 48% / 0.2) 0%, hsl(0 60% 18% / 0.08) 50%, transparent 70%)' }}
        />
      </div>

      {/* Ember particles */}
      <EmberParticles />

      <div className="container relative z-10 text-center">
        {/* Logo doré massif */}
        <motion.div 
          className="flex justify-center mb-6"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="relative">
            <img 
              src={appIcon} 
              alt="TORÈ" 
              className="w-28 h-28 md:w-40 md:h-40 rounded-3xl animate-float-slow object-contain"
            />
            <div className="absolute -inset-6 rounded-3xl animate-glow-pulse" 
              style={{ boxShadow: '0 0 40px hsl(40 70% 50% / 0.2), 0 0 80px hsl(8 80% 48% / 0.15)' }}
            />
          </div>
        </motion.div>

        {/* Title — serif épique doré */}
        <motion.h1 
          className="font-ritual text-5xl md:text-7xl lg:text-8xl font-bold mb-6 leading-tight tracking-wide"
          initial={{ opacity: 0, y: 20, filter: 'blur(10px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ duration: 0.8, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
        >
          <span className="text-gradient-gold text-gold-glow">TORÈ</span>
        </motion.h1>

        {/* Tagline */}
        <motion.p 
          className="font-ritual text-lg md:text-2xl text-foreground/80 tracking-widest uppercase mb-4"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.6 }}
        >
          L'app des soirées étudiantes
        </motion.p>

        {/* Séparateur doré */}
        <motion.div 
          className="w-24 h-[2px] mx-auto mb-8 gradient-gold rounded-full"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.8, delay: 0.8 }}
        />

        {/* Subtitle */}
        <motion.p 
          className="text-base md:text-lg text-muted-foreground max-w-xl mx-auto mb-10 leading-relaxed"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.9 }}
        >
          Découvre les events, rejoins ta soirée et aide ton comité à gérer le terrain.
          <br className="hidden md:block" />
          <span className="text-foreground font-medium">Scanner rapide. Dashboard live. Modules fun.</span>
        </motion.p>

        {/* CTAs */}
        <motion.div 
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 1.1 }}
        >
          <Link to="/contact">
            <Button size="lg" className="h-14 px-8 text-lg font-semibold font-ritual tracking-wide bg-transparent border-2 border-accent text-accent hover:bg-accent hover:text-accent-foreground glow-gold-sm hover:glow-gold transition-all duration-500">
              Rejoindre la bêta
            </Button>
          </Link>
          <Link to="/produit">
            <Button size="lg" variant="ghost" className="h-14 px-8 text-lg font-medium text-muted-foreground hover:text-foreground transition-all duration-300">
              Voir les modules →
            </Button>
          </Link>
        </motion.div>

        {/* Stats rituels */}
        <motion.div 
          className="grid grid-cols-3 gap-4 md:gap-8 max-w-xl mx-auto mt-20"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 1.4 }}
        >
          {[
            { value: "<1s", label: "Scan → action" },
            { value: "Offline", label: "Réseau faible" },
            { value: "All‑in", label: "Pensé terrain" },
          ].map((stat) => (
            <div key={stat.label} className="text-center group">
              <p className="text-2xl md:text-3xl font-bold text-accent font-ritual group-hover:text-gold-glow transition-all duration-300">
                {stat.value}
              </p>
              <p className="text-xs md:text-sm text-muted-foreground mt-1">{stat.label}</p>
            </div>
          ))}
        </motion.div>
      </div>

      {/* Bottom gradient */}
      <div className="absolute bottom-0 left-0 right-0 h-40 bg-gradient-to-t from-background to-transparent" />
    </section>
  );
}
