/**
 * screens/ProfileScreen.jsx — Perfil do utilizador e definições.
 *
 * Secções:
 *  - Dados biográficos extraídos pelo Gemini/Groq (perfil_json)
 *  - Temas explorados
 *  - Alterar password
 *  - Sair da conta
 */

import { useState, useEffect } from "react";
import { TokenStorage, authApi } from "../api/client";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Ícones SVG
// ---------------------------------------------------------------------------

const IconArrowLeft = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M19 12H5M12 5l-7 7 7 7"/>
  </svg>
);

const IconUser = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
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
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
    <polyline points="16 17 21 12 16 7"/>
    <line x1="21" y1="12" x2="9" y2="12"/>
  </svg>
);

const IconChevron = ({ open }) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }}>
    <polyline points="6 9 12 15 18 9"/>
  </svg>
);

// ---------------------------------------------------------------------------
// Componente — Linha de perfil
// ---------------------------------------------------------------------------

function LinhaPerfilBio({ label, valor }) {
  if (!valor) return null;
  return (
    <div className="py-5 border-b border-[#f0ebe3] last:border-0">
      <p className="text-[#aaa] text-sm tracking-widest uppercase mb-1">{label}</p>
      <p className="text-[#1a1a2e] text-xl leading-relaxed">{valor}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Componente — Secção colapsável
// ---------------------------------------------------------------------------

function Seccao({ titulo, children, defaultOpen = false }) {
  const [aberta, setAberta] = useState(defaultOpen);
  return (
    <div className="bg-white border border-[#e8e0d5] mb-4">
      <button
        onClick={() => setAberta(!aberta)}
        className="w-full flex items-center justify-between px-7 py-5 text-left hover:bg-[#faf7f2] transition-colors"
      >
        <span className="text-[#1e3a5f] text-xl font-semibold"
          style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "1.3rem" }}>
          {titulo}
        </span>
        <IconChevron open={aberta} />
      </button>
      {aberta && (
        <div className="px-7 pb-6 border-t border-[#f0ebe3]">
          {children}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ecrã principal
// ---------------------------------------------------------------------------

export default function ProfileScreen({ onVoltar, onLogout }) {
  const [utilizador, setUtilizador] = useState(null);
  const [perfil, setPerfil]         = useState(null);
  const [loading, setLoading]       = useState(true);
  const [erro, setErro]             = useState("");

  // Alterar password
  const [pwAtual,  setPwAtual]  = useState("");
  const [pwNova,   setPwNova]   = useState("");
  const [pwErro,   setPwErro]   = useState("");
  const [pwSucesso, setPwSucesso] = useState("");
  const [pwLoading, setPwLoading] = useState(false);

  // ---------------------------------------------------------------------------
  // Carregar dados
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const carregar = async () => {
      setLoading(true);
      try {
        // Dados do utilizador
        const user = await authApi.me();
        setUtilizador(user);

        // Perfil biográfico
        const res = await fetch(
          `${BASE}/api/v1/auth/perfil`,
          { headers: { Authorization: `Bearer ${TokenStorage.getAccess()}` } }
        );
        if (res.ok) {
          const data = await res.json();
          setPerfil(data);
        }
      } catch (err) {
        setErro("Não foi possível carregar o perfil.");
      } finally {
        setLoading(false);
      }
    };
    carregar();
  }, []);

  // ---------------------------------------------------------------------------
  // Alterar password
  // ---------------------------------------------------------------------------

  const handleAlterarPassword = async (e) => {
    e.preventDefault();
    setPwErro(""); setPwSucesso("");
    if (!pwAtual || !pwNova) { setPwErro("Preencha os dois campos."); return; }
    if (pwNova.length < 8)   { setPwErro("A nova password deve ter pelo menos 8 caracteres."); return; }
    setPwLoading(true);
    try {
      await authApi.alterarPassword(pwAtual, pwNova);
      setPwSucesso("Password alterada com sucesso.");
      setPwAtual(""); setPwNova("");
    } catch (err) {
      setPwErro(err.message || "Erro ao alterar password.");
    } finally {
      setPwLoading(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Loading
  // ---------------------------------------------------------------------------

  if (loading) return (
    <div className="min-h-screen bg-[#FAF7F2] flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-[#1e3a5f] border-t-transparent rounded-full animate-spin" />
    </div>
  );

  const bio = perfil?.perfil_json || {};
  const temas = perfil?.temas_explorados || [];

  const TEMAS_LABELS = {
    memorias: "Memórias", familia: "Família", saude: "Bem-estar",
    entretenimento: "Entretenimento", exercicio: "Exercício", geral: "Conversa livre",
  };

  const inputPw = "w-full px-0 py-3 bg-transparent border-b-2 border-[#c8bfb0] focus:border-[#1e3a5f] focus:outline-none text-[#1a1a2e] text-xl transition-colors placeholder-[#c0b8af]";

  return (
    <div className="min-h-screen bg-[#FAF7F2] flex flex-col" style={{ fontFamily: "'Lora', serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />

      {/* Header */}
      <header className="bg-[#1e3a5f] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button onClick={onVoltar} className="text-[#7a9cbf] hover:text-white transition-colors p-1">
            <IconArrowLeft />
          </button>
          <div>
            <p className="text-white text-xl"
              style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "1.3rem" }}>
              O meu perfil
            </p>
            <div className="w-4 h-[1px] bg-[#c9a84c] mt-0.5" />
          </div>
        </div>
      </header>

      {/* Corpo */}
      <main className="flex-1 px-4 py-8 max-w-2xl w-full mx-auto">

        {/* Cabeçalho do perfil */}
        <div className="flex items-center gap-5 mb-8 px-2">
          <div className="w-16 h-16 rounded-full bg-[#1e3a5f] flex items-center justify-center text-white flex-shrink-0">
            <IconUser />
          </div>
          <div>
            <h2 className="text-[#1e3a5f]"
              style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "1.9rem", fontWeight: 500 }}>
              {utilizador?.nome || "Utilizador"}
            </h2>
            <p className="text-[#aaa] text-lg">{utilizador?.email}</p>
          </div>
        </div>

        {erro && (
          <p className="text-red-600 text-lg border border-red-200 bg-red-50 px-5 py-3 mb-6">{erro}</p>
        )}

        {/* Perfil biográfico */}
        <Seccao titulo="Perfil Biográfico" defaultOpen={true}>
          {Object.keys(bio).length === 0 ? (
            <p className="text-[#aaa] text-xl pt-5">
              O seu perfil biográfico ainda não foi criado. Complete o onboarding para o preencher.
            </p>
          ) : (
            <div className="mt-2">
              <LinhaPerfilBio label="Nome"              valor={bio.nome} />
              <LinhaPerfilBio label="Terra natal"       valor={bio.terra_natal} />
              <LinhaPerfilBio label="Família"           valor={bio.familia} />
              <LinhaPerfilBio label="Profissão"         valor={bio.profissao} />
              <LinhaPerfilBio label="Memória marcante"  valor={bio.memoria_marcante} />
              {bio.outros && Object.entries(bio.outros).map(([k, v]) =>
                v ? <LinhaPerfilBio key={k} label={k.replace(/_/g, " ")} valor={String(v)} /> : null
              )}
            </div>
          )}
        </Seccao>

        {/* Temas explorados */}
        <Seccao titulo="Temas Explorados">
          {temas.length === 0 ? (
            <p className="text-[#aaa] text-xl pt-5">Ainda não explorou nenhum tema.</p>
          ) : (
            <div className="flex flex-wrap gap-3 pt-5">
              {temas.map(t => (
                <span key={t}
                  className="px-4 py-2 bg-[#f0f4f8] border border-[#d0dae8] text-[#1e3a5f] text-lg">
                  {TEMAS_LABELS[t] || t}
                </span>
              ))}
            </div>
          )}
        </Seccao>

        {/* Alterar password */}
        <Seccao titulo="Segurança">
          <form onSubmit={handleAlterarPassword} noValidate className="pt-5">
            <div className="flex items-center gap-2 mb-6 text-[#888]">
              <IconLock />
              <span className="text-lg tracking-wide">Alterar password</span>
            </div>

            <div className="mb-7">
              <label className="block text-[#aaa] text-sm tracking-widest uppercase mb-2">Password atual</label>
              <input type="password" className={inputPw} value={pwAtual}
                onChange={e => setPwAtual(e.target.value)} placeholder="••••••••" />
            </div>
            <div className="mb-8">
              <label className="block text-[#aaa] text-sm tracking-widest uppercase mb-2">Nova password</label>
              <input type="password" className={inputPw} value={pwNova}
                onChange={e => setPwNova(e.target.value)} placeholder="mínimo 8 caracteres" />
            </div>

            {pwErro   && <p className="text-red-600 text-lg mb-4">{pwErro}</p>}
            {pwSucesso && <p className="text-green-700 text-lg mb-4">{pwSucesso}</p>}

            <button type="submit" disabled={pwLoading}
              className="w-full py-4 bg-[#1e3a5f] text-white text-xl font-medium hover:bg-[#163050] disabled:opacity-50 transition-colors">
              {pwLoading ? "A alterar..." : "Alterar password"}
            </button>
          </form>
        </Seccao>

        {/* Sair */}
        <button onClick={onLogout}
          className="w-full flex items-center justify-center gap-3 py-5 border-2 border-[#e8e0d5] text-[#888] hover:border-[#c0392b] hover:text-[#c0392b] transition-all duration-200 text-xl mt-2 mb-8">
          <IconLogout />
          Terminar sessão
        </button>

      </main>
    </div>
  );
}