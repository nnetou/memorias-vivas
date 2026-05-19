/**
 * screens/PortfolioScreen.jsx — Portfólio do utilizador (Epic 6).
 * Mobile-first: cards full-width, botões de geração como accordion.
 */

import { useState, useEffect } from "react";
import { artefactosApi, BASE_URL } from "../api/client";

// ── Ícones ──────────────────────────────────────────────────────────────────

const IconArrowLeft = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M19 12H5M12 5l-7 7 7 7"/>
  </svg>
);

const IconFileText = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/>
    <line x1="16" y1="17" x2="8" y2="17"/>
  </svg>
);

const IconDownload = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7 10 12 15 17 10"/>
    <line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
);

const IconVideo = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="23 7 16 12 23 17 23 7"/>
    <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
  </svg>
);

const IconTimeline = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="2" x2="12" y2="22"/>
    <line x1="12" y1="6" x2="16" y2="6"/>
    <line x1="12" y1="12" x2="8" y2="12"/>
    <line x1="12" y1="18" x2="16" y2="18"/>
  </svg>
);

const IconCards = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
    <line x1="3" y1="9" x2="21" y2="9"/>
    <line x1="9" y1="21" x2="9" y2="9"/>
  </svg>
);

const IconPlus = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19"/>
    <line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
);

const IconChevronDown = ({ open }) => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.25s" }}>
    <polyline points="6 9 12 15 18 9"/>
  </svg>
);

function SpinnerInline() {
  return (
    <span style={{
      display: "inline-block",
      width: "18px", height: "18px",
      border: "2px solid rgba(255,255,255,0.4)",
      borderTopColor: "white",
      borderRadius: "50%",
      animation: "spin 0.9s linear infinite",
      flexShrink: 0,
    }} />
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

// ── Configuração dos tipos de artefacto ─────────────────────────────────────

const TIPO_CONFIG = {
  livro_pdf:     { label: "Livro de Memórias",    Icon: IconFileText,  cor: "#1e3a5f", bg: "#e8f0f8", emoji: "📖" },
  timeline_html: { label: "Linha Temporal",        Icon: IconTimeline,  cor: "#8a6e00", bg: "#faf3d8", emoji: "📅" },
  cartoes_pdf:   { label: "Cartões de Histórias",  Icon: IconCards,     cor: "#4a2a7e", bg: "#f0ebf8", emoji: "🃏" },
  video_mp4:     { label: "Vídeo Ilustrativo",     Icon: IconVideo,     cor: "#7e1a1a", bg: "#faeaea", emoji: "🎬" },
};

const BOTOES_GERACAO = [
  {
    id: "livro",
    tipo: "livro_pdf",
    desc: "Um livro em PDF com as suas memórias organizadas",
    fn: "gerarLivro",
  },
  {
    id: "timeline",
    tipo: "timeline_html",
    desc: "Uma linha do tempo visual da sua vida",
    fn: "gerarTimeline",
  },
  {
    id: "cartoes",
    tipo: "cartoes_pdf",
    desc: "Cartões ilustrados com as suas histórias",
    fn: "gerarCartoes",
  },
  {
    id: "video",
    tipo: "video_mp4",
    desc: "Um vídeo com as suas memórias em imagens",
    fn: "gerarVideo",
  },
];

// ── Card de artefacto gerado ─────────────────────────────────────────────────

function ArtefactoCard({ artefacto }) {
  const conf = TIPO_CONFIG[artefacto.tipo] || { label: artefacto.tipo, Icon: IconFileText, cor: "#888", bg: "#f5f5f5", emoji: "📄" };
  const downloadUrl = BASE_URL + artefacto.url_download;

  return (
    <div style={{
      background: "white",
      border: "1.5px solid #e8e0d5",
      borderRadius: "var(--radius-md)",
      padding: "1.25rem",
      display: "flex",
      alignItems: "center",
      gap: "1rem",
      boxShadow: "var(--shadow-sm)",
    }} className="animate-slide-up">
      {/* Ícone */}
      <div style={{
        width: "52px", height: "52px",
        borderRadius: "var(--radius-sm)",
        background: conf.bg,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "1.6rem",
        flexShrink: 0,
      }}>
        {conf.emoji}
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ color: conf.cor, fontSize: "var(--text-lg)", fontWeight: 600, margin: "0 0 0.2rem", fontFamily: "var(--font-serif)" }}>
          {conf.label}
        </p>
        <p style={{ color: "var(--cinza)", fontSize: "var(--text-xs)", margin: 0 }}>
          {artefacto.gerado_em}
        </p>
      </div>

      {/* Descarregar */}
      <a
        href={downloadUrl}
        target="_blank"
        rel="noopener noreferrer"
        download
        aria-label={`Descarregar ${conf.label}`}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "48px", height: "48px",
          borderRadius: "var(--radius-sm)",
          background: "var(--creme)",
          color: "var(--azul)",
          border: "1.5px solid #e8e0d5",
          transition: "all 0.18s",
          flexShrink: 0,
        }}
        onMouseEnter={e => { e.currentTarget.style.background = "var(--azul)"; e.currentTarget.style.color = "white"; }}
        onMouseLeave={e => { e.currentTarget.style.background = "var(--creme)"; e.currentTarget.style.color = "var(--azul)"; }}
      >
        <IconDownload />
      </a>
    </div>
  );
}

// ── Ecrã principal ───────────────────────────────────────────────────────────

export default function PortfolioScreen() {
  const [artefactos,    setArtefactos]    = useState([]);
  const [loading,       setLoading]       = useState(true);
  const [erro,          setErro]          = useState("");
  const [gerandoId,     setGerandoId]     = useState(null);
  const [panelAberto,   setPanelAberto]   = useState(false);

  useEffect(() => { carregarArtefactos(); }, []);

  const carregarArtefactos = async () => {
    setLoading(true); setErro("");
    try {
      const data = await artefactosApi.listar();
      setArtefactos(data.artefactos || []);
    } catch { setErro("Não foi possível carregar os ficheiros."); }
    finally { setLoading(false); }
  };

  const gerar = async (id, fn) => {
    setErro(""); setGerandoId(id);
    try {
      await artefactosApi[fn]();
      await carregarArtefactos();
    } catch (err) { setErro(err.message || "Erro ao gerar ficheiro."); }
    finally { setGerandoId(null); }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "var(--creme)" }}>
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />

      {/* Header */}
      <header className="app-header">
        <div>
          <span style={{ color: "white", fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 500 }}>
            O meu Portfólio
          </span>
          <div className="linha-dourada" style={{ width: "24px", marginTop: "4px" }} />
        </div>
      </header>

      {/* Conteúdo */}
      <main style={{ flex: 1, padding: "1.5rem 1.25rem", overflowY: "auto" }} className="pb-nav">

        {/* Erro */}
        {erro && (
          <div style={{
            background: "#fef2f2", border: "1px solid #fca5a5",
            borderRadius: "var(--radius-sm)", padding: "1rem 1.25rem",
            marginBottom: "1.25rem", color: "#b91c1c",
            fontSize: "var(--text-base)",
          }} role="alert">
            {erro}
          </div>
        )}

        {/* Lista de artefactos */}
        <section style={{ marginBottom: "2rem" }}>
          <h2 style={{
            color: "var(--azul)", fontFamily: "var(--font-display)",
            fontSize: "var(--text-2xl)", fontWeight: 500,
            margin: "0 0 1rem",
          }}>
            Ficheiros gerados
          </h2>

          {loading ? (
            <div style={{ display: "flex", justifyContent: "center", paddingTop: "3rem" }}>
              <SpinnerAzul />
            </div>
          ) : artefactos.length === 0 ? (
            <div style={{
              textAlign: "center", padding: "3rem 1rem",
              border: "2px dashed #e8e0d5",
              borderRadius: "var(--radius-md)",
            }}>
              <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>📂</div>
              <p style={{ color: "var(--cinza)", fontSize: "var(--text-lg)", margin: 0 }}>
                Ainda não gerou nenhum ficheiro.
              </p>
              <p style={{ color: "var(--cinza-claro)", fontSize: "var(--text-base)", marginTop: "0.35rem" }}>
                Use o botão abaixo para começar.
              </p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
              {artefactos.map(a => <ArtefactoCard key={a.id} artefacto={a} />)}
            </div>
          )}
        </section>

        {/* Painel de geração — accordion */}
        <section>
          <button
            id="btn-toggle-geracao"
            onClick={() => setPanelAberto(o => !o)}
            style={{
              width: "100%",
              background: "var(--azul)",
              color: "white",
              border: "none",
              borderRadius: "var(--radius-md)",
              padding: "1.1rem 1.5rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "0.75rem",
              cursor: "pointer",
              fontSize: "var(--text-lg)",
              fontFamily: "var(--font-serif)",
              fontWeight: 600,
              minHeight: "var(--tap-lg)",
              transition: "background 0.18s",
            }}
            onMouseEnter={e => e.currentTarget.style.background = "var(--azul-escuro)"}
            onMouseLeave={e => e.currentTarget.style.background = "var(--azul)"}
          >
            <span style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
              <IconPlus /> Gerar novo ficheiro
            </span>
            <IconChevronDown open={panelAberto} />
          </button>

          {panelAberto && (
            <div style={{
              background: "white",
              border: "1.5px solid #e8e0d5",
              borderTop: "none",
              borderRadius: "0 0 var(--radius-md) var(--radius-md)",
              padding: "0.5rem 1rem 1rem",
              display: "flex",
              flexDirection: "column",
              gap: "0.625rem",
            }} className="animate-slide-down">
              {BOTOES_GERACAO.map(({ id, tipo, desc, fn }) => {
                const conf = TIPO_CONFIG[tipo];
                const gerando = gerandoId === id;
                return (
                  <button
                    key={id}
                    id={`btn-gerar-${id}`}
                    onClick={() => gerar(id, fn)}
                    disabled={!!gerandoId}
                    style={{
                      width: "100%",
                      background: gerando ? conf.cor : conf.bg,
                      border: `1.5px solid ${conf.cor}33`,
                      borderRadius: "var(--radius-sm)",
                      padding: "1rem 1.25rem",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.875rem",
                      cursor: gerandoId ? "not-allowed" : "pointer",
                      opacity: gerandoId && !gerando ? 0.5 : 1,
                      transition: "all 0.18s",
                      textAlign: "left",
                      minHeight: "var(--tap-lg)",
                    }}
                  >
                    <div style={{
                      width: "40px", height: "40px",
                      borderRadius: "var(--radius-sm)",
                      background: gerando ? "rgba(255,255,255,0.2)" : conf.cor,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      flexShrink: 0, fontSize: "1.25rem",
                    }}>
                      {gerando ? <SpinnerInline /> : conf.emoji}
                    </div>
                    <div style={{ flex: 1 }}>
                      <p style={{ color: gerando ? "white" : conf.cor, fontSize: "var(--text-base)", fontWeight: 600, margin: "0 0 0.15rem", fontFamily: "var(--font-serif)" }}>
                        {conf.label}
                      </p>
                      <p style={{ color: gerando ? "rgba(255,255,255,0.7)" : "var(--cinza)", fontSize: "var(--text-xs)", margin: 0 }}>
                        {gerando ? "A gerar..." : desc}
                      </p>
                    </div>
                  </button>
                );
              })}

              <p style={{ color: "var(--cinza-claro)", fontSize: "var(--text-xs)", textAlign: "center", marginTop: "0.25rem", lineHeight: 1.5 }}>
                A geração pode demorar alguns segundos.
              </p>
            </div>
          )}
        </section>

      </main>
    </div>
  );
}
