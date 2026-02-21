import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

interface StickyCTAProps {
  text?: string;
  href?: string;
}

export function StickyCTA({ text = "Rejoindre la bêta", href = "/contact" }: StickyCTAProps) {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 md:hidden bg-background/90 backdrop-blur-lg border-t border-border/30 p-4">
      <Link to={href} className="block">
        <Button className="w-full h-12 text-base font-semibold font-ritual tracking-wider bg-transparent border border-accent text-accent hover:bg-accent hover:text-accent-foreground glow-gold-sm transition-all duration-300">
          {text}
        </Button>
      </Link>
    </div>
  );
}
