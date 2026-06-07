import asyncio
import json
import os
from groq import Groq
from app.services.gemini_service import _PROMPT_EXTRACAO, _PROMPT_MERGE, _PROMPT_CAPITULO

# Load env variables for groq
from dotenv import load_dotenv
load_dotenv("/app/.env")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def run_groq(prompt):
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

async def main():
    conversa_simulada = [
        {"role": "assistant", "content": "Olá Sr. Manuel. Hoje gostava de falar sobre algumas memórias suas. Lembra-se do seu primeiro emprego?"},
        {"role": "user", "content": "Sim, lembro-me perfeitamente. Aos 14 anos, comecei a trabalhar como aprendiz de sapateiro com o Sr. Joaquim, na Baixa de Lisboa. Ganhava muito pouco, mas adorava o cheiro a couro."},
        {"role": "assistant", "content": "Que memória tão interessante! 14 anos é muito jovem. Mais tarde chegou a mudar de profissão?"},
        {"role": "user", "content": "Sim, aos 22 anos fui para a tropa e quando voltei, com 24, decidi abrir a minha própria sapataria no bairro de Alvalade. Foi um dia de muito orgulho, a minha esposa a Maria estava lá a ajudar a pintar as paredes de verde."},
        {"role": "assistant", "content": "Deve ter sido um dia de muito orgulho, de facto, inaugurar a sua sapataria verde com a dona Maria! Teve esse negócio durante muito tempo?"},
        {"role": "user", "content": "Tive a sapataria até me reformar, aos 65 anos. Foram 41 anos de muito trabalho, mas conheci quase toda a gente do bairro. Tenho muita saudade dessa altura, das conversas que tínhamos ao balcão."}
    ]
    conversa_str = "\n".join(f"{m['role']}: {m['content']}" for m in conversa_simulada)

    print("--- INICIANDO EXTRAÇÃO DA SESSÃO (via Groq Fallback) ---")
    prompt_extracao = _PROMPT_EXTRACAO.format(conversa=conversa_str)
    perfil_novo = run_groq(prompt_extracao)
    print("\n[Perfil Extraído da Conversa]:")
    print(json.dumps(perfil_novo, indent=2, ensure_ascii=False))

    perfil_antigo = {
        "nome": "Manuel",
        "terra_natal": "Lisboa",
        "profissao": "Sapateiro",
        "linha_temporal": [
            {"periodo": "10 anos", "acontecimento": "Aprendeu a andar de bicicleta."}
        ],
        "memorias": [
            {"titulo": "A Bicicleta Azul", "narrativa": "Aos 10 anos, o pai comprou-lhe uma bicicleta azul.", "pessoas_envolvidas": ["Pai"], "local": "Jardim", "emocao": "Alegria", "idade_ou_data": "10 anos"}
        ]
    }

    print("\n--- INICIANDO MERGE COM PERFIL ANTIGO (via Groq Fallback) ---")
    prompt_merge = _PROMPT_MERGE.format(perfil_antigo=json.dumps(perfil_antigo, ensure_ascii=False), novos_factos=json.dumps(perfil_novo, ensure_ascii=False))
    perfil_fundido = run_groq(prompt_merge)
    print("\n[Perfil Fundido Final]:")
    print(json.dumps(perfil_fundido, indent=2, ensure_ascii=False))

    resumo_sessao = "O Sr. Manuel falou sobre o início da sua vida profissional. Começou aos 14 anos como aprendiz de sapateiro na Baixa. Aos 24 abriu a própria sapataria em Alvalade com a esposa Maria, paredes verdes, e lá esteve até aos 65 anos, tendo muitas saudades do contacto com os clientes do bairro."
    
    print("\n--- INICIANDO GERAÇÃO DE CAPÍTULO DE LIVRO (via Groq Fallback) ---")
    prompt_cap = _PROMPT_CAPITULO.format(resumo=resumo_sessao, nome="Manuel")
    capitulo = run_groq(prompt_cap)
    print("\n[Capítulo Gerado]:")
    print(json.dumps(capitulo, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
