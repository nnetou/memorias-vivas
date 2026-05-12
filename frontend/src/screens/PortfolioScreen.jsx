/**
 * screens/PortfolioScreen.jsx — Ecrã de portfólio (Epic 6).
 *
 * Lista os artefactos gerados e permite gerar novos.
 */

import { useState, useEffect } from "react";
import { artefactosApi, BASE_URL } from "../api/client";

// ---------------------------------------------------------------------------
// Ícones SVG
// ---------------------------------------------------------------------------

const IconArrowLeft = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M19 12H5M12 5l-7 7 7 7"/>
  </svg>
);

const IconFileText = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="16" y1="13" x2="8" y2="13"/>
    <line x1="16" y1="17" x2="8" y2="17"/>
    <polyline points="10 9 9 9 8 9"/>
  </svg>
);

const IconDownload = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7 10 12 15 17 10"/>
    <line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
);

const IconVideo = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="23 7 16 12 23 17 23 7"/>
    <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
  </svg>
);

const IconTimeline = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="2" x2="12" y2="22"/>
    <line x1="12" y1="6" x2="16" y2="6"/>
    <line x1="12" y1="12" x2="8" y2="12"/>
    <line x1="12" y1="18" x2="16" y2="18"/>
  </svg>
);

const IconCards = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
    <line x1="3" y1="9" x2="21" y2="9"/>
    <line x1="9" y1="21" x2="9" y2="9"/>
  </svg>
);

const IconLoader = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M21 12a9 9 0 1 1-6.219-8.56" className="animate-spin origin-center"/>
  </svg>
);

// ---------------------------------------------------------------------------
// Componentes visuais
// ---------------------------------------------------------------------------

const TIPO_CONFIG = {
  livro_pdf:     { label: "Livro de Memórias", icon: <IconFileText />, cor: "#1e3a5f" },
  timeline_html: { label: "Linha Temporal",    icon: <IconTimeline />, cor: "#c9a84c" },
  cartoes_pdf:   { label: "Cartões de Histórias", icon: <IconCards />,    cor: "#2a2a4e" },
  video_mp4:     { label: "Vídeo Ilustrativo", icon: <IconVideo />,    cor: "#c0392b" },
};

function ArtefactoCard({ artefacto }) {
  const conf = TIPO_CONFIG[artefacto.tipo] || { label: artefacto.tipo, icon: <IconFileText />, cor: "#888" };
  const downloadUrl = BASE_URL + artefacto.url_download;

  return (
    <div className="bg-white border border-[#e8e0d5] p-5 flex items-center justify-between hover:border-[#1e3a5f] transition-colors mb-4">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded flex items-center justify-center flex-shrink-0" style={{ backgroundColor: conf.cor, color: "white" }}>
          {conf.icon}
        </div>
        <div>
          <h3 className="text-[#1e3a5f] text-lg font-semibold" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "1.4rem" }}>
            {conf.label}
          </h3>
          <p className="text-[#aaa] text-sm">Gerado em {artefacto.gerado_em}</p>
        </div>
      </div>
      <a
        href={downloadUrl}
        target="_blank"
        rel="noopener noreferrer"
        download
        className="p-3 text-[#7a9cbf] hover:text-[#1e3a5f] hover:bg-[#f0f4f8] rounded transition-colors"
        title="Descarregar"
      >
        <IconDownload />
      </a>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ecrã Principal
// ---------------------------------------------------------------------------

export default function PortfolioScreen({ onVoltar }) {
  const [artefactos, setArtefactos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  
  // Estado de loading para botões de geração
  const [gerandoLivro, setGerandoLivro] = useState(false);
  const [gerandoTimeline, setGerandoTimeline] = useState(false);
  const [gerandoCartoes, setGerandoCartoes] = useState(false);
  const [gerandoVideo, setGerandoVideo] = useState(false);

  useEffect(() => {
    carregarArtefactos();
  }, []);

  const carregarArtefactos = async () => {
    setLoading(true);
    setErro("");
    try {
      const data = await artefactosApi.listar();
      setArtefactos(data.artefactos || []);
    } catch (err) {
      setErro("Não foi possível carregar os artefactos.");
    } finally {
      setLoading(false);
    }
  };

  const wrapGeracao = async (setter, fn) => {
    setErro("");
    setter(true);
    try {
      await fn();
      await carregarArtefactos();
    } catch (err) {
      setErro(err.message || "Erro ao gerar artefacto.");
    } finally {
      setter(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF7F2] flex flex-col" style={{ fontFamily: "'Lora', serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />

      {/* Header */}
      <header className="bg-[#1e3a5f] px-6 py-4 flex items-center gap-4">
        <button onClick={onVoltar} className="text-[#7a9cbf] hover:text-white transition-colors p-1">
          <IconArrowLeft />
        </button>
        <div>
          <p className="text-white text-xl" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "1.3rem" }}>
            O meu portfólio
          </p>
          <div className="w-4 h-[1px] bg-[#c9a84c] mt-0.5" />
        </div>
      </header>

      {/* Corpo */}
      <main className="flex-1 px-4 py-8 max-w-4xl w-full mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
        
        {/* Coluna Principal: Lista de Artefactos */}
        <div className="md:col-span-2">
          <h2 className="text-[#1e3a5f] mb-6" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "2rem" }}>
            Ficheiros gerados
          </h2>

          {erro && (
            <p className="text-red-600 text-lg border border-red-200 bg-red-50 px-5 py-3 mb-6">
              {erro}
            </p>
          )}

          {loading ? (
            <div className="flex justify-center py-12">
              <div className="w-8 h-8 border-2 border-[#1e3a5f] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : artefactos.length === 0 ? (
            <div className="text-center py-12 border-2 border-dashed border-[#e8e0d5]">
              <p className="text-[#888] text-xl">Ainda não gerou nenhum ficheiro.</p>
              <p className="text-[#aaa] mt-2">Use os botões ao lado para começar.</p>
            </div>
          ) : (
            <div>
              {artefactos.map((a) => (
                <ArtefactoCard key={a.id} artefacto={a} />
              ))}
            </div>
          )}
        </div>

        {/* Coluna Lateral: Botões de Geração */}
        <div className="bg-white border border-[#e8e0d5] p-6 self-start">
          <h3 className="text-[#1e3a5f] mb-6 border-b border-[#f0ebe3] pb-3" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "1.5rem" }}>
            Gerar novos
          </h3>

          <div className="flex flex-col gap-4">
            <button
              onClick={() => wrapGeracao(setGerandoLivro, artefactosApi.gerarLivro)}
              disabled={gerandoLivro}
              className="flex items-center gap-3 w-full p-4 border border-[#1e3a5f] text-[#1e3a5f] hover:bg-[#1e3a5f] hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-left"
            >
              {gerandoLivro ? <IconLoader /> : <IconFileText />}
              <span className="font-semibold tracking-wide">Livro de Memórias</span>
            </button>

            <button
              onClick={() => wrapGeracao(setGerandoTimeline, artefactosApi.gerarTimeline)}
              disabled={gerandoTimeline}
              className="flex items-center gap-3 w-full p-4 border border-[#c9a84c] text-[#c9a84c] hover:bg-[#c9a84c] hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-left"
            >
              {gerandoTimeline ? <IconLoader /> : <IconTimeline />}
              <span className="font-semibold tracking-wide">Linha Temporal</span>
            </button>

            <button
              onClick={() => wrapGeracao(setGerandoCartoes, artefactosApi.gerarCartoes)}
              disabled={gerandoCartoes}
              className="flex items-center gap-3 w-full p-4 border border-[#2a2a4e] text-[#2a2a4e] hover:bg-[#2a2a4e] hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-left"
            >
              {gerandoCartoes ? <IconLoader /> : <IconCards />}
              <span className="font-semibold tracking-wide">Cartões de Histórias</span>
            </button>

            <button
              onClick={() => wrapGeracao(setGerandoVideo, artefactosApi.gerarVideo)}
              disabled={gerandoVideo}
              className="flex items-center gap-3 w-full p-4 border border-[#c0392b] text-[#c0392b] hover:bg-[#c0392b] hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-left"
            >
              {gerandoVideo ? <IconLoader /> : <IconVideo />}
              <span className="font-semibold tracking-wide">Vídeo Ilustrativo</span>
            </button>
          </div>
          
          <p className="text-xs text-[#aaa] mt-6 leading-relaxed">
            A geração pode demorar alguns segundos, especialmente para vídeos. Os ficheiros aparecerão na lista quando concluídos.
          </p>
        </div>

      </main>
    </div>
  );
}
