import { ReactNode, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

type TransitionMode = "idle" | "to-forum" | "from-forum";

function isForumRoute(pathname: string) {
  return pathname === "/forum" || pathname.startsWith("/forum/") || pathname === "/compte";
}

export default function RouteTransition({ children }: { children: ReactNode }) {
  const location = useLocation();
  const previousPath = useRef(location.pathname);
  const [mode, setMode] = useState<TransitionMode>("idle");

  useEffect(() => {
    const wasForum = isForumRoute(previousPath.current);
    const isForum = isForumRoute(location.pathname);
    previousPath.current = location.pathname;

    if (wasForum === isForum) { setMode("idle"); return; }

    setMode(isForum ? "to-forum" : "from-forum");
    const timeout = window.setTimeout(() => setMode("idle"), 620);
    return () => window.clearTimeout(timeout);
  }, [location.pathname]);

  return <div className={`route-transition${mode === "idle" ? "" : ` route-transition--${mode}`}`}>{children}</div>;
}
