import { Navigate, useNavigate } from "react-router-dom";
import AuthModal from "@/components/AuthModal";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const { userId, isLoaded, login } = useAuth();
  const navigate = useNavigate();

  if (!isLoaded) return null;
  if (userId) return <Navigate to="/chat" replace />;

  return (
    <AuthModal
      isLogin
      onAuthenticated={(token, userId) => {
        login(token, userId);
        navigate("/chat", { replace: true });
      }}
      onToggleMode={() => navigate("/signup")}
    />
  );
}
