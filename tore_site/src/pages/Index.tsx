import { Header, Footer, StickyCTA } from "@/components/layout";
import {
  HeroSection,
  FeaturesSection,
  TeaserSection,
  DemoForm,
} from "@/components/home";

const Index = () => {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main>
        <HeroSection />
        <FeaturesSection />
        <TeaserSection />
        <DemoForm />
      </main>

      <Footer />
      <StickyCTA />
    </div>
  );
};

export default Index;
