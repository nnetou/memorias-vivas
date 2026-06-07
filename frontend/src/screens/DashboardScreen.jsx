/**
 * screens/DashboardScreen.jsx — Dashboard principal do Memórias Vivas.
 * Mobile-first, acessível para idosos.
 * Props:
 *   - iniciarConversa: boolean — se true, começa directamente no ecrã de conversa
 *   - onIrConversa: fn — callback para mudar tab para "conversa"
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import { TokenStorage, chatApi, BASE_URL } from "../api/client";

const WS_URL = BASE_URL.replace("http", "ws") + "/api/v1/audio/ws/conversa";

// ── Temas ──────────────────────────────────────────────────────────────────

const TEMAS = [
  {
    id: "memorias",
    label: "Memórias",
    desc: "Histórias e recordações da sua vida",
    emoji: "📖",
    cor: "#1e3a5f",
    corClaro: "#e8f0f8",
  },
  {
    id: "familia",
    label: "Família",
    desc: "Pessoas queridas e momentos especiais",
    emoji: "👨‍👩‍👧",
    cor: "#2a6049",
    corClaro: "#e6f4ef",
  },
  {
    id: "saude",
    label: "Bem-estar",
    desc: "Saúde, hábitos e qualidade de vida",
    emoji: "🌿",
    cor: "#5a3e8a",
    corClaro: "#f0ebf8",
  },
  {
    id: "entretenimento",
    label: "Entretenimento",
    desc: "Músicas, histórias e curiosidades",
    emoji: "🎵",
    cor: "#8a4e1a",
    corClaro: "#faf0e6",
  },
  {
    id: "exercicio",
    label: "Exercício",
    desc: "Atividade física adaptada à sua idade",
    emoji: "🚶",
    cor: "#1a6080",
    corClaro: "#e6f4fa",
  },
  {
    id: "geral",
    label: "Conversa livre",
    desc: "Fale sobre o que quiser",
    emoji: "💬",
    cor: "#555",
    corClaro: "#f5f5f5",
  },
];

// ── Ícones ─────────────────────────────────────────────────────────────────

const IconMic = ({ size = 36 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
    <line x1="12" y1="19" x2="12" y2="23"/>
    <line x1="8" y1="23" x2="16" y2="23"/>
  </svg>
);

const IconStop = ({ size = 32 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
    <rect x="6" y="6" width="12" height="12" rx="2"/>
  </svg>
);

const IconArrowLeft = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M19 12H5M12 5l-7 7 7 7"/>
  </svg>
);

const IconCheck = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
);

// ── Bolha de mensagem ──────────────────────────────────────────────────────

function Bolha({ role, texto, streaming }) {
  const isUser = role === "user";
  return (
    <div style={{
      display: "flex",
      justifyContent: isUser ? "flex-end" : "flex-start",
      marginBottom: "1rem",
      gap: "0.5rem",
      alignItems: "flex-end",
    }}>
      {!isUser && (
        <div style={{
          width: "36px", height: "36px", borderRadius: "50%",
          background: "var(--azul)",
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}>
          <div style={{ width: "10px", height: "10px", borderRadius: "50%", background: "var(--dourado)" }} />
        </div>
      )}
      <div style={{
        maxWidth: "78%",
        padding: "1rem 1.25rem",
        borderRadius: isUser ? "20px 20px 4px 20px" : "20px 20px 20px 4px",
        background: isUser ? "var(--azul)" : "white",
        color: isUser ? "white" : "var(--texto)",
        fontSize: "var(--text-lg)",
        lineHeight: 1.6,
        fontFamily: "var(--font-serif)",
        boxShadow: "var(--shadow-sm)",
        border: isUser ? "none" : "1px solid #e8e0d5",
        position: "relative",
      }}>
        {texto}
        {streaming && (
          <span style={{
            display: "inline-block",
            width: "6px", height: "16px",
            background: isUser ? "rgba(255,255,255,0.7)" : "var(--azul-claro)",
            borderRadius: "2px",
            marginLeft: "3px",
            animation: "spin 0.8s steps(2) infinite",
            verticalAlign: "middle",
          }} />
        )}
      </div>
    </div>
  );
}

// ── Typewriter hook ────────────────────────────────────────────────────────

function useTypewriter() {
  const timerRef = useRef(null);

  const iniciarComAudio = (textoCompleto, duracaoMs, onUpdate, onDone) => {
    if (timerRef.current) clearInterval(timerRef.current);
    const total = textoCompleto.length;
    if (total === 0) { onDone?.(); return; }
    const tickMs = Math.max(16, (duracaoMs - 150) / total);
    let pos = 0;
    timerRef.current = setInterval(() => {
      pos += 1;
      onUpdate?.(textoCompleto.slice(0, pos));
      if (pos >= total) {
        clearInterval(timerRef.current);
        timerRef.current = null;
        onDone?.();
      }
    }, tickMs);
  };

  const parar = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };

  return { iniciarComAudio, parar };
}

// ── Ecrã de selecção de tema ───────────────────────────────────────────────

function EcraTemas({ utilizador, onEscolher }) {
  const saudacao = () => {
    const h = new Date().getHours();
    if (h < 12) return "Bom dia";
    if (h < 19) return "Boa tarde";
    return "Boa noite";
  };
  const primeiroNome = utilizador?.nome?.split(" ")[0] || "";

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "var(--creme)" }}>
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />

      {/* Header */}
      <header className="app-header">
        <div>
          <span style={{ color: "var(--azul)", fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 600 }}>
            Memórias Vivas
          </span>
          <div className="linha-dourada" style={{ width: "32px", marginTop: "2px" }} />
        </div>
      </header>

      <main style={{ flex: 1, paddingTop: "1.75rem", paddingLeft: "1.25rem", paddingRight: "1.25rem", overflowY: "auto" }} className="pb-nav">
        {/* Saudação */}
        <div style={{ marginBottom: "2rem" }} className="animate-slide-down">
          <p style={{ color: "var(--cinza)", fontSize: "var(--text-sm)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "0.25rem" }}>
            {saudacao()},
          </p>
          <h1 style={{
            color: "var(--azul)",
            fontFamily: "var(--font-display)",
            fontSize: "var(--text-4xl)",
            fontWeight: 500,
            margin: 0,
            lineHeight: 1.15,
          }}>
            {primeiroNome}
          </h1>
          <p style={{ color: "var(--cinza)", fontSize: "var(--text-base)", marginTop: "0.5rem" }}>
            Sobre o que quer conversar hoje?
          </p>
        </div>

        {/* Cards de tema */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
          {TEMAS.map((t, i) => (
            <button
              key={t.id}
              id={`tema-${t.id}`}
              onClick={() => onEscolher(t.id)}
              className="animate-slide-up"
              style={{
                animationDelay: `${i * 60}ms`,
                background: "white",
                border: "1.5px solid #e8e0d5",
                borderRadius: "var(--radius-md)",
                padding: "1.25rem 1.25rem",
                display: "flex",
                alignItems: "center",
                gap: "1rem",
                cursor: "pointer",
                textAlign: "left",
                transition: "all 0.18s",
                minHeight: "var(--tap-lg)",
                boxShadow: "var(--shadow-sm)",
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = t.cor;
                e.currentTarget.style.boxShadow = `0 4px 20px ${t.cor}22`;
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = "#e8e0d5";
                e.currentTarget.style.boxShadow = "var(--shadow-sm)";
              }}
            >
              {/* Emoji ilustrativo */}
              <div style={{
                width: "52px", height: "52px", borderRadius: "var(--radius-sm)",
                background: t.corClaro,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "1.75rem",
                flexShrink: 0,
              }}>
                {t.emoji}
              </div>
              <div style={{ flex: 1 }}>
                <p style={{ color: t.cor, fontSize: "var(--text-xl)", fontWeight: 600, margin: "0 0 0.2rem", fontFamily: "var(--font-serif)" }}>
                  {t.label}
                </p>
                <p style={{ color: "var(--cinza)", fontSize: "var(--text-sm)", margin: 0 }}>
                  {t.desc}
                </p>
              </div>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={t.cor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, opacity: 0.5 }}>
                <path d="M9 18l6-6-6-6"/>
              </svg>
            </button>
          ))}
        </div>
      </main>
    </div>
  );
}

// ── Componente Mascote Raquel (SVG Animado) ─────────────────────────────────

function MascoteRaquel({ estado }) {
  return (
    <svg viewBox="0 0 200 200" className={`mascote-svg ${estado}`} fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* 1. Definições de Gradientes para aspeto premium e jovem */}
      <defs>
        <radialGradient id="pele-grad" cx="50%" cy="40%" r="60%">
          <stop offset="0%" stopColor="#FFF2E6" />
          <stop offset="100%" stopColor="#FFE3D1" />
        </radialGradient>
        <linearGradient id="cabelo-jovem-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#8D5B4C" />
          <stop offset="60%" stopColor="#6C4336" />
          <stop offset="100%" stopColor="#4A2D23" />
        </linearGradient>
        <linearGradient id="sweater-jovem-grad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#C4B5FD" />
          <stop offset="100%" stopColor="#8B5CF6" />
        </linearGradient>
      </defs>

      {/* 2. Cabelo de Fundo Volumoso (Cúpula da cabeça e laterais) */}
      <path d="M35 80C35 25 165 25 165 80C165 130 150 160 150 160C150 160 138 135 138 120C120 120 115 100 100 100C85 100 80 120 62 120C62 135 50 160 50 160C50 160 35 130 35 80Z" fill="url(#cabelo-jovem-grad)" />

      {/* 3. Corpo / Ombros com Camisola/Sweater Lilás (Jovem e Moderna) */}
      <path d="M28 200C28 145 62 120 100 120C138 120 172 145 172 200Z" fill="url(#sweater-jovem-grad)" />
      
      {/* Gola Redonda Branca / Camisa por baixo */}
      <path d="M82 120C82 135 118 135 118 120Z" fill="#FFFFFF" />
      {/* Decote elegante em V da Camisola */}
      <path d="M78 120L100 142L122 120" stroke="#7C3AED" strokeWidth="2.5" fill="none" />
      
      {/* Colar jovem delicado com brilhante de prata */}
      <path d="M88 123C92 129 108 129 112 123" stroke="#D1D5DB" strokeWidth="1" fill="none" />
      <circle cx="100" cy="129" r="2.5" fill="#E5E7EB" stroke="#9CA3AF" strokeWidth="0.5" />
      
      {/* Pescoço jovem */}
      <path d="M85 108V122C85 125 115 125 115 122V108Z" fill="#FFE3D1" />

      {/* CABELO POR CIMA DO CORPO (Madeixas compridas que caem sobre o peito/sweater) */}
      <path d="M52 110C38 130 32 155 42 190C46 198 58 198 62 190C68 170 66 145 60 120Z" fill="url(#cabelo-jovem-grad)" />
      <path d="M148 110C162 130 168 155 158 190C154 198 142 198 138 190C132 170 134 145 140 120Z" fill="url(#cabelo-jovem-grad)" />

      {/* 4. Rosto de Rapariga Jovem (Cortado no topo para nunca aparecer pele no topo da cabeça!) */}
      <path d="M59 82C59 55 141 55 141 82C141 108 128 123 100 123C72 123 59 108 59 82Z" fill="url(#pele-grad)" />
      
      {/* Bochechas Rosadas com Blush fresco de juventude */}
      <circle cx="69" cy="95" r="7.5" fill="#FFA6C9" opacity="0.6" />
      <circle cx="131" cy="95" r="7.5" fill="#FFA6C9" opacity="0.6" />

      {/* 5. Cabelo da frente (Franja moderna grossa que cobre totalmente a testa) */}
      <path d="M58 82C58 40 142 40 142 82C142 82 128 65 100 68C72 65 58 82 58 82Z" fill="url(#cabelo-jovem-grad)" />
      
      {/* Fita de cabelo/bandolete amarela moderna */}
      <path d="M60 56C70 44 130 44 140 56" stroke="#FBBF24" strokeWidth="4.5" strokeLinecap="round" fill="none" />

      {/* 6. Óculos de Armação Fina de Ouro (Super Jovem, Intelectual e Chic) */}
      <circle cx="78" cy="82" r="12" stroke="#D4AF37" strokeWidth="2" fill="none" />
      <circle cx="122" cy="82" r="12" stroke="#D4AF37" strokeWidth="2" fill="none" />
      <line x1="90" y1="82" x2="110" y2="82" stroke="#D4AF37" strokeWidth="2" strokeLinecap="round" />

      {/* 7. Expressões Faciais Dinâmicas com base no Estado */}
      
      {estado === "speaking" && (
        <>
          {/* Sobrancelhas jovens e ativas */}
          <path d="M67 63Q78 57 89 62" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <path d="M111 62Q122 57 133 63" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          {/* Olhos brilhantes com pestanas expressivas */}
          <g className="mascote-olho">
            <path d="M68 80L63 76" stroke="#2d3748" strokeWidth="1.5" strokeLinecap="round" />
            <path d="M132 80L137 76" stroke="#2d3748" strokeWidth="1.5" strokeLinecap="round" />
            <circle cx="78" cy="82" r="4.5" fill="#2d3748" />
            <circle cx="76" cy="80" r="1.5" fill="white" />
            <circle cx="122" cy="82" r="4.5" fill="#2d3748" />
            <circle cx="120" cy="80" r="1.5" fill="white" />
          </g>
          {/* Boca expressiva em movimento de fala */}
          <ellipse cx="100" cy="107" rx="6" ry="8.5" fill="#881337" className="mascote-boca-falante" />
        </>
      )}

      {estado === "speaking-happy" && (
        <>
          {/* Sobrancelhas muito felizes e levantadas */}
          <path d="M66 60Q78 51 90 60" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <path d="M110 60Q122 51 134 60" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          {/* Olhos ultra felizes e cintilantes com pestanas */}
          <g className="mascote-olho">
            <path d="M68 80L63 76" stroke="#2d3748" strokeWidth="1.5" strokeLinecap="round" />
            <path d="M132 80L137 76" stroke="#2d3748" strokeWidth="1.5" strokeLinecap="round" />
            <circle cx="78" cy="82" r="5" fill="#2d3748" />
            <circle cx="76" cy="79" r="2" fill="white" />
            <circle cx="122" cy="82" r="5" fill="#2d3748" />
            <circle cx="120" cy="79" r="2" fill="white" />
          </g>
          {/* Boca sorridente e aberta a falar com entusiasmo */}
          <ellipse cx="100" cy="107" rx="8" ry="9.5" fill="#881337" className="mascote-boca-falante" />
        </>
      )}

      {estado === "speaking-sad" && (
        <>
          {/* Sobrancelhas inclinadas em compaixão ("sinto muito") */}
          <path d="M68 64Q78 70 88 64" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <path d="M112 64Q122 70 132 64" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          {/* Olhos empáticos doces */}
          <g className="mascote-olho">
            <circle cx="78" cy="83" r="4.2" fill="#2d3748" />
            <circle cx="76" cy="81" r="1.3" fill="white" />
            <circle cx="122" cy="83" r="4.2" fill="#2d3748" />
            <circle cx="120" cy="81" r="1.3" fill="white" />
          </g>
          {/* Boca a falar de forma contida e empática */}
          <ellipse cx="100" cy="109" rx="5" ry="7" fill="#581c2f" className="mascote-boca-falante-triste" />
        </>
      )}

      {estado === "listening" && (
        <>
          {/* Sobrancelhas doces */}
          <path d="M67 65Q78 66 89 63" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <path d="M111 63Q122 66 133 65" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          {/* Olhos fechados num lindo sorriso de escuta atenta */}
          <path d="M72 82Q78 88 84 82" stroke="#2D3748" strokeWidth="3" strokeLinecap="round" fill="none" />
          <path d="M116 82Q122 88 128 82" stroke="#2D3748" strokeWidth="3" strokeLinecap="round" fill="none" />
          {/* Sorriso fechado e feliz */}
          <path d="M93 104Q100 108 107 104" stroke="#881337" strokeWidth="3" strokeLinecap="round" fill="none" />
        </>
      )}

      {estado === "thinking" && (
        <>
          {/* Sobrancelhas curiosas (uma arqueada) */}
          <path d="M66 59Q78 54 89 61" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <path d="M110 65Q122 68 133 64" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          {/* Olhos expressivos a olhar de soslaio para cima */}
          <g>
            <circle cx="80" cy="79" r="4.5" fill="#2d3748" />
            <circle cx="78" cy="77" r="1.5" fill="white" />
            <circle cx="124" cy="79" r="4.5" fill="#2d3748" />
            <circle cx="122" cy="77" r="1.5" fill="white" />
          </g>
          {/* Boca em pequeno circulo pensativo */}
          <circle cx="100" cy="106" r="4" fill="#881337" />
        </>
      )}

      {estado === "idle" && (
        <>
          {/* Sobrancelhas tranquilas */}
          <path d="M67 63Q78 59 89 63" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <path d="M111 63Q122 59 133 63" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          {/* Olhos brilhantes normais */}
          <g className="mascote-olho">
            <path d="M68 80L63 76" stroke="#2d3748" strokeWidth="1.5" strokeLinecap="round" />
            <path d="M132 80L137 76" stroke="#2d3748" strokeWidth="1.5" strokeLinecap="round" />
            <circle cx="78" cy="82" r="4.5" fill="#2d3748" />
            <circle cx="76" cy="80" r="1.5" fill="white" />
            <circle cx="122" cy="82" r="4.5" fill="#2d3748" />
            <circle cx="120" cy="80" r="1.5" fill="white" />
          </g>
          {/* Sorriso caloroso de rapariga simpática */}
          <path d="M89 102Q100 114 111 102Z" fill="#881337" />
        </>
      )}

      {estado === "idle-happy" && (
        <>
          {/* Sobrancelhas muito felizes */}
          <path d="M66 61Q78 54 90 61" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <path d="M110 61Q122 54 134 61" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          {/* Olhos super sorridentes e felizes */}
          <g className="mascote-olho">
            <path d="M68 80L63 76" stroke="#2d3748" strokeWidth="1.5" strokeLinecap="round" />
            <path d="M132 80L137 76" stroke="#2d3748" strokeWidth="1.5" strokeLinecap="round" />
            <circle cx="78" cy="82" r="4.5" fill="#2d3748" />
            <circle cx="76" cy="80" r="1.8" fill="white" />
            <circle cx="122" cy="82" r="4.5" fill="#2d3748" />
            <circle cx="120" cy="80" r="1.8" fill="white" />
          </g>
          {/* Lindo e radiante sorriso aberto de alegria ("Uau!", "Excelente!") */}
          <path d="M87 101Q100 117 113 101Z" fill="#881337" />
        </>
      )}

      {estado === "idle-sad" && (
        <>
          {/* Sobrancelhas doces inclinadas em empatia */}
          <path d="M68 64Q78 69 88 64" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <path d="M112 64Q122 69 132 64" stroke="#4A2D23" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          {/* Olhos compreensivos e gentis */}
          <g className="mascote-olho">
            <circle cx="78" cy="83" r="4.2" fill="#2d3748" />
            <circle cx="76" cy="81" r="1.3" fill="white" />
            <circle cx="122" cy="83" r="4.2" fill="#2d3748" />
            <circle cx="120" cy="81" r="1.3" fill="white" />
          </g>
          {/* Sorriso pequeno de compaixão e carinho ("Sinto muito...") */}
          <path d="M92 106Q100 110 108 106" stroke="#881337" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        </>
      )}
    </svg>
  );
}

// ── Ecrã de conversa ───────────────────────────────────────────────────────

function EcraConversa({ tema, onVoltar, onEncerrada }) {
  const [mensagens, setMensagens] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [micEstado, setMicEstado] = useState("idle");
  const [erro, setErro]           = useState("");
  const [isEncerrando, setIsEncerrando] = useState(false);
  const [isSpeaking, setIsSpeaking]     = useState(false);

  const wsRef          = useRef(null);
  const mediaRecRef    = useRef(null);
  const audioChunksRef = useRef([]);
  const audioQueueRef  = useRef([]);
  const audioPlayerRef = useRef(null);
  const anchorRef      = useRef(null);
  const textoCompletoRef = useRef("");
  const typewriter     = useTypewriter();

  const temaAtual = TEMAS.find(t => t.id === tema);

  // Auto-scroll
  useEffect(() => {
    anchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensagens]);

  // Escutar eventos de áudio para mudar o estado de fala
  useEffect(() => {
    if (!audioPlayerRef.current) {
      audioPlayerRef.current = new Audio();
    }
    const audio = audioPlayerRef.current;
    const handlePlay = () => setIsSpeaking(true);
    const handleEnd = () => setIsSpeaking(false);
    const handlePause = () => setIsSpeaking(false);

    audio.addEventListener("play", handlePlay);
    audio.addEventListener("ended", handleEnd);
    audio.addEventListener("pause", handlePause);

    return () => {
      audio.removeEventListener("play", handlePlay);
      audio.removeEventListener("ended", handleEnd);
      audio.removeEventListener("pause", handlePause);
    };
  }, []);

  // Ligar WebSocket
  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => ws.send(JSON.stringify({
      type: "init", user_id: TokenStorage.getUserId(),
      session_id: null, tema, voz: "pt-PT-RaquelNeural",
    }));

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        audioQueueRef.current.push(event.data); return;
      }
      const msg = JSON.parse(event.data);
      if (msg.type === "pronto")          { setSessionId(msg.session_id); }
      if (msg.type === "transcricao")     { setMensagens(p => [...p, { role: "user", texto: msg.texto }]); }
      if (msg.type === "resposta_inicio") {
        if (msg.session_id) setSessionId(msg.session_id);
        setMensagens(p => [...p, { role: "assistant", texto: "", streaming: true }]);
        textoCompletoRef.current = "";
      }
      if (msg.type === "resposta_chunk") { textoCompletoRef.current += msg.chunk; }
      if (msg.type === "resposta_fim")   { textoCompletoRef.current = msg.texto; }
      if (msg.type === "audio_inicio")   { audioQueueRef.current = []; }
      if (msg.type === "audio_fim")      { reproduzirAudio(); setMicEstado("idle"); }
      if (msg.type === "pedir_repeticao") { reproduzirAudio(); setMicEstado("idle"); }
      if (msg.type === "erro")           { setErro(msg.mensagem); setMicEstado("idle"); }
    };

    ws.onerror = () => setErro("Erro de ligação ao servidor.");
    ws.onclose = () => setMicEstado("idle");

    return () => ws.close();
  }, [tema]);

  const reproduzirAudio = () => {
    const q = audioQueueRef.current;
    if (!q.length) return;
    const total = q.reduce((a, b) => a + b.byteLength, 0);
    const buf = new Uint8Array(total);
    let off = 0;
    for (const c of q) { buf.set(new Uint8Array(c), off); off += c.byteLength; }
    const blob  = new Blob([buf], { type: "audio/mpeg" });
    const url   = URL.createObjectURL(blob);
    
    const audio = audioPlayerRef.current;
    audio.src = url;
    const texto = textoCompletoRef.current;

    audio.addEventListener("loadedmetadata", () => {
      const duracaoMs = audio.duration * 1000;
      typewriter.iniciarComAudio(
        texto, duracaoMs,
        (textoVisivel) => setMensagens(p => p.map((m, i) => i === p.length - 1 ? { ...m, texto: textoVisivel } : m)),
        () => setMensagens(p => p.map((m, i) => i === p.length - 1 ? { ...m, streaming: false } : m))
      );
      audio.play().catch(e => console.warn("Erro ao reproduzir áudio:", e));
    }, { once: true });
    audio.load();
  };

  const handleMic = async () => {
    setErro("");
    // Desbloquear áudio no iOS no primeiro clique do utilizador
    if (audioPlayerRef.current && !audioPlayerRef.current.unlocked) {
      audioPlayerRef.current.src = "data:audio/mp3;base64,//NExAAAAANIAAAAAExBTUUzLjEwMKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq";
      audioPlayerRef.current.play().catch(() => {}).finally(() => {
        audioPlayerRef.current.unlocked = true;
      });
    }

    if (micEstado === "idle") {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
        audioChunksRef.current = [];
        rec.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
        rec.onstop = async () => {
          const buf = await new Blob(audioChunksRef.current, { type: "audio/webm" }).arrayBuffer();
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(buf); setMicEstado("processando");
          }
          stream.getTracks().forEach(t => t.stop());
        };
        rec.start(); mediaRecRef.current = rec; setMicEstado("gravando");
      } catch { setErro("Não foi possível aceder ao microfone."); }
    } else if (micEstado === "gravando") {
      mediaRecRef.current?.stop();
    }
  };

  const encerrar = async () => {
    setIsEncerrando(true);
    wsRef.current?.close();
    try {
      await chatApi.encerrarSessao({
        session_id: sessionId,
        tema,
        historico_sessao: mensagens.map(m => ({ role: m.role, content: m.texto })),
      });
    } catch (e) { console.warn(e); }
    setIsEncerrando(false);
    onEncerrada();
  };

  const micConfig = {
    idle:        { classe: "idle",       label: "Prima para falar",           icone: <IconMic size={40} /> },
    gravando:    { classe: "gravando",   label: "A gravar — prima para parar", icone: <IconStop size={34} /> },
    processando: { classe: "processando", label: "A processar...",             icone: <SpinnerIcon /> },
  };
  const mc = micConfig[micEstado] || micConfig.idle;

  let companionState = "idle";
  
  // Obter o texto da última resposta da assistente para detetar a emoção
  const ultimaMsgAssistente = [...mensagens].reverse().find(m => m.role === "assistant")?.texto || "";
  const textoLower = ultimaMsgAssistente.toLowerCase();
  
  const palavrasFelizes = ["ótimo", "otimo", "maravilha", "uau", "excelente", "que bom", "fantástico", "fantastico", "espetacular", "lindo", "alegria", "parabéns", "parabens", "adoro", "gosto muito", "divertido", "sorriso", "feliz", "celebrar", "linda"];
  const palavrasTristes = ["sinto muito", "que pena", "lamento", "triste", "lamentável", "lamentavel", "pena", "coitado", "dor", "saudade", "difícil", "dificil", "complicado", "doença", "doenca", "falecer", "partiu", "morreu"];
  
  const isTriste = palavrasTristes.some(p => textoLower.includes(p));
  const isFeliz = palavrasFelizes.some(p => textoLower.includes(p));

  if (isSpeaking) {
    if (isTriste) {
      companionState = "speaking-sad";
    } else if (isFeliz) {
      companionState = "speaking-happy";
    } else {
      companionState = "speaking";
    }
  } else if (micEstado === "gravando") {
    companionState = "listening";
  } else if (micEstado === "processando") {
    companionState = "thinking";
  } else {
    // Idle com sentimento herdado da última interação
    if (isTriste) {
      companionState = "idle-sad";
    } else if (isFeliz) {
      companionState = "idle-happy";
    } else {
      companionState = "idle";
    }
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "var(--creme)", height: "100dvh", overflow: "hidden" }}>
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />

      {/* Header */}
      <header className="app-header" style={{ gap: "1rem", flexShrink: 0 }}>
        <button onClick={onVoltar}
          style={{ background: "none", border: "none", color: "var(--azul)", cursor: "pointer", padding: "0.5rem", display: "flex", marginLeft: "-0.5rem" }}
          aria-label="Voltar à seleção de tema">
          <IconArrowLeft />
        </button>
        <div style={{ flex: 1 }}>
          <p style={{ color: "var(--azul)", fontFamily: "var(--font-serif)", fontSize: "var(--text-lg)", fontWeight: 600, margin: 0 }}>
            {temaAtual?.label || "Conversa"}
          </p>
          <div className="linha-dourada" style={{ width: "16px", marginTop: "3px" }} />
        </div>
        <button
          id="btn-terminar"
          onClick={encerrar}
          disabled={isEncerrando}
          style={{
            background: "none",
            border: "1.5px solid var(--azul)",
            color: "var(--azul)",
            borderRadius: "var(--radius-sm)",
            padding: "0.5rem 1rem",
            fontSize: "var(--text-sm)",
            fontFamily: "var(--font-serif)",
            cursor: isEncerrando ? "wait" : "pointer",
            transition: "all 0.18s",
            minHeight: "var(--tap-min)",
            opacity: isEncerrando ? 0.7 : 1,
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
          onMouseEnter={e => { if (!isEncerrando) { e.currentTarget.style.background = "var(--azul)"; e.currentTarget.style.color = "white"; } }}
          onMouseLeave={e => { if (!isEncerrando) { e.currentTarget.style.background = "none"; e.currentTarget.style.color = "var(--azul)"; } }}
        >
          {isEncerrando ? (
            <>
              <SpinnerIcon />
              A guardar...
            </>
          ) : (
            "Terminar"
          )}
        </button>
      </header>

      {/* Visual da Mascote em Estilo Vídeochamada (Duolingo) */}
      <div className="video-call-layout">
        
        {/* Painel da Raquel (Vídeo superior ou esquerdo) */}
        <div className="companion-panel">
          {/* Badge de Estado centralizado horizontalmente com o corpo */}
          <div style={{
            position: "absolute",
            top: "1rem",
            left: "50%",
            transform: "translateX(-50%)",
            background: "rgba(0, 0, 0, 0.4)",
            backdropFilter: "blur(8px)",
            padding: "0.4rem 0.8rem",
            borderRadius: "9999px",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            zIndex: 10
          }}>
            <span style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: companionState === "speaking" ? "#a855f7" : companionState === "listening" ? "#06b6d4" : companionState === "thinking" ? "#eab308" : "#10b981",
              boxShadow: "0 0 8px currentColor",
              display: "inline-block"
            }} />
            <span style={{ color: "white", fontSize: "0.8rem", fontFamily: "var(--font-serif)" }}>
              {companionState === "speaking" ? "A falar..." : companionState === "listening" ? "A ouvi-lo..." : companionState === "thinking" ? "A pensar..." : "Raquel (Assistente)"}
            </span>
          </div>

          <div className={`avatar-halo ${companionState}`}>
            <MascoteRaquel estado={companionState} />
            {/* Sparkles quando feliz a falar */}
            {(companionState === "speaking-happy" || companionState === "idle-happy") && (
              <div className="mascote-sparkles">
                <span className="sparkle">✨</span>
                <span className="sparkle">⭐</span>
                <span className="sparkle">✨</span>
                <span className="sparkle">⭐</span>
                <span className="sparkle">✨</span>
                <span className="sparkle">⭐</span>
              </div>
            )}
            {/* Dots de pensamento */}
            {companionState === "thinking" && (
              <div className="think-dots">
                <div className="think-dot" />
                <div className="think-dot" />
                <div className="think-dot" />
              </div>
            )}
            {/* Rings de escuta pulsantes */}
            {companionState === "listening" && (
              <>
                <div className="listen-ring" />
                <div className="listen-ring" />
              </>
            )}
          </div>

          {/* Ondas sonoras animadas */}
          <div className={`sound-waves ${companionState === "speaking" ? "speaking" : ""}`}>
            <div className="sound-bar" />
            <div className="sound-bar" />
            <div className="sound-bar" />
            <div className="sound-bar" />
            <div className="sound-bar" />
          </div>
        </div>

        {/* Painel do Chat e Transcrição */}
        <div className="chat-panel">
          <div style={{ flex: 1, overflowY: "auto", padding: "1.25rem 1rem 0.5rem" }}>
            {mensagens.length === 0 && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", textAlign: "center", padding: "2rem" }}>
                <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>{temaAtual?.emoji}</div>
                <p style={{ color: "var(--texto-suave)", fontSize: "var(--text-lg)", fontFamily: "var(--font-serif)", lineHeight: "1.6" }}>
                  Olá, sou a Raquel! Carregue no microfone abaixo e vamos conversar sobre as suas memórias mais bonitas. Estou pronta a ouvi-lo!
                </p>
              </div>
            )}
            {mensagens.map((m, i) => <Bolha key={i} role={m.role} texto={m.texto} streaming={m.streaming} />)}
            <div ref={anchorRef} />
          </div>

          {/* Erro */}
          {erro && (
            <div style={{
              margin: "0 1rem 0.5rem",
              padding: "0.875rem 1.25rem",
              background: "#fef2f2",
              border: "1px solid #fca5a5",
              borderRadius: "var(--radius-sm)",
              color: "#b91c1c",
              fontSize: "var(--text-base)",
            }} role="alert">
              {erro}
            </div>
          )}

          {/* Controlo microfone */}
          <div style={{
            background: "white",
            borderTop: "1px solid #e8e0d5",
            padding: "1.25rem 1rem calc(1.25rem + var(--safe-bottom))",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "0.75rem",
            flexShrink: 0
          }}>
            <button
              id="btn-microfone"
              className={`mic-btn ${mc.classe}`}
              onClick={handleMic}
              disabled={micEstado === "processando"}
              aria-label={mc.label}
              style={{ width: "90px", height: "90px" }}
            >
              {mc.icone}
            </button>
            <p className="mic-label" style={{ margin: 0, fontSize: "var(--text-sm)" }}>{mc.label}</p>
          </div>
        </div>

      </div>
    </div>
  );
}

// ── Ecrã "conversa encerrada" ──────────────────────────────────────────────

function EcraEncerrada({ onNova }) {
  return (
    <div style={{
      flex: 1, display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      padding: "2rem", textAlign: "center",
      background: "var(--creme)",
    }} className="animate-fade-in">
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />
      <div style={{
        width: "72px", height: "72px", borderRadius: "50%",
        background: "#e6f4ef",
        display: "flex", alignItems: "center", justifyContent: "center",
        marginBottom: "1.5rem",
      }}>
        <IconCheck />
      </div>
      <div className="linha-dourada" style={{ width: "40px", margin: "0 auto 1.5rem" }} />
      <h2 style={{
        color: "var(--azul)",
        fontFamily: "var(--font-display)",
        fontSize: "var(--text-3xl)",
        fontWeight: 500,
        margin: "0 0 0.75rem",
      }}>
        Conversa guardada
      </h2>
      <p style={{ color: "var(--cinza)", fontSize: "var(--text-lg)", lineHeight: 1.6, maxWidth: "320px", marginBottom: "2.5rem" }}>
        As suas memórias foram preservadas com segurança.
      </p>
      <button
        id="btn-nova-conversa"
        className="btn-primary"
        onClick={onNova}
        style={{ maxWidth: "280px" }}
      >
        Nova conversa
      </button>
    </div>
  );
}

// ── Componente principal ───────────────────────────────────────────────────

export default function DashboardScreen({ iniciarConversa = false, onConversaAtivaChange }) {
  const { utilizador } = useAuth();
  const [tema, setTema]       = useState(null);
  const [encerrada, setEncerrada] = useState(false);

  // Reportar se a conversa está ativa para o App.jsx poder ocultar o BottomNav
  useEffect(() => {
    if (onConversaAtivaChange) {
      onConversaAtivaChange(!!tema && !encerrada);
    }
  }, [tema, encerrada, onConversaAtivaChange]);

  const handleEscolherTema = (id) => {
    setTema(id);
    setEncerrada(false);
  };

  const handleVoltar = () => setTema(null);
  const handleEncerrada = () => setEncerrada(true);
  const handleNova = () => { setTema(null); setEncerrada(false); };

  if (encerrada)
    return <EcraEncerrada onNova={handleNova} />;

  if (tema)
    return <EcraConversa tema={tema} onVoltar={handleVoltar} onEncerrada={handleEncerrada} />;

  return <EcraTemas utilizador={utilizador} onEscolher={handleEscolherTema} />;
}

// ── Helpers visuais ────────────────────────────────────────────────────────

function SpinnerIcon() {
  return (
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" style={{ animation: "spin 1s linear infinite", transformOrigin: "center" }}/>
    </svg>
  );
}