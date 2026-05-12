# Relatório de Desenvolvimento: Epic 6 - Geração de Artefactos (Memórias Vivas)

## 1. Visão Geral
Esta iteração do projeto incidiu na implementação integral do **Epic 6**, focado na conversão do património imaterial dos utilizadores seniores em artefactos digitais tangíveis (Livro de Memórias, Cartões de Histórias, Timeline e Vídeo Narrativo). O objetivo foi assegurar que as histórias partilhadas com o assistente virtual pudessem ser consolidadas e exportadas.

## 2. Funcionalidades Desenvolvidas

### 2.1. Backend (API & Serviços)
- **`artefactos_service.py`**: Desenvolvida a lógica principal para agregação do perfil biográfico (`PerfilBiografico`) e resumos das sessões (`Sessoes`) na construção do conteúdo dos artefactos.
- **Templates Dinâmicos HTML/Jinja2**: Criados os templates `livro_memorias.html` e `story_card.html` com suporte tipográfico clássico (Garamond/Lora) e estilos CSS injetados, servindo de base estrutural para os PDFs.
- **Integração WeasyPrint/XHTML2PDF**: Implementado o motor de conversão HTML-to-PDF para renderizar o Livro de Memórias (texto longo) e os Cartões (foco visual).
- **Geração de Vídeo (MoviePy)**: Configurado um pipeline que combina o texto de um momento chave, imagens estáticas de contexto e uma banda sonora de fundo (`saudade.mp3`) para gerar pequenos clipes nostálgicos MP4.

### 2.2. Frontend (Integração)
- **`PortfolioScreen.jsx`**: Construção do ecrã de Portfólio, permitindo ao utilizador visualizar a contagem de artefactos disponíveis e acionar os pedidos de geração à API.
- **`client.js`**: Centralização de todos os *endpoints* no serviço `artefactosApi` (ex: `gerarLivro`, `gerarVideo`, `downloadUrl`), garantindo injeção transparente de JWT.

---

## 3. Desafios Encontrados e Resoluções (Troubleshooting)

Ao longo do desenvolvimento e testes de integração end-to-end, foram identificados e resolvidos múltiplos problemas críticos que impediam o correto funcionamento do fluxo de geração de portfólio.

### Impasse 1: Erros de CORS e Acesso Frontend-Backend
- **Sintoma**: O Frontend falhava ao fazer chamadas a `/api/v1/artefactos` devolvendo Erros HTTP 500 originados por bloqueios de *Access-Control-Allow-Origin*.
- **Causa**: O `main.py` não tinha o router de artefactos registado nem incluía o endpoint nas permissões de CORS.
- **Resolução**: Inclusão do `artefactos_router` na árvore principal da aplicação (`app.include_router(artefactos.router)`) e verificação das políticas de CORS em ambiente de desenvolvimento.

### Impasse 2: Falha Crítica de Esquema na Base de Dados (SQLAlchemy vs PostgreSQL)
- **Sintoma**: Exceção `UndefinedColumnError` ao tentar gravar um artefacto recém-gerado.
- **Causa**: O modelo ORM SQLAlchemy usava a propriedade `metadata` (que é reservada na framework) mapeada incorretamente para a coluna do PostgreSQL. A base de dados esperava a coluna `meta_dados`.
- **Resolução**: O modelo em `utilizador.py` foi corrigido para usar explicitamente `meta_dados`. Posteriormente, foi gerada e aplicada uma migração do **Alembic** (`ad34d1296223_update_artefactos.py`) para alinhar a base de dados com o código.

### Impasse 3: Artefactos (PDFs) Gerados em Branco (0 Sessões)
- **Sintoma**: O Livro de Memórias e os Cartões eram gerados com sucesso, mas não continham histórias, declarando que a conta tinha 0 sessões concluídas, mesmo após longas conversas.
- **Causa**: O endpoint `POST /api/v1/chat/sessao/encerrar` extraía corretamente os factos com o Gemini e atualizava o Perfil Biográfico, mas "esquecia-se" de criar uma entrada na tabela `sessoes`.
- **Resolução**: Intervenção no ficheiro `chat.py` adicionando a instanciação direta do objeto `Sessao` e o respetivo `db.add()` e `db.commit()` logo após o sucesso do merge de perfil.

### Impasse 4: UI Congelado no Onboarding ("A Raquel está a falar...")
- **Sintoma**: Ao testar novos perfis, o frontend ficava preso e impedia o utilizador de falar.
- **Causa**: As políticas restritas de *Autoplay* dos *browsers* modernos (Safari/Chrome) bloqueavam a reprodução áudio do TTS porque não houve clique prévio. A Promessa de sincronização do texto estava pendente unicamente do evento de `ended` do áudio, provocando um ciclo infinito.
- **Resolução**: Em `OnboardingScreen.jsx`, refatorizou-se a lógica para apanhar rejeições na promessa `audio.play()`. Em caso de bloqueio do browser, a aplicação aciona imediatamente um *fallback* (`fallbackResolve()`) que mostra todo o texto e ativa o microfone no ecrã de imediato.

### Impasse 5: Sobrescrita Destrutiva do Histórico Inicial (Onboarding)
- **Sintoma**: Registos da entrevista inicial eram perdidos quando os utilizadores terminavam sessões no Dashboard.
- **Causa**: O endpoint de encerramento passava inadvertidamente o histórico da sessão corrente (`payload.historico_sessao`) para o parâmetro `historico_onboarding` aquando do update do perfil, sobrescrevendo a entrevista inicial.
- **Resolução**: Atualização do `chat.py` para passar o valor `historico_onboarding=None` na chamada a `profile_service.save_profile`, assegurando que o motor de base de dados mantinha a coluna original inalterada.

### Impasse 6: Rate Limits da API de IA a Gerar Resumos Vazios
- **Sintoma**: Textos massivos e ricos proferidos pelo utilizador eram processados no chat, mas no final, a sessão ficava registada com o `resumo_sessao` vazio na base de dados (e logo, não constava no livro).
- **Causa**: O uso repetitivo excedeu a quota gratuita (Free Tier) do Google Gemini 2.5 Flash, devolvendo um erro `429 RESOURCE_EXHAUSTED`. A função de extração de resumos silenciava o erro e devolvia uma string vazia `""`.
- **Resolução**: Implementou-se um sistema robusto de fallback multi-modelo no `gemini_service.py` (`_resumo_groq_fallback`). Sempre que o Gemini atinge o limite ou falha (ex: timeout, 429), o sistema faz uma comutação fluída para a API do Groq (usando o modelo *Llama 3.3 70B*), garantindo que as memórias nunca são perdidas devido a exaustão de quota de um serviço de terceiros.

### Impasse 7: Falha na Geração de Vídeo (`No module named 'moviepy.editor'`)
- **Sintoma**: Ao tentar gerar o "Vídeo Ilustrativo" no Portfólio, o backend lançava a exceção `ModuleNotFoundError` quebrando todo o processo de renderização e devolvendo erro 500.
- **Causa**: O ficheiro `requirements.txt` estava definido com `moviepy>=1.0.3`. Aquando do *build* da imagem Docker, o sistema descarregou automaticamente a versão recente `2.2.1` da biblioteca MoviePy, na qual o submódulo `moviepy.editor` foi completamente descontinuado e removido.
- **Resolução**: A dependência no `requirements.txt` foi redefinida com "pinning" rigoroso para `moviepy==1.0.3`. O contentor da API foi atualizado em "hot-swap" desinstalando a versão problemática e reinstalando a versão exata que suporta a arquitetura de processamento de áudio/vídeo concebida para este projeto.
