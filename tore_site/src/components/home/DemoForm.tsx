import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Send, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { motion } from "framer-motion";

const formSchema = z.object({
  name: z.string().min(2, "Nom requis"),
  email: z.string().email("Email invalide"),
  role: z.string().min(1, "Sélectionnez un profil"),
  faculty: z.string().min(2, "Faculté requise"),
  interest: z.string().min(1, "Sélectionnez un intérêt"),
});

type FormData = z.infer<typeof formSchema>;

export function DemoForm() {
  const [isSubmitted, setIsSubmitted] = useState(false);
  const { toast } = useToast();
  
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema),
  });

  useEffect(() => {
    // Prefill role/module from other CTAs
    const role = localStorage.getItem("tore_waitlist_role");
    const mod = localStorage.getItem("tore_waitlist_module");
    if (role) setValue("role", role);
    if (mod) setValue("interest", mod);
  }, [setValue]);

  const onSubmit = async (data: FormData) => {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    console.log("Demo request:", data);
    setIsSubmitted(true);
    toast({
      title: "Inscription envoyée !",
      description: "On te contacte dès qu'une soirée test est dispo.",
    });
  };

  if (isSubmitted) {
    return (
      <section id="waitlist" className="py-20 md:py-28 relative">
        <div className="absolute inset-0" style={{ background: 'radial-gradient(ellipse at 50% 50%, hsl(0 0% 100% / 0.03) 0%, transparent 55%)' }} />
        <div className="container relative z-10">
          <div className="max-w-lg mx-auto text-center">
            <div className="w-16 h-16 rounded-lg border border-accent/30 flex items-center justify-center mx-auto mb-6">
              <CheckCircle className="text-accent" size={32} />
            </div>
            <h2 className="text-3xl font-bold mb-4">T’es dans la liste ✅</h2>
            <p className="text-muted-foreground">
              On t'écrit dès qu'une bêta / soirée test ouvre à Liège.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section id="waitlist" className="py-20 md:py-28 relative border-t border-border/40">
      <div className="absolute inset-0" style={{ background: 'radial-gradient(ellipse at 50% 50%, hsl(0 0% 100% / 0.03) 0%, transparent 55%)' }} />
      
      <div className="container relative z-10">
        <motion.div 
          className="max-w-lg mx-auto"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <div className="text-center mb-10">
            <h2 className="text-3xl md:text-4xl font-bold mb-3">Rejoindre la bêta</h2>
            <p className="text-muted-foreground">Étudiant, comité, DJ ou staff : on te contacte pour les prochains tests.</p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name" className="text-sm text-muted-foreground">Nom / pseudo *</Label>
                <Input
                  id="name"
                  placeholder="Ex: Alex"
                  {...register("name")}
                  className={`bg-card border-border/50 focus:border-accent ${errors.name ? "border-destructive" : ""}`}
                />
                {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm text-muted-foreground">Email *</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="alex@email.com"
                  {...register("email")}
                  className={`bg-card border-border/50 focus:border-accent ${errors.email ? "border-destructive" : ""}`}
                />
                {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="role" className="text-sm text-muted-foreground">Tu es plutôt… *</Label>
                <Select onValueChange={(value) => setValue("role", value)}>
                  <SelectTrigger className={`bg-card border-border/50 ${errors.role ? "border-destructive" : ""}`}>
                    <SelectValue placeholder="Sélectionner" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="student">Étudiant</SelectItem>
                    <SelectItem value="committee">Comité / Cercle</SelectItem>
                    <SelectItem value="dj">DJ / Son</SelectItem>
                    <SelectItem value="staff">Staff / Bar</SelectItem>
                    <SelectItem value="other">Autre</SelectItem>
                  </SelectContent>
                </Select>
                {errors.role && <p className="text-xs text-destructive">{errors.role.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="faculty" className="text-sm text-muted-foreground">Faculté / école *</Label>
                <Input
                  id="faculty"
                  placeholder="Ex: HEC, ULiège, HELMo…"
                  {...register("faculty")}
                  className={`bg-card border-border/50 focus:border-accent ${errors.faculty ? "border-destructive" : ""}`}
                />
                {errors.faculty && <p className="text-xs text-destructive">{errors.faculty.message}</p>}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="interest" className="text-sm text-muted-foreground">Module que tu veux tester en premier *</Label>
              <Select onValueChange={(value) => setValue("interest", value)}>
                <SelectTrigger className={`bg-card border-border/50 ${errors.interest ? "border-destructive" : ""}`}>
                  <SelectValue placeholder="Sélectionner" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ops">Gestion soirée (entrée / staff / dashboard)</SelectItem>
                  <SelectItem value="music">Musique (préférences + votes simples)</SelectItem>
                  <SelectItem value="map">Map pour se retrouver</SelectItem>
                  <SelectItem value="bets">Rooms de prédiction (crédits internes)</SelectItem>
                  <SelectItem value="inventory">Inventaire pré/post soirée</SelectItem>
                </SelectContent>
              </Select>
              {errors.interest && <p className="text-xs text-destructive">{errors.interest.message}</p>}
            </div>

            <Button 
              type="submit" 
              size="lg" 
              className="w-full h-12 text-base font-semibold"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Envoi en cours..." : (
                <>
                  Rejoindre la bêta
                  <Send className="ml-2" size={18} />
                </>
              )}
            </Button>

            <p className="text-xs text-center text-muted-foreground">
              En envoyant, tu acceptes d’être contacté pour une bêta / soirée test.
            </p>
          </form>
        </motion.div>
      </div>
    </section>
  );
}
