/**
 * screens/DashboardScreen.jsx — Dashboard principal do Memórias Vivas.
 * Design: refinado, sem emojis, tipografia Cormorant Garamond + Lora.
 * Ícones SVG inline limpos para microfone e temas.
 */

import { useState, useRef, useCallback, useEffect } from "react";

// ---------------------------------------------------------------------------
// Hook — efeito de máquina de escrever
// Acumula texto num buffer e exibe a ~15 chars/seg (ritmo da fala humana)
// ---------------------------------------------------------------------------
function useTypewriter() {
  const timerRef    = useRef(null);
  const onUpdateRef = useRef(null);
  const onDoneRef   = useRef(null);

  // Inicia o typewriter com texto completo e duração alvo em ms
  const iniciarComAudio = (textoCompleto, duracaoMs, onUpdate, onDone) => {
    if (timerRef.current) clearInterval(timerRef.current);
    onUpdateRef.current = onUpdate;
    onDoneRef.current   = onDone;

    const total   = textoCompleto.length;
    if (total === 0) { onDone?.(); return; }

    // Margem de 150ms para o texto terminar ligeiramente antes do áudio
    const tickMs  = Math.max(16, (duracaoMs - 150) / total);
    let   pos     = 0;

    timerRef.current = setInterval(() => {
      pos += 1;
      onUpdateRef.current?.(textoCompleto.slice(0, pos));
      if (pos >= total) {
        clearInterval(timerRef.current);
        timerRef.current = null;
        onDoneRef.current?.();
      }
    }, tickMs);
  };

  const parar = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };

  return { iniciarComAudio, parar };
}
import ProfileScreen from "./ProfileScreen";
import { useAuth } from "../contexts/AuthContext";
import { TokenStorage, chatApi, BASE_URL } from "../api/client";

const WS_URL = BASE_URL.replace("http", "ws") + "/api/v1/audio/ws/conversa";

const TEMAS = [
  { id: "memorias",       label: "Memórias",       desc: "Histórias de vida" },
  { id: "familia",        label: "Família",         desc: "Pessoas queridas" },
  { id: "saude",          label: "Bem-estar",       desc: "Saúde e hábitos" },
  { id: "entretenimento", label: "Entretenimento",  desc: "Músicas e histórias" },
  { id: "exercicio",      label: "Exercício",       desc: "Atividade física" },
  { id: "geral",          label: "Conversa livre",  desc: "Sem tema definido" },
];

// ---------------------------------------------------------------------------
// Ícones SVG
// ---------------------------------------------------------------------------

const IconMic = ({ size = 32 }) => (
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

const IconLoader = ({ size = 28 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M21 12a9 9 0 1 1-6.219-8.56" className="animate-spin origin-center"/>
  </svg>
);

const IconArrowLeft = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M19 12H5M12 5l-7 7 7 7"/>
  </svg>
);

// ---------------------------------------------------------------------------
// Bolha de mensagem
// ---------------------------------------------------------------------------

function Bolha({ role, texto, streaming }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-5`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-[#1e3a5f] flex items-center justify-center mr-3 flex-shrink-0 mt-1">
          <div className="w-2 h-2 bg-[#c9a84c] rounded-full" />
        </div>
      )}
      <div className={[
        "max-w-[75%] px-6 py-4 text-xl leading-relaxed",
        isUser
          ? "bg-[#1e3a5f] text-white rounded-3xl rounded-br-sm"
          : "bg-white text-[#1a1a2e] rounded-3xl rounded-bl-sm border border-[#e8e0d5] shadow-sm",
      ].join(" ")} style={{ fontFamily: "'Lora', serif" }}>
        {texto}
      </div>
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-[#e8e0d5] flex items-center justify-center ml-3 flex-shrink-0 mt-1">
          <div className="w-2 h-2 bg-[#888] rounded-full" />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Botão de microfone
// ---------------------------------------------------------------------------

function MicButton({ estado, onClick }) {
  const config = {
    idle:        { bg: "bg-[#1e3a5f] hover:bg-[#163050] shadow-[0_8px_32px_rgba(30,58,95,0.35)]", label: "Prima para falar",          icone: <IconMic size={36} /> },
    gravando:    { bg: "bg-[#c0392b] hover:bg-[#a93226] shadow-[0_8px_32px_rgba(192,57,43,0.45)] scale-110", label: "A gravar — prima para parar", icone: <IconStop size={28} /> },
    processando: { bg: "bg-[#c9a84c] shadow-[0_8px_32px_rgba(201,168,76,0.35)]", label: "A processar...", icone: <IconLoader size={28} /> },
  };
  const c = config[estado];

  return (
    <div className="flex flex-col items-center gap-5">
      <button
        onClick={onClick}
        disabled={estado === "processando"}
        aria-label={c.label}
        className={[
          "w-24 h-24 rounded-full text-white flex items-center justify-center",
          "transition-all duration-300 active:scale-95",
          "disabled:cursor-not-allowed",
          c.bg,
        ].join(" ")}
      >
        {c.icone}
      </button>
      <p className="text-[#888] text-lg tracking-wide">{c.label}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dashboard principal
// ---------------------------------------------------------------------------

export default function DashboardScreen() {
  const { utilizador, logout } = useAuth();

  const [tema, setTema]           = useState(null);
  const [mensagens, setMensagens] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [micEstado, setMicEstado] = useState("idle");
  const [erro, setErro]           = useState("");
  const [encerrada, setEncerrada] = useState(false);
  const [mostrarPerfil, setMostrarPerfil] = useState(false);

  const wsRef          = useRef(null);
  const mediaRecRef    = useRef(null);
  const audioChunksRef = useRef([]);
  const audioQueueRef  = useRef([]);
  const anchorRef        = useRef(null);
  const textoCompletoRef = useRef("");     // texto acumulado até o áudio arrancar
  const typewriter     = useTypewriter();

  const ligarWS = useCallback((t) => {
    if (wsRef.current) wsRef.current.close();
    const ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => ws.send(JSON.stringify({
      type: "init", user_id: TokenStorage.getUserId(),
      session_id: null, tema: t, voz: "pt-PT-RaquelNeural",
    }));

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        audioQueueRef.current.push(event.data); return;
      }
      const msg = JSON.parse(event.data);
      if (msg.type === "pronto")      { setSessionId(msg.session_id); }
      if (msg.type === "transcricao") { setMensagens(p => [...p, { role: "user", texto: msg.texto }]); }
      if (msg.type === "resposta_inicio") {
        if (msg.session_id) setSessionId(msg.session_id);
        // Cria bolha vazia — typewriter arranca quando o áudio começar
        setMensagens(p => [...p, { role: "assistant", texto: "", streaming: true }]);
        textoCompletoRef.current = "";
      }
      if (msg.type === "resposta_chunk") {
        // Acumular texto completo para usar quando o áudio arrancar
        textoCompletoRef.current += msg.chunk;
      }
      if (msg.type === "resposta_fim") {
        // Guardar texto final — typewriter arranca no audio_fim
        textoCompletoRef.current = msg.texto;
      }
      if (msg.type === "audio_inicio") { audioQueueRef.current = []; }
      if (msg.type === "audio_fim") {
        // Áudio e texto sincronizam — audio_fim chega quando TTS terminou de gerar
        reproduzirAudio();
        setMicEstado("idle");
      }
      if (msg.type === "pedir_repeticao") { reproduzirAudio(); setMicEstado("idle"); }
      if (msg.type === "erro") { setErro(msg.mensagem); setMicEstado("idle"); }
    };

    ws.onerror = () => setErro("Erro de ligação ao servidor.");
    ws.onclose = () => setMicEstado("idle");
  }, []);

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
      // Texto e áudio arrancam juntos — typewriter calculado para terminarem ao mesmo tempo
      typewriter.iniciarComAudio(
        texto,
        duracaoMs,
        (textoVisivel) => {
          setMensagens(p => p.map((m, i) =>
            i === p.length - 1 ? { ...m, texto: textoVisivel } : m
          ));
        },
        () => {
          setMensagens(p => p.map((m, i) =>
            i === p.length - 1 ? { ...m, streaming: false } : m
          ));
        }
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

  const encerrarConversa = async () => {
    wsRef.current?.close();
    try {
      await chatApi.encerrarSessao({
        session_id: sessionId,
        historico_sessao: mensagens.map(m => ({ role: m.role, content: m.texto })),
      });
    } catch (e) { console.warn(e); }
    setEncerrada(true);
  };

  const novaConversa = () => {
    setTema(null); setMensagens([]); setSessionId(null);
    setMicEstado("idle"); setEncerrada(false); setErro("");
  };

  // ── Perfil ───────────────────────────────────────────────────────────────
  if (mostrarPerfil) return (
    <ProfileScreen
      onVoltar={() => setMostrarPerfil(false)}
      onLogout={logout}
      utilizadorInicial={utilizador}
    />
  );

  // ── Sessão encerrada ──────────────────────────────────────────────────────
  if (encerrada) return (
    <div className="min-h-screen bg-[#FAF7F2] flex items-center justify-center p-8">
      <div className="text-center max-w-md" style={{ fontFamily: "'Lora', serif" }}>
        <div className="w-16 h-[2px] bg-[#c9a84c] mx-auto mb-10" />
        <h2 className="text-[#1e3a5f] mb-4" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "2.4rem", fontWeight: 500 }}>
          Conversa guardada
        </h2>
        <p className="text-[#888] text-xl leading-relaxed mb-10">
          As suas memórias foram preservadas com segurança.
        </p>
        <button onClick={novaConversa}
          className="px-10 py-4 bg-[#1e3a5f] text-white text-xl font-medium hover:bg-[#163050] transition-colors">
          Nova conversa
        </button>
      </div>
    </div>
  );

  // ── Seleção de tema ───────────────────────────────────────────────────────
  if (!tema) return (
    <div className="min-h-screen bg-[#FAF7F2] flex flex-col" style={{ fontFamily: "'Lora', serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />

      <header className="bg-[#1e3a5f] px-8 py-5 flex items-center justify-between">
        <div>
          <span className="text-white text-2xl font-semibold tracking-wide" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "1.6rem" }}>
            Memórias Vivas
          </span>
          <div className="w-6 h-[1px] bg-[#c9a84c] mt-1" />
        </div>
        <div className="flex items-center gap-6">
          <span className="text-[#7a9cbf] text-lg">
            {utilizador?.nome?.split(" ")[0]}
          </span>
          <button onClick={() => setMostrarPerfil(true)} className="text-[#7a9cbf] hover:text-white text-lg transition-colors tracking-wide">
            Perfil
          </button>
        </div>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center px-8 py-12">
        <div className="text-center mb-12">
          <div className="w-10 h-[2px] bg-[#c9a84c] mx-auto mb-8" />
          <h1 className="text-[#1e3a5f] mb-3" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "2.6rem", fontWeight: 400 }}>
            Bom dia, {utilizador?.nome?.split(" ")[0]}
          </h1>
          <p className="text-[#888] text-xl">Escolha um tema para começar a conversar.</p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 w-full max-w-2xl">
          {TEMAS.map(t => (
            <button key={t.id} onClick={() => { setTema(t.id); ligarWS(t.id); }}
              className="group text-left p-6 bg-white border border-[#e8e0d5] hover:border-[#1e3a5f] hover:bg-[#f0f4f8] transition-all duration-200 active:scale-[0.98]">
              <p className="text-[#1e3a5f] text-xl font-semibold mb-1 group-hover:text-[#163050]">{t.label}</p>
              <p className="text-[#aaa] text-base">{t.desc}</p>
            </button>
          ))}
        </div>
      </main>
    </div>
  );

  // ── Conversa ──────────────────────────────────────────────────────────────
  const temaAtual = TEMAS.find(t => t.id === tema);

  return (
    <div className="min-h-screen bg-[#FAF7F2] flex flex-col" style={{ fontFamily: "'Lora', serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />

      <header className="bg-[#1e3a5f] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button onClick={novaConversa} className="text-[#7a9cbf] hover:text-white transition-colors p-1">
            <IconArrowLeft />
          </button>
          <div>
            <p className="text-white text-xl font-semibold">{temaAtual?.label}</p>
            <div className="w-4 h-[1px] bg-[#c9a84c] mt-0.5" />
          </div>
        </div>
        <button onClick={encerrarConversa}
          className="border border-[#3d6080] text-[#7a9cbf] hover:text-white hover:border-white px-5 py-2 text-lg transition-colors">
          Terminar
        </button>
      </header>

      {/* Mensagens */}
      <div className="flex-1 overflow-y-auto px-4 py-8 max-w-2xl w-full mx-auto">
        {mensagens.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full pt-24 text-center">
            <div className="w-8 h-[2px] bg-[#c9a84c] mx-auto mb-6" />
            <p className="text-[#bbb] text-xl">Prima o botão para começar a conversar.</p>
          </div>
        )}
        {mensagens.map((m, i) => <Bolha key={i} role={m.role} texto={m.texto} streaming={m.streaming} />)}
        <div ref={anchorRef} />
      </div>

      {erro && (
        <div className="max-w-2xl mx-auto w-full px-4 mb-2">
          <p className="text-red-600 text-lg border border-red-200 bg-red-50 px-5 py-3">{erro}</p>
        </div>
      )}

      {/* Controlo */}
      <div className="bg-white border-t border-[#e8e0d5] py-8 flex justify-center">
        <MicButton estado={micEstado} onClick={handleMic} />
      </div>
    </div>
  );
}