import { useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Routes, Route, useLocation } from "react-router-dom";
import Index from "./pages/Index";
import JoinPage from "./pages/Join";

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
import ForumHome from "./pages/ForumHome";
import ForumPublicPage from "./pages/ForumPublic";
import ForumStructurePage from "./pages/ForumStructure";
import ChannelAclPage from "./pages/ChannelAclPage";
import CommitteeStudioPage from "./pages/CommitteeStudio";
import LoginPage from "./pages/Login";
import AuthCallbackPage from "./pages/AuthCallback";
import ProtectedRoute from "./components/ProtectedRoute";
import RouteTransition from "./components/RouteTransition";
import ForumLayout from "./components/layout/ForumLayout";


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
      const timeout = window.setTimeout(() => {
        document.getElementById(id)?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      }, 50);
      return () => window.clearTimeout(timeout);
    }
    window.scrollTo({ top: 0, behavior: "instant" });
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
        <RouteTransition>
          <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/produit" element={<Produit />} />
          <Route path="/rejoindre" element={<JoinPage />} />
          <Route path="/bars" element={<Navigate to="/rejoindre#account" replace />} />
          <Route path="/comites" element={<Comites />} />
          <Route path="/roadmap" element={<Roadmap />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/trust" element={<Trust />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route path="/profile" element={<Navigate to="/compte" replace />} />
          <Route element={<ForumLayout />}>
            <Route path="/compte" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
            <Route path="/forum/login" element={<LoginPage context="forum" />} />
            <Route path="/forum/public" element={<Navigate to="/forum" replace />} />
            <Route path="/forum" element={<ForumHome />} />
            <Route path="/forum/structures" element={<ForumPage />} />
            <Route path="/forum/structures/:slug" element={<ForumPublicPage />} />
            <Route path="/forum/structures/:slug/channel-acl" element={<ProtectedRoute><ChannelAclPage /></ProtectedRoute>} />
            <Route path="/forum/structures/:slug/:section" element={<ProtectedRoute><ForumStructurePage /></ProtectedRoute>} />
          </Route>
          <Route path="/studio" element={<CommitteeStudioPage />} />
          <Route path="/legal/privacy" element={<Privacy />} />
          <Route path="/legal/terms" element={<Terms />} />
          <Route path="/legal/cookies" element={<Cookies />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </RouteTransition>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;