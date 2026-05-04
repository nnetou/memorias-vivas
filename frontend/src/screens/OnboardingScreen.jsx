/**
 * screens/OnboardingScreen.jsx — Onboarding por voz (1.º acesso).
 *
 * Fluxo:
 *  1. Backend devolve pergunta (texto)
 *  2. TTS sintetiza e toca automaticamente
 *  3. Utilizador prime microfone e responde a falar
 *  4. STT transcreve a resposta
 *  5. Transcrição enviada ao backend → próxima pergunta
 *  6. Repetir até onboarding_completo: true
 */

import { useState, useEffect, useRef } from "react";
import { TokenStorage } from "../api/client";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const API  = BASE + "/api/v1/chat";
const AUDIO_API = BASE + "/api/v1/audio";

// ---------------------------------------------------------------------------
// Ícones SVG
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
  <svg width="36" height="36" viewBox="0 0 24 24" fill="currentColor">
    <rect x="6" y="6" width="12" height="12" rx="2"/>
  </svg>
);

const IconVolume = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
    <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
  </svg>
);

// ---------------------------------------------------------------------------
// Helpers de áudio
// ---------------------------------------------------------------------------

async function sintetizarETocar(texto) {
  const res = await fetch(`${AUDIO_API}/sintetizar`, {
    method:  "POST",
    headers: {
      "Content-Type":  "application/json",
      "Authorization": `Bearer ${TokenStorage.getAccess()}`,
    },
    body: JSON.stringify({ texto, voz: "pt-PT-RaquelNeural", streaming: false }),
  });
  if (!res.ok) return;
  const blob = await res.blob();
  const url  = URL.createObjectURL(blob);
  return new Promise((resolve) => {
    const audio = new Audio(url);
    audio.onended = resolve;
    audio.onerror = resolve;
    audio.play();
  });
}

async function transcreverAudio(audioBytes, filename = "resposta.webm") {
  const form = new FormData();
  form.append("audio", new Blob([audioBytes], { type: "audio/webm" }), filename);
  const res = await fetch(`${AUDIO_API}/transcrever`, {
    method:  "POST",
    headers: { "Authorization": `Bearer ${TokenStorage.getAccess()}` },
    body:    form,
  });
  if (!res.ok) throw new Error("Erro na transcrição.");
  const data = await res.json();
  return data.texto;
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export default function OnboardingScreen() {
  const userId = TokenStorage.getUserId();

  const [historico,  setHistorico]  = useState([]);
  const [pergunta,   setPergunta]   = useState("");
  const [transcricao, setTranscricao] = useState("");
  const [progresso,  setProgresso]  = useState(0);
  const [fase, setFase] = useState("carregando");
  // fases: carregando | ia_a_falar | aguardar_mic | gravando | transcrevendo | enviando | completo | erro

  const [msgErro, setMsgErro] = useState("");
  const mediaRecRef    = useRef(null);
  const audioChunksRef = useRef([]);

  // ---------------------------------------------------------------------------
  // Chamar backend de onboarding
  // ---------------------------------------------------------------------------

  const chamarOnboarding = async (mensagem, hist) => {
    setFase("carregando");
    setMsgErro("");
    try {
      const res = await fetch(`${API}/onboarding`, {
        method:  "POST",
        headers: {
          "Content-Type":  "application/json",
          "Authorization": `Bearer ${TokenStorage.getAccess()}`,
        },
        body: JSON.stringify({ user_id: userId, mensagem, historico: hist }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Erro no servidor.");
      }

      const data = await res.json();
      setHistorico(data.historico_atualizado);

      if (data.onboarding_completo) {
        setFase("completo");
        // Sintetizar mensagem de conclusão
        await sintetizarETocar("Muito obrigado. O seu perfil foi criado com sucesso. Já pode começar a conversar!");
        setTimeout(() => window.location.reload(), 1500);
        return;
      }

      if (data.pergunta) {
        setPergunta(data.pergunta);
        const n = (data.historico_atualizado || [])
          .filter(m => m.role === "assistant" && m.content !== data.pergunta).length;
        setProgresso(Math.min(n, 5));

        // Sintetizar a pergunta em voz
        setFase("ia_a_falar");
        await sintetizarETocar(data.pergunta);
        setFase("aguardar_mic");
      }

    } catch (err) {
      setMsgErro(err.message || "Erro de ligação.");
      setFase("erro");
    }
  };

  // Arrancar no mount
  useEffect(() => { chamarOnboarding("", []); }, []);

  // ---------------------------------------------------------------------------
  // Gravação de voz
  // ---------------------------------------------------------------------------

  const iniciarGravacao = async () => {
    setMsgErro("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream, { mimeType: "audio/webm" });
      audioChunksRef.current = [];

      rec.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };

      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        setFase("transcrevendo");
        try {
          const buf  = await new Blob(audioChunksRef.current, { type: "audio/webm" }).arrayBuffer();
          const texto = await transcreverAudio(buf);
          setTranscricao(texto);
          setFase("enviando");
          await chamarOnboarding(texto, historico);
        } catch (err) {
          setMsgErro("Não consegui ouvir bem. Pode repetir?");
          await sintetizarETocar("Não consegui ouvir bem. Pode repetir, por favor?");
          setFase("aguardar_mic");
        }
      };

      rec.start();
      mediaRecRef.current = rec;
      setFase("gravando");
    } catch {
      setMsgErro("Não foi possível aceder ao microfone. Verifique as permissões.");
      setFase("aguardar_mic");
    }
  };

  const pararGravacao = () => {
    mediaRecRef.current?.stop();
  };

  // ---------------------------------------------------------------------------
  // Labels e estilos por fase
  // ---------------------------------------------------------------------------

  const faseConfig = {
    carregando:    { label: "Um momento...",                    btnAtivo: false },
    ia_a_falar:    { label: "A Raquel está a falar...",         btnAtivo: false },
    aguardar_mic:  { label: "Prima para responder",             btnAtivo: true  },
    gravando:      { label: "A gravar — prima para parar",      btnAtivo: true  },
    transcrevendo: { label: "A transcrever a sua resposta...",  btnAtivo: false },
    enviando:      { label: "A processar...",                   btnAtivo: false },
    completo:      { label: "Concluído!",                       btnAtivo: false },
    erro:          { label: "Tente novamente",                  btnAtivo: true  },
  };

  const cfg = faseConfig[fase] || faseConfig.carregando;
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
        <p className="text-[#888] text-xl leading-relaxed">
          O seu perfil foi criado. A preparar a sua experiência...
        </p>
        <div className="mt-10 flex justify-center">
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

      {/* Header */}
      <header className="bg-[#1e3a5f] px-8 py-5">
        <span className="text-white" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "1.5rem" }}>
          Memórias Vivas
        </span>
        <div className="w-6 h-[1px] bg-[#c9a84c] mt-1" />
      </header>

      {/* Barra de progresso */}
      <div className="w-full h-1 bg-[#e8e0d5]">
        <div className="h-1 bg-[#c9a84c] transition-all duration-700"
          style={{ width: `${(progresso / 5) * 100}%` }} />
      </div>

      {/* Conteúdo */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-lg flex flex-col items-center">

          {/* Progresso */}
          <p className="text-[#aaa] text-sm tracking-widest uppercase mb-8 self-start">
            {progresso > 0 ? `Pergunta ${progresso} de 5` : "Apresentação"}
          </p>

          {/* Pergunta em destaque */}
          {pergunta && (
            <div className="w-full mb-12">
              <div className="w-8 h-[2px] bg-[#c9a84c] mb-6" />
              <div className="flex items-start gap-3">
                <div className="text-[#c9a84c] mt-1 flex-shrink-0">
                  <IconVolume />
                </div>
                <p className="text-[#1e3a5f] leading-relaxed"
                  style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "1.9rem", fontWeight: 500 }}>
                  {pergunta}
                </p>
              </div>
            </div>
          )}

          {/* Transcrição da última resposta */}
          {transcricao && (fase === "enviando" || fase === "carregando" || fase === "ia_a_falar" || fase === "aguardar_mic") && (
            <div className="w-full mb-8 px-5 py-4 bg-white border border-[#e8e0d5]">
              <p className="text-[#aaa] text-sm tracking-widest uppercase mb-2">A sua resposta</p>
              <p className="text-[#444] text-xl leading-relaxed">{transcricao}</p>
            </div>
          )}

          {/* Erro */}
          {msgErro && (
            <p className="text-red-600 text-lg border border-red-200 bg-red-50 px-5 py-3 mb-8 w-full">
              {msgErro}
            </p>
          )}

          {/* Botão de microfone */}
          <div className="flex flex-col items-center gap-5 mt-4">
            <button
              onClick={aGravar ? pararGravacao : iniciarGravacao}
              disabled={!cfg.btnAtivo}
              aria-label={cfg.label}
              className={[
                "w-28 h-28 rounded-full flex items-center justify-center text-white",
                "transition-all duration-300 active:scale-95",
                "disabled:opacity-40 disabled:cursor-not-allowed",
                aGravar
                  ? "bg-[#c0392b] shadow-[0_8px_32px_rgba(192,57,43,0.4)] scale-110 animate-pulse"
                  : cfg.btnAtivo
                    ? "bg-[#1e3a5f] shadow-[0_8px_32px_rgba(30,58,95,0.3)] hover:bg-[#163050]"
                    : "bg-[#c9a84c] shadow-[0_4px_16px_rgba(201,168,76,0.3)]",
              ].join(" ")}
            >
              {aGravar ? <IconStop /> : <IconMic />}
            </button>

            <p className="text-[#888] text-lg tracking-wide text-center">{cfg.label}</p>

            {/* Indicador de fase a carregar */}
            {!cfg.btnAtivo && fase !== "completo" && (
              <div className="w-6 h-6 border-2 border-[#1e3a5f] border-t-transparent rounded-full animate-spin" />
            )}
          </div>

        </div>
      </main>
    </div>
  );
}