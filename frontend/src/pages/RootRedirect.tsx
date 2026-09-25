import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function RootRedirect() {
  const { userId, isLoaded } = useAuth();

  if (!isLoaded) return null;
  return <Navigate to={userId ? "/chat" : "/login"} replace />;
}
