import { ReactNode, useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { getToken } from '@/lib/auth';
import { getMe } from '@/lib/session';

type ProtectedRouteProps = {
  children: ReactNode;
};

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const location = useLocation();
  const [isChecking, setIsChecking] = useState(true);
  const [isAllowed, setIsAllowed] = useState(false);

  useEffect(() => {
    let active = true;
    const token = getToken();
    if (!token) {
      setIsAllowed(false);
      setIsChecking(false);
      return;
    }

    void getMe()
      .then(() => {
        if (!active) return;
        setIsAllowed(true);
      })
      .catch(() => {
        if (!active) return;
        setIsAllowed(false);
      })
      .finally(() => {
        if (!active) return;
        setIsChecking(false);
      });

    return () => {
      active = false;
    };
  }, []);

  if (isChecking) {
    return <main style={{ padding: 24 }}>Vérification de session…</main>;
  }

  if (!isAllowed) {
    const loginPath = location.pathname.startsWith('/forum') || location.pathname === '/compte' ? '/forum/login' : '/login';
    return <Navigate to={loginPath} replace state={{ from: location.pathname + location.search + location.hash }} />;
  }

  return <>{children}</>;
}
