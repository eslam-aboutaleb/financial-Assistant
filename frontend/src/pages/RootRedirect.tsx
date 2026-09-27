import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function RootRedirect() {
  const { status } = useAuth();

  if (status === "loading") return null;
  return (
    <Navigate to={status === "authenticated" ? "/chat" : "/login"} replace />
  );
}
