/**
 * screens/LoginScreen.jsx — Autenticação do Memórias Vivas.
 * Design: mobile-first, campos XL acessíveis para idosos.
 * Painel esquerdo decorativo em md+ mantido.
 */

import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { authApi, TokenStorage } from "../api/client";

export default function LoginScreen() {
  const { login } = useAuth();
  const [modo, setModo]         = useState("login");
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [nome, setNome]         = useState("");
  const [erro, setErro]         = useState("");
  const [sucesso, setSucesso]   = useState("");
  const [loading, setLoading]   = useState(false);

  const limpar = () => { setErro(""); setSucesso(""); };

  const handleLogin = async (e) => {
    e.preventDefault(); limpar();
    if (!email || !password) { setErro("Por favor preencha o email e a password."); return; }
    setLoading(true);
    try { await login(email, password); }
    catch (err) { setErro(err.message || "Email ou password incorretos."); }
    finally { setLoading(false); }
  };

  const handleRegistar = async (e) => {
    e.preventDefault(); limpar();
    if (!email || !password || !nome) { setErro("Por favor preencha todos os campos."); return; }
    if (password.length < 8) { setErro("A password deve ter pelo menos 8 caracteres."); return; }
    setLoading(true);
    try {
      const data = await authApi.registar(email, password, nome);
      TokenStorage.save(data);
      window.location.reload();
    }
    catch (err) { setErro(err.message || "Erro ao criar conta."); }
    finally { setLoading(false); }
  };

  const handleRecuperar = async (e) => {
    e.preventDefault(); limpar();
    if (!email) { setErro("Por favor indique o seu email."); return; }
    setLoading(true);
    try {
      await authApi.recuperarPassword(email);
      setSucesso("Se o email existir, receberá instruções em breve.");
    } catch { setSucesso("Se o email existir, receberá instruções em breve."); }
    finally { setLoading(false); }
  };

  return (
    <>
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600;700&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />

      <div style={{ minHeight: "100dvh", display: "flex", fontFamily: "var(--font-serif)" }}>

        {/* ── Painel esquerdo — decorativo (só desktop) ── */}
        <div style={{
          display: "none",
          width: "42%",
          background: "var(--azul)",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "3.5rem",
        }} className="md-panel-left">
          <div>
            <div className="linha-dourada" style={{ width: "40px", marginBottom: "2.5rem" }} />
            <h1 style={{
              color: "white",
              fontFamily: "var(--font-display)",
              fontSize: "var(--text-5xl)",
              fontWeight: 300,
              lineHeight: 1.15,
              margin: 0,
            }}>
              Memórias<br /><span style={{ fontWeight: 600 }}>Vivas</span>
            </h1>
            <p style={{ color: "var(--azul-claro)", fontSize: "var(--text-lg)", marginTop: "1.5rem", lineHeight: 1.7 }}>
              Assistente conversacional<br />para Portfólios Sócio-Culturais.
            </p>
          </div>

          {/* Decoração geométrica */}
          <div style={{ position: "relative", height: "220px" }}>
            <div style={{ position: "absolute", bottom: 0, left: 0, width: "180px", height: "180px", border: "1px solid rgba(201,168,76,0.2)", borderRadius: "50%" }} />
            <div style={{ position: "absolute", bottom: "24px", left: "24px", width: "120px", height: "120px", border: "1px solid rgba(201,168,76,0.3)", borderRadius: "50%" }} />
            <div style={{ position: "absolute", bottom: "48px", left: "48px", width: "60px", height: "60px", background: "rgba(201,168,76,0.1)", borderRadius: "50%" }} />
            <p style={{ position: "absolute", bottom: 0, left: 0, color: "var(--azul-medio)", fontSize: "0.75rem", letterSpacing: "0.12em", textTransform: "uppercase", margin: 0 }}>
              Património Imaterial
            </p>
          </div>
        </div>

        {/* ── Formulário ── */}
        <div style={{
          flex: 1,
          background: "var(--creme)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem 1.5rem",
          minHeight: "100dvh",
        }}>
          <div style={{ width: "100%", maxWidth: "420px" }} className="animate-slide-up">

            {/* Logo mobile */}
            <div style={{ marginBottom: "3rem", textAlign: "center" }}>
              <div className="linha-dourada" style={{ width: "32px", margin: "0 auto 1.25rem" }} />
              <h1 style={{
                color: "var(--azul)",
                fontFamily: "var(--font-display)",
                fontSize: "var(--text-4xl)",
                fontWeight: 600,
                margin: 0,
                lineHeight: 1.1,
              }}>
                Memórias Vivas
              </h1>
              <p style={{ color: "var(--cinza)", fontSize: "var(--text-base)", marginTop: "0.5rem" }}>
                {modo === "login"     && "Bem-vindo de volta"}
                {modo === "registar"  && "Criar a sua conta"}
                {modo === "recuperar" && "Recuperar acesso"}
              </p>
            </div>

            {/* ── LOGIN ── */}
            {modo === "login" && (
              <form onSubmit={handleLogin} noValidate>
                <div style={{ marginBottom: "2rem" }}>
                  <label style={{ display: "block", color: "var(--cinza)", fontSize: "var(--text-xs)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "0.5rem" }}>
                    Email
                  </label>
                  <input
                    id="login-email"
                    type="email"
                    className="input-base"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="o.seu@email.pt"
                    autoComplete="email"
                    inputMode="email"
                  />
                </div>
                <div style={{ marginBottom: "2.5rem" }}>
                  <label style={{ display: "block", color: "var(--cinza)", fontSize: "var(--text-xs)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "0.5rem" }}>
                    Password
                  </label>
                  <input
                    id="login-password"
                    type="password"
                    className="input-base"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder="••••••••"
                    autoComplete="current-password"
                  />
                </div>

                {erro    && <MsgErro texto={erro} />}
                {sucesso && <MsgSucesso texto={sucesso} />}

                <button id="btn-entrar" type="submit" className="btn-primary" disabled={loading} style={{ marginBottom: "1.5rem" }}>
                  {loading ? <Spinner /> : "Entrar"}
                </button>

                <div style={{ display: "flex", flexDirection: "column", gap: "1rem", alignItems: "center" }}>
                  <button type="button" onClick={() => { setModo("recuperar"); limpar(); }}
                    style={{ background: "none", border: "none", color: "var(--cinza)", fontSize: "var(--text-base)", cursor: "pointer", padding: "0.5rem" }}>
                    Esqueceu a password?
                  </button>
                  <button type="button" onClick={() => { setModo("registar"); limpar(); }}
                    style={{ background: "none", border: "none", color: "var(--azul)", fontSize: "var(--text-lg)", fontWeight: 600, cursor: "pointer", padding: "0.5rem" }}>
                    Criar conta nova
                  </button>
                </div>
              </form>
            )}

            {/* ── REGISTAR ── */}
            {modo === "registar" && (
              <form onSubmit={handleRegistar} noValidate>
                <div style={{ marginBottom: "1.75rem" }}>
                  <label style={labelStyle}>Nome completo</label>
                  <input id="reg-nome" type="text" className="input-base" value={nome}
                    onChange={e => setNome(e.target.value)} placeholder="Manuel Silva" autoComplete="name" />
                </div>
                <div style={{ marginBottom: "1.75rem" }}>
                  <label style={labelStyle}>Email</label>
                  <input id="reg-email" type="email" className="input-base" value={email}
                    onChange={e => setEmail(e.target.value)} placeholder="o.seu@email.pt" autoComplete="email" inputMode="email" />
                </div>
                <div style={{ marginBottom: "2.5rem" }}>
                  <label style={labelStyle}>Password (mínimo 8 caracteres)</label>
                  <input id="reg-password" type="password" className="input-base" value={password}
                    onChange={e => setPassword(e.target.value)} placeholder="••••••••" autoComplete="new-password" />
                </div>

                {erro && <MsgErro texto={erro} />}

                <button id="btn-criar-conta" type="submit" className="btn-primary" disabled={loading} style={{ marginBottom: "1.5rem" }}>
                  {loading ? <Spinner /> : "Criar conta"}
                </button>
                <div style={{ textAlign: "center" }}>
                  <button type="button" onClick={() => { setModo("login"); limpar(); }}
                    style={{ background: "none", border: "none", color: "var(--cinza)", fontSize: "var(--text-base)", cursor: "pointer", padding: "0.5rem" }}>
                    Já tenho conta — Entrar
                  </button>
                </div>
              </form>
            )}

            {/* ── RECUPERAR ── */}
            {modo === "recuperar" && (
              <form onSubmit={handleRecuperar} noValidate>
                <p style={{ color: "var(--cinza)", fontSize: "var(--text-lg)", lineHeight: 1.6, marginBottom: "2rem" }}>
                  Indique o seu email e enviar-lhe-emos instruções para recuperar o acesso.
                </p>
                <div style={{ marginBottom: "2.5rem" }}>
                  <label style={labelStyle}>Email</label>
                  <input id="rec-email" type="email" className="input-base" value={email}
                    onChange={e => setEmail(e.target.value)} placeholder="o.seu@email.pt" autoComplete="email" inputMode="email" />
                </div>

                {erro    && <MsgErro texto={erro} />}
                {sucesso && <MsgSucesso texto={sucesso} />}

                <button id="btn-recuperar" type="submit" className="btn-primary" disabled={loading} style={{ marginBottom: "1.5rem" }}>
                  {loading ? <Spinner /> : "Enviar instruções"}
                </button>
                <div style={{ textAlign: "center" }}>
                  <button type="button" onClick={() => { setModo("login"); limpar(); }}
                    style={{ background: "none", border: "none", color: "var(--cinza)", fontSize: "var(--text-base)", cursor: "pointer", padding: "0.5rem" }}>
                    Voltar ao início de sessão
                  </button>
                </div>
              </form>
            )}

          </div>
        </div>
      </div>

      {/* Media query para o painel esquerdo */}
      <style>{`
        @media (min-width: 768px) {
          .md-panel-left { display: flex !important; }
        }
      `}</style>
    </>
  );
}

// ── Sub-componentes ─────────────────────────────────────────────────────────

const labelStyle = {
  display: "block",
  color: "var(--cinza)",
  fontSize: "var(--text-xs)",
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  marginBottom: "0.5rem",
};

const Spinner = () => (
  <span style={{
    width: "22px", height: "22px",
    border: "2.5px solid rgba(255,255,255,0.4)",
    borderTopColor: "white",
    borderRadius: "50%",
    display: "inline-block",
    animation: "spin 0.9s linear infinite",
  }} />
);

const MsgErro = ({ texto }) => (
  <div style={{
    background: "#fef2f2",
    border: "1px solid #fca5a5",
    borderRadius: "var(--radius-sm)",
    padding: "1rem 1.25rem",
    marginBottom: "1.5rem",
    color: "#b91c1c",
    fontSize: "var(--text-base)",
    lineHeight: 1.5,
  }} role="alert">
    {texto}
  </div>
);

const MsgSucesso = ({ texto }) => (
  <div style={{
    background: "#f0fdf4",
    border: "1px solid #86efac",
    borderRadius: "var(--radius-sm)",
    padding: "1rem 1.25rem",
    marginBottom: "1.5rem",
    color: "#15803d",
    fontSize: "var(--text-base)",
    lineHeight: 1.5,
  }} role="status">
    {texto}
  </div>
);