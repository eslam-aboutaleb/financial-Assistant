import { Navigate, useNavigate } from "react-router-dom";
import AuthModal from "@/components/AuthModal";
import { useAuth } from "@/context/AuthContext";

export default function SignupPage() {
  const { status } = useAuth();
  const navigate = useNavigate();

  if (status === "loading") return null;
  if (status === "authenticated") return <Navigate to="/chat" replace />;

  return (
    <AuthModal
      isLogin={false}
      onAuthenticated={() => {
        navigate("/login", { replace: true });
      }}
      onToggleMode={() => navigate("/login")}
    />
  );
}
