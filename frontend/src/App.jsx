import { AuthProvider, useAuth } from "./contexts/AuthContext";
import LoginScreen      from "./screens/LoginScreen";
import OnboardingScreen from "./screens/OnboardingScreen";
import DashboardScreen  from "./screens/DashboardScreen";

const LoadingScreen = () => (
  <div className="min-h-screen bg-[#FAF7F2] flex flex-col items-center justify-center gap-4">
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500&display=swap" rel="stylesheet" />
    <div className="w-10 h-[2px] bg-[#c9a84c] mb-4" />
    <p className="text-[#1e3a5f] text-2xl"
      style={{ fontFamily: "'Cormorant Garamond', serif", fontWeight: 400 }}>
      Memórias Vivas
    </p>
    <div className="w-8 h-8 border-2 border-[#1e3a5f] border-t-transparent rounded-full animate-spin mt-4" />
  </div>
);

function AppInner() {
  const { utilizador, loading } = useAuth();

  if (loading)                         return <LoadingScreen />;
  if (!utilizador)                     return <LoginScreen />;
  if (!utilizador.onboarding_completo) return <OnboardingScreen />;

  return <DashboardScreen />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}