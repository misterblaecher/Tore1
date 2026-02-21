import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Send, CheckCircle, Calendar, MessageSquare, Clock, Wifi, CreditCard, ChevronDown } from "lucide-react";
import { Header, Footer, StickyCTA } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { useToast } from "@/hooks/use-toast";

const formSchema = z.object({
  firstName: z.string().min(2, "Prénom requis"),
  lastName: z.string().min(2, "Nom requis"),
  email: z.string().email("Email invalide"),
  phone: z.string().optional(),
  company: z.string().optional(),
  role: z.string().min(1, "Sélectionnez un rôle"),
  type: z.string().min(1, "Sélectionnez un type"),
  city: z.string().min(2, "Ville requise"),
  subject: z.string().min(1, "Sélectionnez un sujet"),
  message: z.string().min(10, "Message trop court (min. 10 caractères)"),
});

type FormData = z.infer<typeof formSchema>;

const faqs = [
  {
    question: "Comment fonctionne TORÈ en mode réseau faible ?",
    answer: "TORÈ utilise un cache intelligent et une synchronisation différée. Les scans QR fonctionnent hors-ligne, les données sont stockées localement et synchronisées dès que la connexion revient. Idéal pour les caves, sous-sols ou zones à faible couverture.",
  },
  {
    question: "Combien de temps pour mettre en place TORÈ ?",
    answer: "Setup < 10 minutes pour un bar (menu QR + zones). Pour un événement, comptez 2-3 minutes avec nos templates. Un onboarding guidé vous accompagne étape par étape.",
  },
  {
    question: "Quand les paiements seront-ils disponibles ?",
    answer: "Les modules de paiement (tickets, commandes) sont prévus pour la Phase 5 de notre roadmap. En attendant, TORÈ gère l'entrée, le comptage et le tracking sans monétisation directe.",
  },
  {
    question: "TORÈ est-il compatible avec mon système de caisse ?",
    answer: "TORÈ fonctionne en parallèle de votre caisse existante. Pas de remplacement, pas d'intégration complexe. Les exports CSV permettent de réconcilier les données si besoin.",
  },
  {
    question: "Mes données sont-elles sécurisées ?",
    answer: "Oui. QR signés cryptographiquement, ledger d'audit inviolable, chiffrement des données sensibles, et conformité RGPD native. Consultez notre page Trust pour les détails.",
  },
  {
    question: "Puis-je tester gratuitement ?",
    answer: "Absolument. Le plan Free inclut menu QR + tracking basique, sans limite de temps. Parfait pour découvrir TORÈ avant de passer Pro.",
  },
];

export default function Contact() {
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

  const onSubmit = async (data: FormData) => {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    console.log("Contact form:", data);
    setIsSubmitted(true);
    toast({
      title: "Message envoyé !",
      description: "Nous vous répondons sous 24h.",
    });
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="pt-24 pb-20 md:pb-10">
        {/* Hero */}
        <section className="py-16 md:py-20">
          <div className="container">
            <div className="max-w-3xl mx-auto text-center">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 text-primary text-sm font-medium mb-6">
                <MessageSquare size={16} />
                Parlons de votre projet
              </div>
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6">
                Contactez-nous
              </h1>
              <p className="text-lg md:text-xl text-muted-foreground">
                Une question ? Une demande de démo ? Notre équipe vous répond sous 24h.
              </p>
            </div>
          </div>
        </section>

        {/* Form + Calendly */}
        <section className="py-10">
          <div className="container">
            <div className="grid lg:grid-cols-5 gap-12 max-w-6xl mx-auto">
              {/* Form */}
              <div className="lg:col-span-3">
                {isSubmitted ? (
                  <div className="bg-card border border-border rounded-2xl p-8 text-center">
                    <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center mx-auto mb-6">
                      <CheckCircle className="text-primary" size={32} />
                    </div>
                    <h2 className="text-2xl font-bold mb-4">Message envoyé !</h2>
                    <p className="text-muted-foreground">
                      Merci pour votre message. Notre équipe vous contactera sous 24h pour discuter de votre projet.
                    </p>
                  </div>
                ) : (
                  <div className="bg-card border border-border rounded-2xl p-6 md:p-8">
                    <h2 className="text-2xl font-bold mb-6">Envoyez-nous un message</h2>
                    
                    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
                      {/* Name row */}
                      <div className="grid sm:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="firstName">Prénom *</Label>
                          <Input
                            id="firstName"
                            placeholder="Votre prénom"
                            {...register("firstName")}
                            className={errors.firstName ? "border-destructive" : ""}
                          />
                          {errors.firstName && (
                            <p className="text-xs text-destructive">{errors.firstName.message}</p>
                          )}
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="lastName">Nom *</Label>
                          <Input
                            id="lastName"
                            placeholder="Votre nom"
                            {...register("lastName")}
                            className={errors.lastName ? "border-destructive" : ""}
                          />
                          {errors.lastName && (
                            <p className="text-xs text-destructive">{errors.lastName.message}</p>
                          )}
                        </div>
                      </div>

                      {/* Contact row */}
                      <div className="grid sm:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="email">Email *</Label>
                          <Input
                            id="email"
                            type="email"
                            placeholder="votre@email.com"
                            {...register("email")}
                            className={errors.email ? "border-destructive" : ""}
                          />
                          {errors.email && (
                            <p className="text-xs text-destructive">{errors.email.message}</p>
                          )}
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="phone">Téléphone</Label>
                          <Input
                            id="phone"
                            type="tel"
                            placeholder="+33 6 00 00 00 00"
                            {...register("phone")}
                          />
                        </div>
                      </div>

                      {/* Company row */}
                      <div className="grid sm:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="company">Entreprise / Organisation</Label>
                          <Input
                            id="company"
                            placeholder="Nom de votre établissement"
                            {...register("company")}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="city">Ville *</Label>
                          <Input
                            id="city"
                            placeholder="Votre ville"
                            {...register("city")}
                            className={errors.city ? "border-destructive" : ""}
                          />
                          {errors.city && (
                            <p className="text-xs text-destructive">{errors.city.message}</p>
                          )}
                        </div>
                      </div>

                      {/* Role & Type row */}
                      <div className="grid sm:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="role">Votre rôle *</Label>
                          <Select onValueChange={(value) => setValue("role", value)}>
                            <SelectTrigger className={errors.role ? "border-destructive" : ""}>
                              <SelectValue placeholder="Sélectionner" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="owner">Propriétaire / Gérant</SelectItem>
                              <SelectItem value="manager">Manager</SelectItem>
                              <SelectItem value="committee">Président comité</SelectItem>
                              <SelectItem value="organizer">Organisateur event</SelectItem>
                              <SelectItem value="developer">Développeur / Tech</SelectItem>
                              <SelectItem value="other">Autre</SelectItem>
                            </SelectContent>
                          </Select>
                          {errors.role && (
                            <p className="text-xs text-destructive">{errors.role.message}</p>
                          )}
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="type">Type d'établissement *</Label>
                          <Select onValueChange={(value) => setValue("type", value)}>
                            <SelectTrigger className={errors.type ? "border-destructive" : ""}>
                              <SelectValue placeholder="Sélectionner" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="bar">Bar / Pub</SelectItem>
                              <SelectItem value="restaurant">Restaurant</SelectItem>
                              <SelectItem value="club">Club / Discothèque</SelectItem>
                              <SelectItem value="committee">Comité étudiant</SelectItem>
                              <SelectItem value="event">Organisateur d'events</SelectItem>
                              <SelectItem value="other">Autre</SelectItem>
                            </SelectContent>
                          </Select>
                          {errors.type && (
                            <p className="text-xs text-destructive">{errors.type.message}</p>
                          )}
                        </div>
                      </div>

                      {/* Subject */}
                      <div className="space-y-2">
                        <Label htmlFor="subject">Sujet *</Label>
                        <Select onValueChange={(value) => setValue("subject", value)}>
                          <SelectTrigger className={errors.subject ? "border-destructive" : ""}>
                            <SelectValue placeholder="Sélectionner un sujet" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="demo">Demande de démo</SelectItem>
                            <SelectItem value="pricing">Questions tarifs</SelectItem>
                            <SelectItem value="technical">Support technique</SelectItem>
                            <SelectItem value="partnership">Partenariat</SelectItem>
                            <SelectItem value="press">Presse / Médias</SelectItem>
                            <SelectItem value="other">Autre</SelectItem>
                          </SelectContent>
                        </Select>
                        {errors.subject && (
                          <p className="text-xs text-destructive">{errors.subject.message}</p>
                        )}
                      </div>

                      {/* Message */}
                      <div className="space-y-2">
                        <Label htmlFor="message">Message *</Label>
                        <Textarea
                          id="message"
                          placeholder="Décrivez votre projet, vos besoins..."
                          rows={5}
                          {...register("message")}
                          className={errors.message ? "border-destructive" : ""}
                        />
                        {errors.message && (
                          <p className="text-xs text-destructive">{errors.message.message}</p>
                        )}
                      </div>

                      <Button
                        type="submit"
                        size="lg"
                        className="w-full h-12 text-base font-semibold neon-glow-sm hover:neon-glow transition-shadow"
                        disabled={isSubmitting}
                      >
                        {isSubmitting ? (
                          "Envoi en cours..."
                        ) : (
                          <>
                            Envoyer le message
                            <Send className="ml-2" size={18} />
                          </>
                        )}
                      </Button>

                      <p className="text-xs text-center text-muted-foreground">
                        En soumettant ce formulaire, vous acceptez notre{" "}
                        <a href="/legal/privacy" className="text-primary hover:underline">
                          politique de confidentialité
                        </a>
                        .
                      </p>
                    </form>
                  </div>
                )}
              </div>

              {/* Calendly placeholder */}
              <div className="lg:col-span-2">
                <div className="bg-card border border-border rounded-2xl p-6 md:p-8 sticky top-24">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center">
                      <Calendar className="text-primary" size={24} />
                    </div>
                    <div>
                      <h3 className="font-bold">Réservez un créneau</h3>
                      <p className="text-sm text-muted-foreground">15 min de démo personnalisée</p>
                    </div>
                  </div>

                  {/* Placeholder for Calendly */}
                  <div className="aspect-square bg-muted/30 rounded-xl border-2 border-dashed border-border flex flex-col items-center justify-center text-center p-6">
                    <Clock className="text-muted-foreground mb-4" size={48} />
                    <p className="text-muted-foreground text-sm mb-4">
                      Calendrier de réservation bientôt disponible
                    </p>
                    <p className="text-xs text-muted-foreground">
                      En attendant, envoyez-nous un message et nous vous proposerons des créneaux.
                    </p>
                  </div>

                  <div className="mt-6 pt-6 border-t border-border">
                    <h4 className="font-semibold mb-3">Réponse rapide</h4>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                      <li className="flex items-center gap-2">
                        <CheckCircle size={14} className="text-primary" />
                        Réponse sous 24h
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle size={14} className="text-primary" />
                        Démo personnalisée gratuite
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle size={14} className="text-primary" />
                        Sans engagement
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="py-16 md:py-20">
          <div className="container">
            <div className="max-w-3xl mx-auto">
              <div className="text-center mb-12">
                <h2 className="text-3xl md:text-4xl font-bold mb-4">
                  Questions fréquentes
                </h2>
                <p className="text-muted-foreground">
                  Les réponses aux questions les plus courantes.
                </p>
              </div>

              <Accordion type="single" collapsible className="space-y-4">
                {faqs.map((faq, index) => (
                  <AccordionItem
                    key={index}
                    value={`faq-${index}`}
                    className="bg-card border border-border rounded-xl px-6 data-[state=open]:border-primary/50 transition-colors"
                  >
                    <AccordionTrigger className="text-left hover:no-underline py-5">
                      <span className="font-semibold pr-4">{faq.question}</span>
                    </AccordionTrigger>
                    <AccordionContent className="text-muted-foreground pb-5">
                      {faq.answer}
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
          </div>
        </section>
      </main>

      <Footer />
      <StickyCTA />
    </div>
  );
}
