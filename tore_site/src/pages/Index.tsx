import { Header, Footer, StickyCTA } from "@/components/layout";
import {
  HeroSection,
  ValueCards,
  ForWhoSection,
  FeaturesSection,
  TrustSection,
  TeaserSection,
  DemoForm,
} from "@/components/home";

const Index = () => {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main>
        <HeroSection />
        <ValueCards />
        <ForWhoSection />
        <FeaturesSection />
        <TrustSection />
        <TeaserSection />
        <DemoForm />
      </main>

      <Footer />
      <StickyCTA />
    </div>
  );
};

export default Index;
