import { Button } from "@/components/ui/button";

interface StickyCTAProps {
  text?: string;
}

export function StickyCTA({ text = "Rejoindre la bêta" }: StickyCTAProps) {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 md:hidden bg-background/90 backdrop-blur-lg border-t border-border/30 p-4">
      <Button
        className="w-full h-12 text-base font-semibold"
        onClick={() => document.getElementById("waitlist")?.scrollIntoView({ behavior: "smooth" })}
      >
        {text}
      </Button>
    </div>
  );
}
