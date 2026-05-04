/**
 * screens/LoginScreen.jsx — Autenticação do Memórias Vivas.
 * Design: refinado, editorial, sem emojis. Tipografia Cormorant Garamond.
 * Painel esquerdo decorativo (azul naval) + formulário direito (marfim).
 */

import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { authApi, TokenStorage } from "../api/client";

export default function LoginScreen() {
  const { login } = useAuth();
  const [modo, setModo]         = useState("login");
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [nome, setNome]         = useState("");
  const [erro, setErro]         = useState("");
  const [sucesso, setSucesso]   = useState("");
  const [loading, setLoading]   = useState(false);

  const limpar = () => { setErro(""); setSucesso(""); };

  const handleLogin = async (e) => {
    e.preventDefault(); limpar();
    if (!email || !password) { setErro("Preencha o email e a password."); return; }
    setLoading(true);
    try { await login(email, password); }
    catch (err) { setErro(err.message || "Credenciais incorretas."); }
    finally { setLoading(false); }
  };

  const handleRegistar = async (e) => {
    e.preventDefault(); limpar();
    if (!email || !password || !nome) { setErro("Preencha todos os campos."); return; }
    if (password.length < 8) { setErro("A password deve ter pelo menos 8 caracteres."); return; }
    setLoading(true);
    try {
      const data = await authApi.registar(email, password, nome);
      TokenStorage.save(data);
      window.location.reload();
    }
    catch (err) { setErro(err.message || "Erro ao criar conta."); }
    finally { setLoading(false); }
  };

  const handleRecuperar = async (e) => {
    e.preventDefault(); limpar();
    if (!email) { setErro("Indique o seu email."); return; }
    setLoading(true);
    try {
      await authApi.recuperarPassword(email);
      setSucesso("Se o email existir, receberá instruções em breve.");
    } catch { setSucesso("Se o email existir, receberá instruções em breve."); }
    finally { setLoading(false); }
  };

  const input = "w-full px-0 py-3 bg-transparent border-b-2 border-[#c8bfb0] focus:border-[#1e3a5f] focus:outline-none text-[#1a1a2e] text-xl transition-colors duration-200 placeholder-[#b0a898]";
  const btn   = "w-full py-4 bg-[#1e3a5f] text-white text-xl font-semibold tracking-wide hover:bg-[#163050] active:scale-[0.98] transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed";

  return (
    <>
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600;700&family=Lora:wght@400;500&display=swap" rel="stylesheet" />

      <div className="min-h-screen flex" style={{ fontFamily: "'Lora', serif" }}>

        {/* Painel esquerdo — decorativo */}
        <div className="hidden md:flex w-[45%] bg-[#1e3a5f] flex-col justify-between p-14">
          <div>
            <div className="w-10 h-[2px] bg-[#c9a84c] mb-10" />
            <h1 className="text-white leading-tight" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "3.2rem", fontWeight: 300 }}>
              Memórias<br /><span className="font-semibold">Vivas</span>
            </h1>
            <p className="text-[#7a9cbf] text-xl mt-6 leading-relaxed">
              Assistente conversacional para Portfólios Sócio-Culturais.
            </p>
          </div>

          {/* Decoração geométrica */}
          <div className="relative h-64">
            <div className="absolute bottom-0 left-0 w-48 h-48 border border-[#c9a84c]/20 rounded-full" />
            <div className="absolute bottom-8 left-8 w-32 h-32 border border-[#c9a84c]/30 rounded-full" />
            <div className="absolute bottom-16 left-16 w-16 h-16 bg-[#c9a84c]/10 rounded-full" />
            <p className="absolute bottom-0 left-0 text-[#3d6080] text-sm tracking-widest uppercase">
              Patrimônio Imaterial
            </p>
          </div>
        </div>

        {/* Painel direito — formulário */}
        <div className="flex-1 bg-[#FAF7F2] flex items-center justify-center p-8 md:p-16">
          <div className="w-full max-w-sm">

            {/* Título móvel */}
            <div className="md:hidden mb-10">
              <div className="w-8 h-[2px] bg-[#c9a84c] mb-6" />
              <h1 className="text-[#1e3a5f]" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "2.4rem", fontWeight: 600 }}>
                Memórias Vivas
              </h1>
            </div>

            {modo === "login" && (
              <>
                <h2 className="text-[#1e3a5f] mb-2" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "2rem", fontWeight: 500 }}>
                  Bem-vindo de volta
                </h2>
                <p className="text-[#888] text-lg mb-10">Inicie sessão para continuar.</p>

                <form onSubmit={handleLogin} noValidate>
                  <div className="mb-8">
                    <label className="block text-[#888] text-sm tracking-widest uppercase mb-2">Email</label>
                    <input type="email" className={input} value={email} onChange={e => setEmail(e.target.value)} placeholder="o.seu@email.pt" autoComplete="email" />
                  </div>
                  <div className="mb-10">
                    <label className="block text-[#888] text-sm tracking-widest uppercase mb-2">Password</label>
                    <input type="password" className={input} value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" autoComplete="current-password" />
                  </div>

                  {erro    && <p className="text-red-600 text-lg mb-4">{erro}</p>}
                  {sucesso && <p className="text-green-700 text-lg mb-4">{sucesso}</p>}

                  <button type="submit" className={btn} disabled={loading}>
                    {loading ? "A entrar..." : "Entrar"}
                  </button>
                </form>

                <div className="mt-8 flex flex-col gap-3 text-center">
                  <button onClick={() => { setModo("recuperar"); limpar(); }} className="text-[#888] hover:text-[#1e3a5f] text-lg transition-colors">
                    Esqueceu a password?
                  </button>
                  <button onClick={() => { setModo("registar"); limpar(); }} className="text-[#1e3a5f] text-lg font-semibold hover:text-[#163050] transition-colors">
                    Criar conta nova
                  </button>
                </div>
              </>
            )}

            {modo === "registar" && (
              <>
                <h2 className="text-[#1e3a5f] mb-2" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "2rem", fontWeight: 500 }}>
                  Criar conta
                </h2>
                <p className="text-[#888] text-lg mb-10">Registe-se para começar.</p>

                <form onSubmit={handleRegistar} noValidate>
                  <div className="mb-8">
                    <label className="block text-[#888] text-sm tracking-widest uppercase mb-2">Nome completo</label>
                    <input type="text" className={input} value={nome} onChange={e => setNome(e.target.value)} placeholder="Manuel Silva" autoComplete="name" />
                  </div>
                  <div className="mb-8">
                    <label className="block text-[#888] text-sm tracking-widest uppercase mb-2">Email</label>
                    <input type="email" className={input} value={email} onChange={e => setEmail(e.target.value)} placeholder="o.seu@email.pt" autoComplete="email" />
                  </div>
                  <div className="mb-10">
                    <label className="block text-[#888] text-sm tracking-widest uppercase mb-2">Password</label>
                    <input type="password" className={input} value={password} onChange={e => setPassword(e.target.value)} placeholder="mínimo 8 caracteres" autoComplete="new-password" />
                  </div>

                  {erro && <p className="text-red-600 text-lg mb-4">{erro}</p>}

                  <button type="submit" className={btn} disabled={loading}>
                    {loading ? "A criar conta..." : "Criar conta"}
                  </button>
                </form>

                <div className="mt-8 text-center">
                  <button onClick={() => { setModo("login"); limpar(); }} className="text-[#888] hover:text-[#1e3a5f] text-lg transition-colors">
                    Voltar ao login
                  </button>
                </div>
              </>
            )}

            {modo === "recuperar" && (
              <>
                <h2 className="text-[#1e3a5f] mb-2" style={{ fontFamily: "'Cormorant Garamond', serif", fontSize: "2rem", fontWeight: 500 }}>
                  Recuperar password
                </h2>
                <p className="text-[#888] text-lg mb-10 leading-relaxed">
                  Indique o seu email e enviar-lhe-emos instruções.
                </p>

                <form onSubmit={handleRecuperar} noValidate>
                  <div className="mb-10">
                    <label className="block text-[#888] text-sm tracking-widest uppercase mb-2">Email</label>
                    <input type="email" className={input} value={email} onChange={e => setEmail(e.target.value)} placeholder="o.seu@email.pt" autoComplete="email" />
                  </div>

                  {erro    && <p className="text-red-600 text-lg mb-4">{erro}</p>}
                  {sucesso && <p className="text-green-700 text-lg mb-4">{sucesso}</p>}

                  <button type="submit" className={btn} disabled={loading}>
                    {loading ? "A enviar..." : "Enviar instruções"}
                  </button>
                </form>

                <div className="mt-8 text-center">
                  <button onClick={() => { setModo("login"); limpar(); }} className="text-[#888] hover:text-[#1e3a5f] text-lg transition-colors">
                    Voltar ao login
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}