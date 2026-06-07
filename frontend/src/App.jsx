/**
 * App.jsx — Roteador principal do Memórias Vivas.
 * Arquitectura: tab-based com BottomNav persistente após autenticação.
 * Tabs: inicio | conversa | portfolio | perfil
 */

import { useState } from "react";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import LoginScreen     from "./screens/LoginScreen";
import OnboardingScreen from "./screens/OnboardingScreen";
import DashboardScreen from "./screens/DashboardScreen";
import PortfolioScreen  from "./screens/PortfolioScreen";
import ProfileScreen    from "./screens/ProfileScreen";
import BottomNav        from "./components/BottomNav";

// ---------------------------------------------------------------------------
// Loading Screen
// ---------------------------------------------------------------------------
const LoadingScreen = () => (
  <div style={{
    minHeight: "100dvh",
    background: "var(--creme)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "1.5rem",
    fontFamily: "var(--font-display)",
  }}>
    <div className="linha-dourada" style={{ width: "40px" }} />
    <p style={{ color: "var(--azul)", fontSize: "var(--text-3xl)", fontWeight: 400, margin: 0 }}>
      Memórias Vivas
    </p>
    <div style={{
      width: "32px", height: "32px",
      border: "2.5px solid var(--azul)",
      borderTopColor: "transparent",
      borderRadius: "50%",
      animation: "spin 1s linear infinite",
      marginTop: "0.5rem",
    }} />
  </div>
);

// ---------------------------------------------------------------------------
// App interior (autenticado)
// ---------------------------------------------------------------------------
function AppAutenticado({ utilizador, logout }) {
  const [tabActiva, setTabActiva] = useState("inicio");
  const [conversaAtiva, setConversaAtiva] = useState(false);

  // Onboarding ainda não completo — fluxo dedicado sem bottom nav
  if (!utilizador.onboarding_completo) {
    return <OnboardingScreen />;
  }

  const renderTab = () => {
    switch (tabActiva) {
      case "inicio":
        return <DashboardScreen onConversaAtivaChange={setConversaAtiva} />;
      case "portfolio":
        return <PortfolioScreen />;
      case "perfil":
        return <ProfileScreen utilizadorInicial={utilizador} onLogout={logout} />;
      default:
        return null;
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100dvh" }}>
      {renderTab()}
      {!conversaAtiva && <BottomNav tabActiva={tabActiva} onChange={setTabActiva} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// App raiz
// ---------------------------------------------------------------------------
function AppInner() {
  const { utilizador, loading, logout } = useAuth();

  if (loading)     return <LoadingScreen />;
  if (!utilizador) return <LoginScreen />;

  return <AppAutenticado utilizador={utilizador} logout={logout} />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}