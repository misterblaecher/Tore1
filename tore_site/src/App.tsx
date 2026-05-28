import { useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Routes, Route, useLocation } from "react-router-dom";
import Index from "./pages/Index";

// Implemented pages
import Produit from "./pages/Produit";
import Comites from "./pages/Comites";
import Roadmap from "./pages/Roadmap";
import Pricing from "./pages/Pricing";
import Trust from "./pages/Trust";
import Contact from "./pages/Contact";
import Privacy from "./pages/legal/Privacy";
import Terms from "./pages/legal/Terms";
import Cookies from "./pages/legal/Cookies";
import ProfilePage from "./pages/Profile";
import ForumPage from "./pages/Forum";
import ForumPublicPage from "./pages/ForumPublic";
import CommitteeStudioPage from "./pages/CommitteeStudio";
import LoginPage from "./pages/Login";
import AuthCallbackPage from "./pages/AuthCallback";
import ProtectedRoute from "./components/ProtectedRoute";


const queryClient = new QueryClient();

function ScrollToHash() {
  const { hash, pathname } = useLocation();

  // Scroll to top on route change (without hash)
  // Scroll to element when hash is present
  // This makes in-page anchors work with react-router.
  useEffect(() => {
    if (hash) {
      const id = hash.replace("#", "");
      // small timeout to allow page render
      setTimeout(() => {
        document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
      }, 50);
      return;
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [hash, pathname]);

  return null;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <ScrollToHash />
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/produit" element={<Produit />} />
          <Route path="/bars" element={<Navigate to="/#account" replace />} />
          <Route path="/comites" element={<Comites />} />
          <Route path="/roadmap" element={<Roadmap />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/trust" element={<Trust />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
          <Route path="/forum/public" element={<ForumPublicPage />} />
          <Route path="/forum" element={<ProtectedRoute><ForumPage /></ProtectedRoute>} />
          <Route path="/studio" element={<ProtectedRoute><CommitteeStudioPage /></ProtectedRoute>} />
          <Route path="/legal/privacy" element={<Privacy />} />
          <Route path="/legal/terms" element={<Terms />} />
          <Route path="/legal/cookies" element={<Cookies />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
