/**
 * screens/OnboardingScreen.jsx — Onboarding conversacional por voz.
 *
 * VUI empático com loop contínuo:
 *  - currentPromptText: estado único que controla o texto visível no ecrã
 *  - Quando silêncio/alucinação: combina frase de transição + pergunta original
 *  - Texto e áudio sincronizados — o ecrã mostra exatamente o que a Raquel diz
 *  - Microfone reativa automaticamente após cada resposta da Raquel
 */

import { useState, useEffect, useRef } from "react";
import { TokenStorage } from "../api/client";
import { useAuth } from "../contexts/AuthContext";

const BASE     = import.meta.env.VITE_API_URL || "http://localhost:8000";
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

// ---------------------------------------------------------------------------
// Ícones
// ---------------------------------------------------------------------------
const IconMic = () => (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
    <line x1="12" y1="19" x2="12" y2="23"/>
    <line x1="8" y1="23" x2="16" y2="23"/>
  </svg>
);

const IconStop = () => (
  <svg width="34" height="34" viewBox="0 0 24 24" fill="currentColor">
    <rect x="6" y="6" width="12" height="12" rx="2"/>
  </svg>
);

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function OnboardingScreen() {
  const userId       = TokenStorage.getUserId();
  const { logout }   = useAuth();

  const [historico,        setHistorico]        = useState([]);
  const [currentPromptText, setCurrentPromptText] = useState(""); // texto visível — sempre igual ao que a Raquel diz
  const [perguntaOriginal,  setPerguntaOriginal]  = useState(""); // última pergunta válida do backend
  const [transcricao,       setTranscricao]       = useState("");
  const [fase,              setFase]              = useState("iniciando");

  const mediaRecRef    = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef       = useRef(null);
  const iniciouRef     = useRef(false);

  // ---------------------------------------------------------------------------
  // TTS — sintetiza e devolve URL
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // Typewriter sincronizado com o áudio
  // Atualiza currentPromptText ao ritmo do áudio
  // ---------------------------------------------------------------------------
  const tocarComTypewriter = (texto, audioUrl) => {
    return new Promise((resolve) => {
      setCurrentPromptText(""); // limpar antes de começar
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
      setTimeout(fallback, 15000); // safety timeout
      audio.load();
    });
  };

  // ---------------------------------------------------------------------------
  // Turno principal — backend → TTS → typewriter → microfone
  // ---------------------------------------------------------------------------
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

      const pergunta = data.pergunta || "";
      setPerguntaOriginal(pergunta);

      setFase("ia_a_falar");
      const audioUrl = await sintetizar(pergunta);
      await tocarComTypewriter(pergunta, audioUrl);

      if (data.onboarding_completo) {
        setFase("completo");
        setTimeout(() => window.location.reload(), 1500);
        return;
      }

      setFase("aguardar_mic");

    } catch (err) {
      setCurrentPromptText("Ocorreu um problema de ligação. Tente novamente.");
      setFase("erro");
    }
  };

  useEffect(() => {
    if (iniciouRef.current) return;
    iniciouRef.current = true;
    turno("", []);
  }, []);

  // ---------------------------------------------------------------------------
  // Loop empático — reformulação dinâmica via backend (llama3-8b)
  // ---------------------------------------------------------------------------
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
    } catch {
      // Fallback silencioso — só reativa o microfone
    }
    setFase("aguardar_mic");
  };

  // ---------------------------------------------------------------------------
  // Transcrição STT
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // Gravação
  // ---------------------------------------------------------------------------
  const iniciarGravacao = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec    = new MediaRecorder(stream, { mimeType: "audio/webm" });
      audioChunksRef.current = [];

      rec.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };

      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());

        // Verificar duração e tamanho mínimos
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

          if (isAlucinacao(texto)) {
            await pedirRepeticaoEmpatica();
            return;
          }

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

  // ---------------------------------------------------------------------------
  // Config por fase
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // Ecrã de conclusão
  // ---------------------------------------------------------------------------
  if (fase === "completo") return (
    <div className="min-h-screen bg-[#FAF7F2] flex items-center justify-center p-8">
      <div className="text-center max-w-md" style={{ fontFamily: "'Lora', serif" }}>
        <div className="w-16 h-[2px] bg-[#c9a84c] mx-auto mb-10" />
        <h2 className="text-[#1e3a5f] mb-4"
          style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "2.4rem", fontWeight: 500 }}>
          Muito obrigado
        </h2>
        <p className="text-[#888] text-xl leading-relaxed mb-10">
          O seu perfil foi criado. A preparar a sua experiência...
        </p>
        <div className="flex justify-center">
          <div className="w-8 h-8 border-2 border-[#1e3a5f] border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    </div>
  );

  // ---------------------------------------------------------------------------
  // Ecrã principal
  // ---------------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-[#FAF7F2] flex flex-col" style={{ fontFamily: "'Lora', serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap" rel="stylesheet" />

      <header className="bg-[#1e3a5f] px-8 py-5 flex items-center justify-between">
        <div>
          <span className="text-white" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "1.5rem" }}>
            Memórias Vivas
          </span>
          <div className="w-6 h-[1px] bg-[#c9a84c] mt-1" />
        </div>
        <button onClick={logout} className="text-[#7a9cbf] hover:text-white text-lg transition-colors tracking-wide">
          Sair
        </button>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-lg flex flex-col items-center">

          {/* Texto principal — espelho exacto do que a Raquel diz */}
          <div className="w-full mb-12 min-h-[120px]">
            {currentPromptText ? (
              <>
                <div className="w-8 h-[2px] bg-[#c9a84c] mb-6" />
                {fase === "ia_a_falar" && (
                  <div className="flex items-center gap-2 mb-4">
                    <div className="flex gap-1">
                      {[0,1,2].map(i => (
                        <div key={i} className="w-1.5 h-1.5 bg-[#c9a84c] rounded-full animate-bounce"
                          style={{ animationDelay: `${i*150}ms` }} />
                      ))}
                    </div>
                    <span className="text-[#aaa] text-sm tracking-wide">Raquel</span>
                  </div>
                )}
                <p className="text-[#1e3a5f] leading-relaxed"
                  style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "1.8rem", fontWeight: 500 }}>
                  {currentPromptText}
                </p>
              </>
            ) : (
              <div className="flex items-center gap-3 mt-8">
                <div className="w-7 h-7 border-2 border-[#1e3a5f] border-t-transparent rounded-full animate-spin" />
                <p className="text-[#aaa] text-xl">Um momento...</p>
              </div>
            )}
          </div>

          {/* Última resposta do utilizador */}
          {transcricao && !["gravando","transcrevendo","ia_a_falar"].includes(fase) && (
            <div className="w-full mb-8 px-5 py-4 bg-white border-l-2 border-[#c9a84c]">
              <p className="text-[#aaa] text-sm tracking-widest uppercase mb-2">A sua resposta</p>
              <p className="text-[#555] text-xl leading-relaxed">{transcricao}</p>
            </div>
          )}

          {/* Botão microfone */}
          <div className="flex flex-col items-center gap-5 mt-2">
            <button
              onClick={aGravar ? pararGravacao : iniciarGravacao}
              disabled={!cfg.ativo}
              aria-label={cfg.label}
              className={[
                "w-28 h-28 rounded-full flex items-center justify-center text-white",
                "transition-all duration-300 active:scale-95 disabled:cursor-not-allowed",
                aGravar
                  ? "bg-[#c0392b] scale-110 animate-pulse shadow-[0_8px_32px_rgba(192,57,43,0.4)]"
                  : cfg.ativo
                    ? "bg-[#1e3a5f] hover:bg-[#163050] shadow-[0_8px_32px_rgba(30,58,95,0.3)]"
                    : "bg-[#d0cac0]",
              ].join(" ")}
            >
              {aGravar ? <IconStop /> : <IconMic />}
            </button>
            <p className="text-[#888] text-lg tracking-wide">{cfg.label}</p>
          </div>

        </div>
      </main>
    </div>
  );
}