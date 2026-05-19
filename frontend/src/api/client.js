/**
 * api/client.js — Cliente HTTP centralizado com injeção automática de JWT.
 *
 * Todas as chamadas à API passam por aqui.
 * O token é lido do localStorage e injetado no header Authorization.
 * Em caso de 401, limpa a sessão e redireciona para o login.
 */

const BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;
const CHAT_URL = `${BASE_URL}/api/v1/chat`;
const AUTH_URL = `${BASE_URL}/api/v1/auth`;

// ---------------------------------------------------------------------------
// Sanitização de erros — nunca expor detalhes internos ao utilizador
// ---------------------------------------------------------------------------

const MENSAGENS_GENERICAS = {
  400: "Pedido inválido. Verifique os dados introduzidos.",
  401: "Sessão expirada. Por favor inicie sessão novamente.",
  403: "Não tem permissão para realizar esta ação.",
  404: "Recurso não encontrado.",
  409: "Já existe uma conta com este email.",
  413: "O ficheiro enviado é demasiado grande.",
  415: "Formato de ficheiro não suportado.",
  422: null,
  429: "Demasiados pedidos. Aguarde um momento e tente novamente.",
  500: "Ocorreu um erro interno. A nossa equipa foi notificada.",
  502: "O assistente não está disponível neste momento. Tente novamente.",
  503: "Serviço temporariamente indisponível. Tente novamente em breves instantes.",
};

async function parsearErro(res) {
  let body = {};
  try { body = await res.json(); } catch { /* body não é JSON */ }

  const detalhe = body.detail;

  // Erros de validação Pydantic (array)
  if (Array.isArray(detalhe)) {
    return detalhe.map(e => e.msg?.replace("Value error, ", "") || "Erro de validação").join(" ");
  }

  // Mensagem genérica por código HTTP
  const generica = MENSAGENS_GENERICAS[res.status];
  if (generica) return generica;

  // 422 com string simples
  if (res.status === 422 && typeof detalhe === "string") return detalhe;

  return "Ocorreu um erro inesperado. Por favor tente novamente mais tarde.";
}

// ---------------------------------------------------------------------------
// Gestão de tokens
// ---------------------------------------------------------------------------

export const TokenStorage = {
  getAccess: () => localStorage.getItem("mv_access_token"),
  getRefresh: () => localStorage.getItem("mv_refresh_token"),
  getUserId: () => localStorage.getItem("mv_user_id"),
  getRole: () => localStorage.getItem("mv_role"),

  save: ({ access_token, refresh_token, user_id, role }) => {
    localStorage.setItem("mv_access_token", access_token);
    localStorage.setItem("mv_refresh_token", refresh_token);
    localStorage.setItem("mv_user_id", user_id);
    localStorage.setItem("mv_role", role);
  },

  clear: () => {
    [
      "mv_access_token",
      "mv_refresh_token",
      "mv_user_id",
      "mv_role",
      "mv_session_id",
      "mv_onboarding_done",
    ].forEach((k) => localStorage.removeItem(k));
  },
};

// ---------------------------------------------------------------------------
// Fetch base com JWT automático
// ---------------------------------------------------------------------------

async function apiFetch(url, options = {}) {
  const token = TokenStorage.getAccess();

  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(url, { ...options, headers });

  // Token expirado — tenta refresh uma vez
  if (res.status === 401 && TokenStorage.getRefresh()) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      const retryHeaders = {
        ...headers,
        Authorization: `Bearer ${TokenStorage.getAccess()}`,
      };
      return fetch(url, { ...options, headers: retryHeaders });
    } else {
      // Refresh falhou — limpar sessão
      TokenStorage.clear();
      window.location.href = "/";
      return res;
    }
  }

  return res;
}

async function tryRefresh() {
  const refresh_token = TokenStorage.getRefresh();
  if (!refresh_token) return false;

  try {
    const res = await fetch(`${AUTH_URL}/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token }),
    });

    if (!res.ok) return false;
    const data = await res.json();
    TokenStorage.save(data);
    return true;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Auth endpoints
// ---------------------------------------------------------------------------

export const authApi = {
  login: async (email, password) => {
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch(`${AUTH_URL}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) throw new Error(await parsearErro(res));
    return res.json();
  },

  registar: async (email, password, nome, role = "idoso") => {
    const res = await fetch(`${AUTH_URL}/registar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, nome, role }),
    });
    if (!res.ok) throw new Error(await parsearErro(res));
    return res.json();
  },

  me: async () => {
    const res = await apiFetch(`${AUTH_URL}/me`);
    if (!res.ok) throw new Error(await parsearErro(res));
    return res.json();
  },

  alterarPassword: async (password_atual, nova_password) => {
    const res = await apiFetch(`${AUTH_URL}/alterar-password`, {
      method: "POST",
      body: JSON.stringify({ password_atual, nova_password }),
    });
    if (!res.ok) throw new Error(await parsearErro(res));
    return res.json();
  },

  recuperarPassword: async (email) => {
    const res = await fetch(`${AUTH_URL}/recuperar-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    return res.json();
  },
};

// ---------------------------------------------------------------------------
// Consentimento endpoints
// ---------------------------------------------------------------------------

export const consentimentoApi = {
  registar: async ({
    autoriza_gravacao_voz,
    autoriza_processamento_ia,
    autoriza_geracao_video,
  }) => {
    const user_id = TokenStorage.getUserId();
    const res = await apiFetch(`${BASE_URL}/api/v1/consentimento`, {
      method: "POST",
      body: JSON.stringify({
        user_id,
        autoriza_gravacao_voz,
        autoriza_processamento_ia,
        autoriza_geracao_video,
      }),
    });
    if (!res.ok) throw new Error(await parsearErro(res));
    return res.json();
  },
};

// ---------------------------------------------------------------------------
// Chat endpoints
// ---------------------------------------------------------------------------

export const chatApi = {
  conversaPersonalizada: async ({ mensagem, tema, session_id }) => {
    const user_id = TokenStorage.getUserId();
    const res = await apiFetch(`${CHAT_URL}/conversa/personalizada`, {
      method: "POST",
      body: JSON.stringify({
        user_id,
        mensagem,
        tema,
        session_id,
        historico: null,
      }),
    });
    if (!res.ok) throw new Error(await parsearErro(res));
    return res.json();
  },

  encerrarSessao: async ({ session_id, tema, historico_sessao }) => {
    const user_id = TokenStorage.getUserId();
    const res = await apiFetch(`${CHAT_URL}/sessao/encerrar`, {
      method: "POST",
      body: JSON.stringify({ user_id, session_id, tema, historico_sessao }),
    });
    return res.json();
  },
};

// ---------------------------------------------------------------------------
// Artefactos endpoints (Epic 6)
// ---------------------------------------------------------------------------

const ARTEFACTOS_URL = `${BASE_URL}/api/v1/artefactos`;

export const artefactosApi = {
  listar: async () => {
    const user_id = TokenStorage.getUserId();
    const res = await apiFetch(`${ARTEFACTOS_URL}/?user_id=${user_id}`);
    if (!res.ok) throw new Error("Erro ao listar artefactos.");
    return res.json();
  },

  gerarLivro: async () => {
    const user_id = TokenStorage.getUserId();
    const res = await apiFetch(`${ARTEFACTOS_URL}/livro-memorias`, {
      method: "POST",
      body: JSON.stringify({ user_id }),
    });
    if (!res.ok) throw new Error(await parsearErro(res));
    return res.json();
  },

  gerarTimeline: async () => {
    const user_id = TokenStorage.getUserId();
    const res = await apiFetch(`${ARTEFACTOS_URL}/timeline`, {
      method: "POST",
      body: JSON.stringify({ user_id }),
    });
    if (!res.ok) throw new Error(await parsearErro(res));
    return res.json();
  },

  gerarCartoes: async () => {
    const user_id = TokenStorage.getUserId();
    const res = await apiFetch(`${ARTEFACTOS_URL}/cartoes`, {
      method: "POST",
      body: JSON.stringify({ user_id }),
    });
    if (!res.ok) throw new Error(await parsearErro(res));
    return res.json();
  },

  gerarVideo: async () => {
    const user_id = TokenStorage.getUserId();
    const res = await apiFetch(`${ARTEFACTOS_URL}/video`, {
      method: "POST",
      body: JSON.stringify({ user_id }),
    });
    if (!res.ok) throw new Error(await parsearErro(res));
    return res.json();
  },

  downloadUrl: (artefactoId) => `${ARTEFACTOS_URL}/${artefactoId}/download`,
};

export { BASE_URL, AUTH_URL, CHAT_URL, ARTEFACTOS_URL };