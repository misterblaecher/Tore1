import { ReactNode, useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { getToken } from '@/lib/auth';
import { ApiError } from '@/lib/api';
import { getMe } from '@/lib/session';

type ProtectedRouteProps = {
  children: ReactNode;
};

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const location = useLocation();
  const [isChecking, setIsChecking] = useState(true);
  const [isAllowed, setIsAllowed] = useState(false);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    setIsChecking(true);
    setError(false);
    void getMe()
      .then(() => {
        if (!active) return;
        setIsAllowed(true);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setIsAllowed(false);
        setError(!(reason instanceof ApiError && reason.status === 401));
      })
      .finally(() => {
        if (!active) return;
        setIsChecking(false);
      });

    return () => {
      active = false;
    };
  }, [revision]);

  if (isChecking) {
    return <main style={{ padding: 24 }}>Vérification de session…</main>;
  }

  if (!isAllowed) {
    if (error) return <main className="forum-main"><p className="forum-alert" role="alert">Impossible de vérifier votre session. Vérifiez votre connexion puis réessayez.</p><button className="forum-button forum-button--primary" onClick={() => setRevision(value => value + 1)}>Réessayer</button></main>;
    const loginPath = location.pathname.startsWith('/forum') || location.pathname === '/compte' ? '/forum/login' : '/login';
    return <Navigate to={loginPath} replace state={{ from: location.pathname + location.search + location.hash }} />;
  }

  return <>{children}</>;
}
