/**
 * screens/ProfileScreen.jsx — Perfil do utilizador.
 * Mobile-first: tap targets grandes, secções colapsáveis, logout claro.
 */

import { useState, useEffect } from "react";
import { TokenStorage, authApi } from "../api/client";

const BASE = import.meta.env.VITE_API_URL || window.location.origin;

// ── Ícones ──────────────────────────────────────────────────────────────────

const IconUser = () => (
  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
    <circle cx="12" cy="7" r="4"/>
  </svg>
);

const IconLock = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
  </svg>
);

const IconLogout = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
    <polyline points="16 17 21 12 16 7"/>
    <line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
);

const IconChevron = ({ open }) => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    style={{ transform: open ? "rotate(180deg)" : "rotate(0)", transition: "transform 0.25s" }}>
    <polyline points="6 9 12 15 18 9"/>
  </svg>
);

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatarValor(v) {
  if (v === null || v === undefined) return null;
  if (typeof v === "boolean") return v ? "Sim" : "Não";
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "object") {
    return Object.entries(v)
      .filter(([, val]) => val !== null && val !== undefined)
      .map(([k, val]) => `${k.replace(/_/g, " ")}: ${Array.isArray(val) ? val.join(", ") : val}`)
      .join(" · ");
  }
  return String(v);
}

// ── Sub-componentes ─────────────────────────────────────────────────────────

function LinhaBio({ label, valor }) {
  const texto = formatarValor(valor);
  if (!texto) return null;
  return (
    <div style={{ padding: "1rem 0", borderBottom: "1px solid var(--creme-escuro)" }}>
      <p style={{ color: "var(--cinza)", fontSize: "var(--text-xs)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "0.35rem" }}>
        {label}
      </p>
      <p style={{ color: "var(--texto)", fontSize: "var(--text-xl)", lineHeight: 1.5, margin: 0, fontFamily: "var(--font-serif)" }}>
        {texto}
      </p>
    </div>
  );
}

function Seccao({ titulo, defaultOpen = false, children }) {
  const [aberta, setAberta] = useState(defaultOpen);
  return (
    <div style={{
      background: "white",
      border: "1.5px solid #e8e0d5",
      borderRadius: "var(--radius-md)",
      marginBottom: "0.875rem",
      overflow: "hidden",
    }}>
      <button
        onClick={() => setAberta(!aberta)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "1.25rem 1.5rem",
          background: "none",
          border: "none",
          cursor: "pointer",
          minHeight: "var(--tap-lg)",
        }}
      >
        <span style={{ color: "var(--azul)", fontFamily: "var(--font-display)", fontSize: "var(--text-xl)", fontWeight: 600 }}>
          {titulo}
        </span>
        <IconChevron open={aberta} />
      </button>
      {aberta && (
        <div style={{ padding: "0 1.5rem 1.5rem", borderTop: "1px solid var(--creme-escuro)" }}>
          {children}
        </div>
      )}
    </div>
  );
}

function SpinnerAzul() {
  return (
    <div style={{
      width: "32px", height: "32px",
      border: "2.5px solid var(--azul)",
      borderTopColor: "transparent",
      borderRadius: "50%",
      animation: "spin 1s linear infinite",
    }} />
  );
}

// ── Ecrã principal ───────────────────────────────────────────────────────────

export default function ProfileScreen({ utilizadorInicial, onLogout }) {
  const [utilizador, setUtilizador] = useState(utilizadorInicial || null);
  const [perfil,     setPerfil]     = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [erro,       setErro]       = useState("");

  const [pwAtual,   setPwAtual]   = useState("");
  const [pwNova,    setPwNova]    = useState("");
  const [pwErro,    setPwErro]    = useState("");
  const [pwSucesso, setPwSucesso] = useState("");
  const [pwLoading, setPwLoading] = useState(false);

  useEffect(() => {
    const carregar = async () => {
      setLoading(true);
      try {
        if (!utilizadorInicial) {
          const user = await authApi.me();
          setUtilizador(user);
        }
        const res = await fetch(
          `${BASE}/api/v1/auth/perfil`,
          { headers: { Authorization: `Bearer ${TokenStorage.getAccess()}` } }
        );
        if (res.ok) setPerfil(await res.json());
      } catch { setErro("Não foi possível carregar o perfil."); }
      finally { setLoading(false); }
    };
    carregar();
  }, []);

  const handleAlterarPassword = async (e) => {
    e.preventDefault();
    setPwErro(""); setPwSucesso("");
    if (!pwAtual || !pwNova) { setPwErro("Por favor preencha os dois campos."); return; }
    if (pwNova.length < 8)   { setPwErro("A nova password deve ter pelo menos 8 caracteres."); return; }
    setPwLoading(true);
    try {
      await authApi.alterarPassword(pwAtual, pwNova);
      setPwSucesso("Password alterada com sucesso.");
      setPwAtual(""); setPwNova("");
    } catch (err) { setPwErro(err.message || "Erro ao alterar password."); }
    finally { setPwLoading(false); }
  };

  if (loading) return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <SpinnerAzul />
    </div>
  );

  const bio   = perfil?.perfil_json || {};
  const temas = perfil?.temas_explorados || [];

  const TEMAS_LABELS = {
    memorias: "Memórias", familia: "Família", saude: "Bem-estar",
    entretenimento: "Entretenimento", exercicio: "Exercício", geral: "Conversa livre",
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "var(--creme)" }}>
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />

      {/* Header */}
      <header className="app-header">
        <div>
          <span style={{ color: "var(--azul)", fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 600 }}>
            O meu Perfil
          </span>
          <div className="linha-dourada" style={{ width: "32px", marginTop: "2px" }} />
        </div>
      </header>

      {/* Conteúdo */}
      <main style={{ flex: 1, paddingTop: "1.5rem", paddingLeft: "1.25rem", paddingRight: "1.25rem", overflowY: "auto" }} className="pb-nav">

        {/* Avatar + nome */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "1rem",
          marginBottom: "1.75rem",
          padding: "1.25rem 1.5rem",
          background: "white",
          borderRadius: "var(--radius-md)",
          border: "1.5px solid #e8e0d5",
          boxShadow: "var(--shadow-sm)",
        }} className="animate-slide-down">
          <div style={{
            width: "64px", height: "64px",
            borderRadius: "50%",
            background: "var(--azul)",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "white", flexShrink: 0,
          }}>
            <IconUser />
          </div>
          <div>
            <h2 style={{
              color: "var(--azul)",
              fontFamily: "var(--font-display)",
              fontSize: "var(--text-2xl)",
              fontWeight: 500,
              margin: "0 0 0.2rem",
            }}>
              {utilizador?.nome || "Utilizador"}
            </h2>
            <p style={{ color: "var(--cinza)", fontSize: "var(--text-base)", margin: 0 }}>
              {utilizador?.email}
            </p>
          </div>
        </div>

        {erro && (
          <div style={{
            background: "#fef2f2", border: "1px solid #fca5a5",
            borderRadius: "var(--radius-sm)", padding: "1rem 1.25rem",
            marginBottom: "1.25rem", color: "#b91c1c", fontSize: "var(--text-base)",
          }} role="alert">
            {erro}
          </div>
        )}

        {/* Perfil Biográfico */}
        <Seccao titulo="Perfil Biográfico" defaultOpen={true}>
          {Object.keys(bio).length === 0 ? (
            <p style={{ color: "var(--cinza)", fontSize: "var(--text-lg)", paddingTop: "1rem", lineHeight: 1.6 }}>
              O seu perfil biográfico ainda não foi criado. Complete o onboarding para o preencher.
            </p>
          ) : (
            <div>
              <LinhaBio label="Nome"             valor={bio.nome} />
              <LinhaBio label="Terra natal"      valor={bio.terra_natal} />
              <LinhaBio label="Família"          valor={bio.familia} />
              <LinhaBio label="Profissão"        valor={bio.profissao} />
              <LinhaBio label="Memória marcante" valor={bio.memoria_marcante} />
              {bio.outros && Object.entries(bio.outros).map(([k, v]) =>
                v !== null && v !== undefined
                  ? <LinhaBio key={k} label={k.replace(/_/g, " ")} valor={v} />
                  : null
              )}
            </div>
          )}
        </Seccao>

        {/* Temas Explorados */}
        <Seccao titulo="Temas Explorados">
          {temas.length === 0 ? (
            <p style={{ color: "var(--cinza)", fontSize: "var(--text-lg)", paddingTop: "1rem" }}>
              Ainda não explorou nenhum tema.
            </p>
          ) : (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.625rem", paddingTop: "1rem" }}>
              {temas.map(t => (
                <span key={t} style={{
                  padding: "0.5rem 1rem",
                  background: "var(--creme)",
                  border: "1.5px solid var(--dourado-suave)",
                  borderRadius: "var(--radius-full)",
                  color: "var(--azul)",
                  fontSize: "var(--text-base)",
                  fontWeight: 500,
                }}>
                  {TEMAS_LABELS[t] || t}
                </span>
              ))}
            </div>
          )}
        </Seccao>

        {/* Segurança */}
        <Seccao titulo="Segurança">
          <form onSubmit={handleAlterarPassword} noValidate style={{ paddingTop: "1rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.5rem", color: "var(--cinza)" }}>
              <IconLock />
              <span style={{ fontSize: "var(--text-base)", letterSpacing: "0.03em" }}>Alterar password</span>
            </div>

            <div style={{ marginBottom: "1.5rem" }}>
              <label style={{ display: "block", color: "var(--cinza)", fontSize: "var(--text-xs)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "0.4rem" }}>
                Password atual
              </label>
              <input id="pw-atual" type="password" className="input-base" value={pwAtual}
                onChange={e => setPwAtual(e.target.value)} placeholder="••••••••" />
            </div>
            <div style={{ marginBottom: "2rem" }}>
              <label style={{ display: "block", color: "var(--cinza)", fontSize: "var(--text-xs)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "0.4rem" }}>
                Nova password (mínimo 8 caracteres)
              </label>
              <input id="pw-nova" type="password" className="input-base" value={pwNova}
                onChange={e => setPwNova(e.target.value)} placeholder="••••••••" />
            </div>

            {pwErro   && (
              <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: "var(--radius-sm)", padding: "0.875rem 1rem", marginBottom: "1rem", color: "#b91c1c", fontSize: "var(--text-base)" }} role="alert">
                {pwErro}
              </div>
            )}
            {pwSucesso && (
              <div style={{ background: "#f0fdf4", border: "1px solid #86efac", borderRadius: "var(--radius-sm)", padding: "0.875rem 1rem", marginBottom: "1rem", color: "#15803d", fontSize: "var(--text-base)" }} role="status">
                {pwSucesso}
              </div>
            )}

            <button id="btn-alterar-pw" type="submit" className="btn-primary" disabled={pwLoading}>
              {pwLoading
                ? <span style={{ display: "inline-block", width: "22px", height: "22px", border: "2.5px solid rgba(255,255,255,0.4)", borderTopColor: "white", borderRadius: "50%", animation: "spin 0.9s linear infinite" }} />
                : "Alterar password"
              }
            </button>
          </form>
        </Seccao>

        {/* Terminar sessão */}
        <button
          id="btn-terminar-sessao"
          onClick={onLogout}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.75rem",
            minHeight: "var(--tap-lg)",
            background: "white",
            border: "2px solid #e8e0d5",
            borderRadius: "var(--radius-md)",
            color: "var(--cinza)",
            fontSize: "var(--text-lg)",
            fontFamily: "var(--font-serif)",
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.2s",
            marginBottom: "1rem",
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--erro)"; e.currentTarget.style.color = "var(--erro)"; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = "#e8e0d5"; e.currentTarget.style.color = "var(--cinza)"; }}
        >
          <IconLogout />
          Terminar sessão
        </button>

      </main>
    </div>
  );
}