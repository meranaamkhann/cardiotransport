import { Navigate, Outlet, useLocation } from "react-router-dom";
import type { Role } from "../api/types";
import { Spinner } from "../components/ui";
import { homeFor, useAuth } from "./AuthContext";

export default function RequireRole({ roles }: { roles: Role[] }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner label="Checking your session" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}
