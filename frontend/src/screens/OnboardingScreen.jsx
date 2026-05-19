/**
 * screens/OnboardingScreen.jsx — Onboarding conversacional por voz.
 * Mobile-first com barra de progresso, microfone grande e texto legível.
 */

import { useState, useEffect, useRef } from "react";
import { TokenStorage } from "../api/client";
import { useAuth } from "../contexts/AuthContext";

const BASE     = import.meta.env.VITE_API_URL || window.location.origin;
const CHAT_API = `${BASE}/api/v1/chat`;
const AUDIO    = `${BASE}/api/v1/audio`;

// Alucinações conhecidas do Whisper
const ALUCINACOES = new Set([
  "pesquisa de pesquisa", "obrigado", "obrigado.", "legendas por",
  "transcrição", "subtítulos", "subtitle", "thanks for watching",
  "legendas", "[música]", "[music]", "silence", ".", "...",
]);

const isAlucinacao = (texto) => {
  const t = texto.trim().toLowerCase().replace(/\.$/, "");
  return !texto || texto.trim().length < 3 || ALUCINACOES.has(t);
};

// ── Ícones ─────────────────────────────────────────────────────────────────

const IconMic = () => (
  <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
    <line x1="12" y1="19" x2="12" y2="23"/>
    <line x1="8" y1="23" x2="16" y2="23"/>
  </svg>
);

const IconStop = () => (
  <svg width="38" height="38" viewBox="0 0 24 24" fill="currentColor">
    <rect x="6" y="6" width="12" height="12" rx="2"/>
  </svg>
);

// ── Barra de progresso ─────────────────────────────────────────────────────

function BarraProgresso({ passo, total = 5 }) {
  return (
    <div style={{ padding: "1rem 1.5rem 0" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
        <span style={{ color: "var(--azul-claro)", fontSize: "var(--text-xs)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
          Apresentação
        </span>
        <span style={{ color: "var(--dourado)", fontSize: "var(--text-xs)", fontWeight: 600 }}>
          {Math.min(passo, total)} / {total}
        </span>
      </div>
      <div style={{ height: "3px", background: "rgba(255,255,255,0.15)", borderRadius: "4px", overflow: "hidden" }}>
        <div style={{
          height: "100%",
          width: `${Math.min((passo / total) * 100, 100)}%`,
          background: "var(--dourado)",
          borderRadius: "4px",
          transition: "width 0.5s ease",
        }} />
      </div>
    </div>
  );
}

// ── Componente principal ───────────────────────────────────────────────────

export default function OnboardingScreen() {
  const userId     = TokenStorage.getUserId();
  const { logout } = useAuth();

  const [historico,         setHistorico]         = useState([]);
  const [currentPromptText, setCurrentPromptText] = useState("");
  const [perguntaOriginal,  setPerguntaOriginal]  = useState("");
  const [transcricao,       setTranscricao]       = useState("");
  const [fase,              setFase]              = useState("iniciando");
  const [passoAtual,        setPassoAtual]        = useState(0);

  const mediaRecRef    = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef       = useRef(null);
  const iniciouRef     = useRef(false);

  // ── TTS ────────────────────────────────────────────────────────────────

  const sintetizar = async (texto) => {
    try {
      const res = await fetch(`${AUDIO}/sintetizar`, {
        method:  "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${TokenStorage.getAccess()}` },
        body: JSON.stringify({ texto, voz: "pt-PT-RaquelNeural", streaming: false }),
      });
      if (!res.ok) return null;
      return URL.createObjectURL(await res.blob());
    } catch { return null; }
  };

  // ── Typewriter sincronizado ────────────────────────────────────────────

  const tocarComTypewriter = (texto, audioUrl) => {
    return new Promise((resolve) => {
      setCurrentPromptText("");
      if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }

      if (!audioUrl || !texto) {
        setCurrentPromptText(texto || "");
        resolve();
        return;
      }

      const audio = new Audio(audioUrl);
      let pos = 0;

      const fallback = () => {
        if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
        setCurrentPromptText(texto);
        resolve();
      };

      audio.addEventListener("canplaythrough", () => {
        const duracaoMs = (audio.duration || 5) * 1000;
        const tickMs    = texto.length > 0 ? Math.max(16, (duracaoMs - 200) / texto.length) : 50;

        timerRef.current = setInterval(() => {
          pos = Math.min(pos + 1, texto.length);
          setCurrentPromptText(texto.slice(0, pos));
          if (pos >= texto.length) { clearInterval(timerRef.current); timerRef.current = null; }
        }, tickMs);

        audio.play().catch(fallback);
      }, { once: true });

      audio.addEventListener("ended",  fallback, { once: true });
      audio.addEventListener("error",  fallback, { once: true });
      setTimeout(fallback, 15000);
      audio.load();
    });
  };

  // ── Turno principal ────────────────────────────────────────────────────

  const turno = async (mensagem, hist) => {
    setFase("processando");
    try {
      const res = await fetch(`${CHAT_API}/onboarding`, {
        method:  "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${TokenStorage.getAccess()}` },
        body: JSON.stringify({ user_id: userId, mensagem, historico: hist }),
      });
      if (!res.ok) throw new Error("Erro no servidor.");

      const data = await res.json();
      setHistorico(data.historico_atualizado);

      // Avançar barra de progresso com cada turno (máx 5)
      if (mensagem) setPassoAtual(p => Math.min(p + 1, 5));

      const pergunta = data.pergunta || "";
      setPerguntaOriginal(pergunta);
      setFase("ia_a_falar");
      const audioUrl = await sintetizar(pergunta);
      await tocarComTypewriter(pergunta, audioUrl);

      if (data.onboarding_completo) {
        setFase("completo");
        setPassoAtual(5);
        setTimeout(() => window.location.reload(), 1500);
        return;
      }
      setFase("aguardar_mic");
    } catch {
      setCurrentPromptText("Ocorreu um problema de ligação. Tente novamente.");
      setFase("erro");
    }
  };

  useEffect(() => {
    if (iniciouRef.current) return;
    iniciouRef.current = true;
    turno("", []);
  }, []);

  // ── Loop empático ──────────────────────────────────────────────────────

  const pedirRepeticaoEmpatica = async () => {
    setFase("ia_a_falar");
    try {
      const res = await fetch(`${CHAT_API}/reformular`, {
        method:  "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${TokenStorage.getAccess()}` },
        body: JSON.stringify({ ultima_frase: perguntaOriginal }),
      });
      const data = res.ok ? await res.json() : null;
      const fraseReformulada = data?.reformulada || "Peço desculpa, não consegui ouvir. Pode repetir?";
      const audioUrl = await sintetizar(fraseReformulada);
      await tocarComTypewriter(fraseReformulada, audioUrl);
    } catch { /* fallback silencioso */ }
    setFase("aguardar_mic");
  };

  // ── STT ────────────────────────────────────────────────────────────────

  const transcrever = async (audioBytes) => {
    const form = new FormData();
    form.append("audio", new Blob([audioBytes], { type: "audio/webm" }), "resposta.webm");
    const res = await fetch(`${AUDIO}/transcrever`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${TokenStorage.getAccess()}` },
      body: form,
    });
    if (!res.ok) throw new Error("Erro na transcrição.");
    return (await res.json()).texto;
  };

  // ── Gravação ───────────────────────────────────────────────────────────

  const iniciarGravacao = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec    = new MediaRecorder(stream, { mimeType: "audio/webm" });
      audioChunksRef.current = [];

      rec.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };

      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const duracaoMs  = Date.now() - (mediaRecRef.current._inicio || Date.now());
        const totalBytes = audioChunksRef.current.reduce((a, b) => a + b.size, 0);

        if (duracaoMs < 1500 || totalBytes < 4000) {
          await pedirRepeticaoEmpatica();
          return;
        }

        setFase("transcrevendo");
        try {
          const buf   = await new Blob(audioChunksRef.current).arrayBuffer();
          const texto = await transcrever(buf);
          if (isAlucinacao(texto)) { await pedirRepeticaoEmpatica(); return; }
          setTranscricao(texto);
          await turno(texto, historico);
        } catch {
          await pedirRepeticaoEmpatica();
        }
      };

      mediaRecRef.current = rec;
      mediaRecRef.current._inicio = Date.now();
      rec.start();
      setFase("gravando");
    } catch {
      setCurrentPromptText("Não foi possível aceder ao microfone. Verifique as permissões.");
      setFase("aguardar_mic");
    }
  };

  const pararGravacao = () => mediaRecRef.current?.stop();

  // ── Config por fase ────────────────────────────────────────────────────

  const btnConfig = {
    iniciando:     { ativo: false, label: "Um momento..." },
    ia_a_falar:    { ativo: false, label: "A Raquel está a falar..." },
    aguardar_mic:  { ativo: true,  label: "Prima para responder" },
    gravando:      { ativo: true,  label: "A gravar — prima para parar" },
    transcrevendo: { ativo: false, label: "A transcrever..." },
    processando:   { ativo: false, label: "A processar..." },
    completo:      { ativo: false, label: "Concluído" },
    erro:          { ativo: true,  label: "Tentar novamente" },
  };

  const cfg     = btnConfig[fase] || btnConfig.iniciando;
  const aGravar = fase === "gravando";

  // ── Ecrã de conclusão ──────────────────────────────────────────────────

  if (fase === "completo") return (
    <div style={{
      minHeight: "100dvh",
      background: "var(--creme)",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "2rem",
      textAlign: "center",
    }} className="animate-fade-in">
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />
      <div style={{ fontSize: "3.5rem", marginBottom: "1.5rem" }}>✨</div>
      <div className="linha-dourada" style={{ width: "48px", margin: "0 auto 1.5rem" }} />
      <h2 style={{ color: "var(--azul)", fontFamily: "var(--font-display)", fontSize: "var(--text-4xl)", fontWeight: 500, margin: "0 0 1rem" }}>
        Muito obrigado
      </h2>
      <p style={{ color: "var(--cinza)", fontSize: "var(--text-xl)", lineHeight: 1.6, maxWidth: "320px", marginBottom: "2rem" }}>
        O seu perfil foi criado. A preparar a sua experiência...
      </p>
      <div style={{
        width: "36px", height: "36px",
        border: "3px solid var(--azul)",
        borderTopColor: "transparent",
        borderRadius: "50%",
        animation: "spin 1s linear infinite",
      }} />
    </div>
  );

  // ── Ecrã principal ─────────────────────────────────────────────────────

  return (
    <div style={{ minHeight: "100dvh", background: "var(--creme)", display: "flex", flexDirection: "column", fontFamily: "var(--font-serif)" }}>
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />

      {/* Header com progresso */}
      <header className="app-header" style={{ flexDirection: "column", alignItems: "stretch", padding: "1rem 1.25rem 0" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.875rem" }}>
          <div>
            <span style={{ color: "white", fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 500 }}>
              Memórias Vivas
            </span>
            <div className="linha-dourada" style={{ width: "20px", marginTop: "3px" }} />
          </div>
          <button
            onClick={logout}
            style={{ background: "none", border: "none", color: "var(--azul-claro)", fontSize: "var(--text-sm)", fontFamily: "var(--font-serif)", cursor: "pointer", padding: "0.5rem" }}
          >
            Sair
          </button>
        </div>
        <BarraProgresso passo={passoAtual} total={5} />
      </header>

      {/* Conteúdo principal */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "space-between", padding: "2rem 1.5rem 2rem" }}>

        {/* Área de texto da Raquel */}
        <div style={{ width: "100%", maxWidth: "480px", flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>

          {currentPromptText ? (
            <div className="animate-fade-in">
              {/* Indicador "Raquel a falar" */}
              {fase === "ia_a_falar" && (
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "1.25rem" }}>
                  <div style={{ display: "flex", gap: "5px" }}>
                    {[0,1,2].map(i => (
                      <div key={i} style={{
                        width: "7px", height: "7px",
                        background: "var(--dourado)",
                        borderRadius: "50%",
                        animation: `bounce3 1.2s ease-in-out infinite`,
                        animationDelay: `${i * 180}ms`,
                      }} />
                    ))}
                  </div>
                  <span style={{ color: "var(--cinza)", fontSize: "var(--text-sm)", letterSpacing: "0.06em" }}>
                    Raquel
                  </span>
                </div>
              )}

              <div className="linha-dourada" style={{ width: "28px", marginBottom: "1.25rem" }} />
              <p style={{
                color: "var(--azul)",
                fontFamily: "var(--font-display)",
                fontSize: "clamp(1.5rem, 5vw, 2.25rem)",
                fontWeight: 500,
                lineHeight: 1.45,
                margin: 0,
              }}>
                {currentPromptText}
              </p>
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
              <div style={{
                width: "32px", height: "32px",
                border: "2.5px solid var(--azul)",
                borderTopColor: "transparent",
                borderRadius: "50%",
                animation: "spin 1s linear infinite",
              }} />
              <p style={{ color: "var(--cinza)", fontSize: "var(--text-xl)" }}>Um momento...</p>
            </div>
          )}
        </div>

        {/* Resposta do utilizador */}
        {transcricao && !["gravando","transcrevendo","ia_a_falar"].includes(fase) && (
          <div style={{
            width: "100%",
            maxWidth: "480px",
            background: "white",
            borderLeft: "3px solid var(--dourado)",
            borderRadius: "0 var(--radius-sm) var(--radius-sm) 0",
            padding: "1rem 1.25rem",
            marginBottom: "1.5rem",
          }} className="animate-slide-up">
            <p style={{ color: "var(--cinza)", fontSize: "var(--text-xs)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "0.4rem" }}>
              A sua resposta
            </p>
            <p style={{ color: "var(--texto-suave)", fontSize: "var(--text-lg)", margin: 0, lineHeight: 1.5 }}>
              {transcricao}
            </p>
          </div>
        )}

        {/* Botão microfone */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem", width: "100%", maxWidth: "480px" }}>
          <button
            id="btn-mic-onboarding"
            onClick={aGravar ? pararGravacao : iniciarGravacao}
            disabled={!cfg.ativo}
            aria-label={cfg.label}
            className={`mic-btn ${aGravar ? "gravando" : cfg.ativo ? "idle" : "disabled"}`}
            style={{ width: "140px", height: "140px" }}
          >
            {aGravar ? <IconStop /> : <IconMic />}
          </button>
          <p className="mic-label" style={{ fontSize: "var(--text-lg)" }}>{cfg.label}</p>
        </div>

      </main>
    </div>
  );
}