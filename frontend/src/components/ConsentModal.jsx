/**
 * components/ConsentModal.jsx — Modal de consentimento RGPD (Epic 7.2).
 *
 * Aparece no primeiro login, antes de qualquer recolha de dados.
 * Comunicar com o backend via POST /api/v1/consentimento.
 *
 * Requisitos RGPD:
 *  - Consentimento explícito por categoria (voz, IA, vídeo)
 *  - Linguagem simples, sem jargão jurídico
 *  - Não pode avançar sem aceitar os mínimos obrigatórios
 *  - Pode rever e alterar mais tarde nas Definições
 */

import { useState } from "react";
import { consentimentoApi } from "../api/client";

// ---------------------------------------------------------------------------
// Categorias de consentimento
// ---------------------------------------------------------------------------
const CATEGORIAS = [
  {
    id:          "autoriza_processamento_ia",
    obrigatorio: true,
    emoji:       "🤖",
    titulo:      "Processamento por Inteligência Artificial",
    descricao:   "As suas conversas são processadas por sistemas de IA para gerar respostas personalizadas e guardar as suas memórias. Este consentimento é obrigatório para usar o serviço.",
  },
  {
    id:          "autoriza_gravacao_voz",
    obrigatorio: false,
    emoji:       "🎤",
    titulo:      "Gravação de Voz",
    descricao:   "Permite utilizar o microfone para falar diretamente com o assistente. A voz é convertida em texto e não é guardada permanentemente.",
  },
  {
    id:          "autoriza_geracao_video",
    obrigatorio: false,
    emoji:       "🎬",
    titulo:      "Geração de Vídeos com as suas Memórias",
    descricao:   "No futuro, poderemos criar vídeos ilustrativos com as suas histórias. As suas memórias só serão usadas com esta autorização explícita.",
  },
];

export default function ConsentModal({ onAceitar }) {
  const [consentimentos, setConsentimentos] = useState({
    autoriza_processamento_ia: false,
    autoriza_gravacao_voz:     false,
    autoriza_geracao_video:    false,
  });
  const [loading, setLoading] = useState(false);
  const [erro, setErro]       = useState("");

  const toggle = (id, obrigatorio) => {
    if (obrigatorio && consentimentos[id]) return; // obrigatório não pode desmarcar
    setConsentimentos(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const podeAvancar = consentimentos.autoriza_processamento_ia;

  const handleAceitar = async () => {
    if (!podeAvancar) {
      setErro("O consentimento de Inteligência Artificial é obrigatório para usar o serviço.");
      return;
    }
    setLoading(true);
    setErro("");
    try {
      await consentimentoApi.registar(consentimentos);
      onAceitar(consentimentos);
    } catch (err) {
      setErro(err.message || "Não foi possível guardar as suas preferências. Tente novamente.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Fonte Lora */}
      <link
        href="https://fonts.googleapis.com/css2?family=Lora:wght@400;600;700&display=swap"
        rel="stylesheet"
      />

      {/* Overlay */}
      <div
        className="fixed inset-0 bg-[#1e3a5f]/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="consent-title"
        style={{ fontFamily: "'Lora', serif" }}
      >
        <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">

          {/* Cabeçalho */}
          <div className="bg-[#1e3a5f] rounded-t-3xl px-8 py-8 text-center">
            <div className="text-5xl mb-3">🔒</div>
            <h2 id="consent-title" className="text-white text-2xl font-bold">
              A sua privacidade é importante
            </h2>
            <p className="text-[#a8c4e0] text-lg mt-2 leading-relaxed">
              Antes de começar, precisamos da sua autorização para algumas funcionalidades.
            </p>
          </div>

          {/* Corpo */}
          <div className="px-8 py-6">
            <p className="text-[#444] text-lg leading-relaxed mb-6">
              O <strong>Memórias Vivas</strong> respeita a sua privacidade conforme o RGPD.
              Escolha o que nos autoriza a fazer com os seus dados:
            </p>

            {/* Categorias */}
            <div className="flex flex-col gap-4 mb-6">
              {CATEGORIAS.map(cat => (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => toggle(cat.id, cat.obrigatorio)}
                  className={[
                    "flex items-start gap-4 p-5 rounded-2xl border-2 text-left",
                    "transition-all duration-200 w-full",
                    consentimentos[cat.id]
                      ? "border-[#1e3a5f] bg-[#e8f0f8]"
                      : "border-[#d0dae8] bg-[#FAF7F2] hover:border-[#a8c4e0]",
                  ].join(" ")}
                  aria-pressed={consentimentos[cat.id]}
                >
                  {/* Checkbox visual */}
                  <div className={[
                    "flex-shrink-0 w-7 h-7 rounded-lg border-2 mt-0.5",
                    "flex items-center justify-center transition-colors",
                    consentimentos[cat.id]
                      ? "bg-[#1e3a5f] border-[#1e3a5f]"
                      : "bg-white border-[#9ab0c8]",
                  ].join(" ")}>
                    {consentimentos[cat.id] && (
                      <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </div>

                  {/* Conteúdo */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-2xl">{cat.emoji}</span>
                      <span className="text-[#1e3a5f] font-semibold text-lg leading-tight">
                        {cat.titulo}
                      </span>
                      {cat.obrigatorio && (
                        <span className="text-xs font-bold text-white bg-[#1e3a5f] px-2 py-0.5 rounded-full ml-1">
                          Obrigatório
                        </span>
                      )}
                    </div>
                    <p className="text-[#555] text-base leading-relaxed">
                      {cat.descricao}
                    </p>
                  </div>
                </button>
              ))}
            </div>

            {/* Nota legal */}
            <div className="bg-[#f0f4f8] rounded-2xl px-5 py-4 mb-6">
              <p className="text-[#555] text-base leading-relaxed">
                📋 Pode alterar estas preferências a qualquer momento nas <strong>Definições de Privacidade</strong>.
                Os seus dados nunca serão partilhados com terceiros para fins comerciais.
              </p>
            </div>

            {/* Erro */}
            {erro && (
              <p className="text-red-600 text-lg mb-4 px-1" role="alert">⚠ {erro}</p>
            )}

            {/* Botão confirmar */}
            <button
              type="button"
              onClick={handleAceitar}
              disabled={!podeAvancar || loading}
              className={[
                "w-full py-5 rounded-2xl text-xl font-bold",
                "transition-all duration-150 min-h-[56px]",
                podeAvancar
                  ? "bg-[#1e3a5f] text-white hover:bg-[#163050] active:scale-[0.98]"
                  : "bg-[#d0dae8] text-[#888] cursor-not-allowed",
              ].join(" ")}
            >
              {loading ? "A guardar..." : "Confirmar e continuar"}
            </button>

            {!podeAvancar && (
              <p className="text-center text-base text-[#888] mt-3">
                Active o consentimento obrigatório para continuar.
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  );
}