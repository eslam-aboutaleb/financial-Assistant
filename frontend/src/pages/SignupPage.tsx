import { Navigate, useNavigate } from "react-router-dom";
import AuthModal from "@/components/AuthModal";
import { useAuth } from "@/context/AuthContext";

export default function SignupPage() {
  const { userId, isLoaded } = useAuth();
  const navigate = useNavigate();

  if (!isLoaded) return null;
  if (userId) return <Navigate to="/chat" replace />;

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
