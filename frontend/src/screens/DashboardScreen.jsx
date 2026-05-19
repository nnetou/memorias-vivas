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
          <span style={{ color: "white", fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 500 }}>
            Memórias Vivas
          </span>
          <div className="linha-dourada" style={{ width: "24px", marginTop: "4px" }} />
        </div>
      </header>

      <main style={{ flex: 1, padding: "1.75rem 1.25rem 1.5rem", overflowY: "auto" }} className="pb-nav">
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

// ── Ecrã de conversa ───────────────────────────────────────────────────────

function EcraConversa({ tema, onVoltar, onEncerrada }) {
  const [mensagens, setMensagens] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [micEstado, setMicEstado] = useState("idle");
  const [erro, setErro]           = useState("");

  const wsRef          = useRef(null);
  const mediaRecRef    = useRef(null);
  const audioChunksRef = useRef([]);
  const audioQueueRef  = useRef([]);
  const anchorRef      = useRef(null);
  const textoCompletoRef = useRef("");
  const typewriter     = useTypewriter();

  const temaAtual = TEMAS.find(t => t.id === tema);

  // Auto-scroll
  useEffect(() => {
    anchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensagens]);

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
    const audio = new Audio(url);
    const texto = textoCompletoRef.current;

    audio.addEventListener("loadedmetadata", () => {
      const duracaoMs = audio.duration * 1000;
      typewriter.iniciarComAudio(
        texto, duracaoMs,
        (textoVisivel) => setMensagens(p => p.map((m, i) => i === p.length - 1 ? { ...m, texto: textoVisivel } : m)),
        () => setMensagens(p => p.map((m, i) => i === p.length - 1 ? { ...m, streaming: false } : m))
      );
      audio.play();
    });
    audio.load();
  };

  const handleMic = async () => {
    setErro("");
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
    wsRef.current?.close();
    try {
      await chatApi.encerrarSessao({
        session_id: sessionId,
        tema,
        historico_sessao: mensagens.map(m => ({ role: m.role, content: m.texto })),
      });
    } catch (e) { console.warn(e); }
    onEncerrada();
  };

  const micConfig = {
    idle:        { classe: "idle",       label: "Prima para falar",           icone: <IconMic size={40} /> },
    gravando:    { classe: "gravando",   label: "A gravar — prima para parar", icone: <IconStop size={34} /> },
    processando: { classe: "processando", label: "A processar...",             icone: <SpinnerIcon /> },
  };
  const mc = micConfig[micEstado] || micConfig.idle;

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "var(--creme)", height: "100dvh" }}>
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />

      {/* Header */}
      <header className="app-header" style={{ gap: "1rem" }}>
        <button onClick={onVoltar}
          style={{ background: "none", border: "none", color: "var(--azul-claro)", cursor: "pointer", padding: "0.5rem", display: "flex" }}
          aria-label="Voltar à seleção de tema">
          <IconArrowLeft />
        </button>
        <div style={{ flex: 1 }}>
          <p style={{ color: "white", fontFamily: "var(--font-serif)", fontSize: "var(--text-lg)", fontWeight: 600, margin: 0 }}>
            {temaAtual?.label || "Conversa"}
          </p>
          <div className="linha-dourada" style={{ width: "16px", marginTop: "3px" }} />
        </div>
        <button
          id="btn-terminar"
          onClick={encerrar}
          style={{
            background: "none",
            border: "1.5px solid rgba(122,156,191,0.5)",
            color: "var(--azul-claro)",
            borderRadius: "var(--radius-sm)",
            padding: "0.5rem 1rem",
            fontSize: "var(--text-sm)",
            fontFamily: "var(--font-serif)",
            cursor: "pointer",
            transition: "all 0.18s",
            minHeight: "var(--tap-min)",
          }}
          onMouseEnter={e => { e.currentTarget.style.background = "rgba(255,255,255,0.1)"; e.currentTarget.style.color = "white"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "none"; e.currentTarget.style.color = "var(--azul-claro)"; }}
        >
          Terminar
        </button>
      </header>

      {/* Mensagens */}
      <div style={{ flex: 1, overflowY: "auto", padding: "1.25rem 1rem 0.5rem" }}>
        {mensagens.length === 0 && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", textAlign: "center", paddingTop: "3rem" }}>
            <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>{temaAtual?.emoji}</div>
            <p style={{ color: "var(--cinza-claro)", fontSize: "var(--text-lg)" }}>
              Prima o botão para começar a conversar.
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
        padding: "1.5rem 1rem calc(1.5rem + var(--safe-bottom))",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "0.875rem",
        marginBottom: "72px", /* espaço para bottom nav */
      }}>
        <button
          id="btn-microfone"
          className={`mic-btn ${mc.classe}`}
          onClick={handleMic}
          disabled={micEstado === "processando"}
          aria-label={mc.label}
        >
          {mc.icone}
        </button>
        <p className="mic-label">{mc.label}</p>
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

export default function DashboardScreen({ iniciarConversa = false }) {
  const { utilizador } = useAuth();
  const [tema, setTema]       = useState(null);
  const [encerrada, setEncerrada] = useState(false);

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