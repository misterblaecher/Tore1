import { Navigate } from "react-router-dom";

/** Backward-compatible entry point for old /studio links. */
export default function CommitteeStudioPage() {
  return <Navigate to="/forum/structures" replace />;
}
