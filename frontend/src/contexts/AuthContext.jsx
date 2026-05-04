/**
 * contexts/AuthContext.jsx — Estado global de autenticação.
 *
 * Fornece: utilizador, loading, login(), logout(), isAuthenticated
 * Usado em App.jsx para controlar qual ecrã mostrar.
 */

import { createContext, useContext, useEffect, useState } from "react";
import { authApi, TokenStorage } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [utilizador, setUtilizador]   = useState(null);
  const [loading, setLoading]         = useState(true);

  // Verificar sessão existente no arranque
  useEffect(() => {
    const token = TokenStorage.getAccess();
    if (!token) { setLoading(false); return; }

    authApi.me()
      .then(setUtilizador)
      .catch(() => TokenStorage.clear())
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const data = await authApi.login(email, password);
    TokenStorage.save(data);
    const user = await authApi.me();
    setUtilizador(user);
    return user;
  };

  const logout = () => {
    TokenStorage.clear();
    setUtilizador(null);
  };

  return (
    <AuthContext.Provider value={{
      utilizador,
      loading,
      login,
      logout,
      isAuthenticated: !!utilizador,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth deve ser usado dentro de AuthProvider");
  return ctx;
}