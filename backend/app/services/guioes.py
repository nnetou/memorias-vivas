"""
guioes.py — Guiões de entrevista por tema para o Memórias Vivas
Utilização:
    from app.services.guioes import GUIOES, get_system_prompt, get_abertura
"""
 
import json
 
# ─────────────────────────────────────────────────────────────────────────────
# GUIÕES POR TEMA
# Cada tema tem:
#   - descricao    : texto curto para mostrar ao utilizador/cuidador
#   - abertura     : primeira mensagem do assistente ao entrar no tema
#   - perguntas    : lista ordenada de perguntas principais (o LLM escolhe a
#                    mais adequada dado o contexto)
#   - followups    : perguntas de aprofundamento, usadas após respostas ricas
#   - encerramento : frase de transição quando o tema está esgotado
# ─────────────────────────────────────────────────────────────────────────────
 
GUIOES: dict = {
 
    # ── 1. INFÂNCIA ──────────────────────────────────────────────────────────
    "infancia": {
        "descricao": "Os primeiros anos de vida, a terra natal, a família e as brincadeiras.",
        "abertura": (
            "Hoje gostava de o/a levar de volta ao início de tudo. "
            "Conte-me um pouco sobre onde cresceu. Como era a sua terra natal?"
        ),
        "perguntas": [
            "Como era a sua casa em criança? Quem vivia lá consigo?",
            "Qual é a memória mais feliz que guarda da sua infância?",
            "Como eram as brincadeiras quando era pequeno/a? Com quem brincava?",
            "Como era a escola? Tinha algum professor que se lembrasse com carinho?",
            "Havia alguma tradição especial na sua família quando era criança?",
            "Como era a relação com os seus pais? Havia momentos especiais com eles?",
            "Tinha irmãos ou primos com quem cresceu? Como eram?",
            "Havia algum lugar especial onde gostava de ir em criança — um campo, uma praça, um rio?",
            "Quais eram as festas que mais esperava quando era pequeno/a?",
            "O que queria ser quando fosse grande?",
            "Havia alguma coisa que o/a assustava em criança?",
            "Como era o Natal ou a Páscoa na sua casa quando era criança?",
        ],
        "followups": [
            "Pode contar-me mais sobre esse momento?",
            "E como é que isso o/a fez sentir na altura?",
            "Lembra-se de algum detalhe especial — um cheiro, uma cor, um som?",
            "Essa pessoa foi importante para si. O que é que aprendeu com ela?",
            "E o que aconteceu a seguir?",
            "Isso era comum na sua região ou era algo especial da sua família?",
            "Quando pensa nessa memória, o que é que sente hoje?",
        ],
        "encerramento": (
            "Que infância rica e cheia de história. "
            "Obrigado/a por me ter deixado entrar nesse mundo. "
            "Gostava de continuar a conversa noutro tema quando quiser."
        ),
    },
 
    # ── 2. TRABALHO ──────────────────────────────────────────────────────────
    "trabalho": {
        "descricao": "A vida profissional, as aprendizagens, os colegas e os momentos de orgulho.",
        "abertura": (
            "Queria conhecer melhor a sua vida profissional. "
            "Qual foi o seu primeiro trabalho? Como foi essa experiência?"
        ),
        "perguntas": [
            "O que o/a levou a escolher essa profissão ou esse caminho?",
            "Como era um dia normal de trabalho para si?",
            "Qual foi o momento de maior orgulho na sua vida profissional?",
            "Havia alguém — um chefe, um colega, um mestre — que o/a ensinou muito?",
            "Recorda-se do primeiro salário que recebeu? O que fez com ele?",
            "Havia alguma tarefa que adorava fazer no trabalho? E alguma que detestava?",
            "O seu trabalho era fisicamente exigente ou mais de cabeça?",
            "Como era a relação com os seus colegas? Havia amizades especiais?",
            "Houve alguma situação difícil no trabalho que o/a marcou?",
            "O trabalho mudou muito ao longo dos anos? O que mudou?",
            "Se pudesse ter escolhido qualquer profissão, o que teria sido?",
            "Quando se reformou (ou deixou de trabalhar), como foi essa transição?",
            "O que é que o seu trabalho lhe ensinou sobre a vida?",
        ],
        "followups": [
            "Como era essa pessoa? Pode descrever-me como era?",
            "E os outros colegas, como reagiram a isso?",
            "Esse momento mudou alguma coisa na forma como via o trabalho?",
            "Havia mais pessoas nessa situação ou era caso único?",
            "Isso era comum na sua época ou era algo novo?",
            "E a sua família, como via o seu trabalho?",
            "Sente orgulho quando pensa nisso hoje?",
        ],
        "encerramento": (
            "Que vida profissional cheia de experiências. "
            "É evidente o quanto trabalhou e o quanto aprendeu ao longo do caminho. "
            "Podemos continuar com outro tema sempre que quiser."
        ),
    },
 
    # ── 3. MIGRAÇÃO ──────────────────────────────────────────────────────────
    "migracao": {
        "descricao": "A experiência de partir, chegar a um lugar novo e reconstruir a vida.",
        "abertura": (
            "Gostava de perceber melhor a sua experiência de partir e chegar a um lugar novo. "
            "O que o/a levou a deixar a sua terra? Como foi essa decisão?"
        ),
        "perguntas": [
            "Como foi a partida? Lembra-se do dia em que saiu?",
            "Quem ficou para trás? Como foram as despedidas?",
            "Como era o sítio para onde foi? O que mais o/a surpreendeu?",
            "Como foi aprender a viver numa terra diferente — os costumes, a língua, a comida?",
            "Havia outros portugueses ou pessoas da sua terra por perto? Como se ajudavam?",
            "Qual foi a maior dificuldade nos primeiros tempos?",
            "Havia alguma coisa de Portugal que sentia mais falta? Como lidava com essa saudade?",
            "Como era a relação com as pessoas do país onde foi viver?",
            "Havia algum ritual ou hábito que mantinha para se sentir ligado/a a Portugal?",
            "Enviava dinheiro ou cartas para a família cá? Como era isso?",
            "O que é que esse país ou região lhe deu que Portugal não poderia ter dado?",
            "Quando voltou (ou pensa em voltar), o que sentiu ao ver a sua terra?",
            "O que é que essa experiência de migrar lhe ensinou sobre si próprio/a?",
        ],
        "followups": [
            "E os seus filhos (ou família), como viveram essa mudança?",
            "Como era comunicar com a família cá? Havia cartas, telefonemas?",
            "Isso custou muito na altura?",
            "Havia uma comunidade que o/a acolheu?",
            "E hoje, como olha para essa decisão de partir?",
            "Sente que ficou dividido/a entre dois mundos?",
            "Esse momento marcou muito a sua identidade?",
        ],
        "encerramento": (
            "A sua história de vida atravessou fronteiras — isso exige uma coragem enorme. "
            "Obrigado/a por partilhar essa jornada comigo. "
            "Podemos continuar com outro tema quando estiver pronto/a."
        ),
    },
 
    # ── 4. TRADIÇÕES ─────────────────────────────────────────────────────────
    "tradicoes": {
        "descricao": "As festas, os rituais familiares, os costumes locais e o que se transmitia de geração em geração.",
        "abertura": (
            "Cada família e cada região tem as suas tradições especiais. "
            "Quais são as tradições que mais marcaram a sua vida — em família ou na sua terra?"
        ),
        "perguntas": [
            "Como se celebrava o Natal na sua casa? Havia algum ritual especial?",
            "E a Páscoa — havia tradições próprias na sua família ou região?",
            "As festas da aldeia ou da cidade eram importantes? O que se fazia?",
            "Havia alguma tradição de casamento, baptizado ou funeral que se seguia rigorosamente?",
            "Como se celebrava a matança do porco ou outras tradições rurais, se havia?",
            "Havia rezas, ladainhas ou práticas religiosas que faziam parte do dia a dia?",
            "Que tradições a sua mãe ou avó lhe transmitiu que ainda guarda?",
            "Havia alguma superstição ou crença que toda a gente na sua terra respeitava?",
            "As colheitas ou as épocas do ano marcavam a vida da sua família de alguma forma?",
            "Havia trajes, danças ou músicas tradicionais da sua região?",
            "Que tradições passou aos seus filhos ou netos?",
            "Há alguma tradição que sente que se perdeu e que lhe custou ver desaparecer?",
        ],
        "followups": [
            "Como era essa festa na prática? Quem participava?",
            "Essa tradição ainda existe hoje ou foi-se perdendo?",
            "O que é que essa tradição significava para a família?",
            "Havia algum momento especial dentro dessa celebração que esperava com mais ansiedade?",
            "Quem era o guardião dessa tradição na sua família — quem a organizava?",
            "Como aprendeu a fazer isso? Alguém lhe ensinou?",
            "O que sente quando pensa nessa tradição hoje?",
        ],
        "encerramento": (
            "As tradições são o fio que nos liga às gerações anteriores. "
            "É muito bonito o que partilhou comigo. "
            "Podemos explorar outro tema sempre que quiser."
        ),
    },
 
    # ── 5. MÚSICA ────────────────────────────────────────────────────────────
    "musica": {
        "descricao": "As músicas que marcaram a vida, os artistas preferidos, as danças e os momentos musicais.",
        "abertura": (
            "A música tem uma forma única de nos trazer de volta a momentos especiais. "
            "Qual é a música ou o cantor que mais o/a marcou ao longo da vida?"
        ),
        "perguntas": [
            "Havia música em casa quando era criança? Quem cantava ou tocava?",
            "Qual é a música que, quando ouve, o/a leva imediatamente a um momento do passado?",
            "Havia danças ou bailes na sua terra? Como eram?",
            "Gostava de fado, de música popular, de outro estilo? O que o/a tocava mais?",
            "Havia um cantor ou cantora que adorava? O que é que essa voz tinha de especial?",
            "Tocava algum instrumento ou gostava de cantar?",
            "Havia músicas que cantavam em família — à mesa, nas festas?",
            "Recorda-se de uma música que esteve presente num momento muito importante da sua vida?",
            "As músicas religiosas — hinos, cantos de missa — eram importantes para si?",
            "Como se ouvia música antigamente — rádio, gira-discos, ao vivo?",
            "Havia alguma música que ouvia quando estava triste ou precisava de força?",
            "Que música gostaria que tocasse no dia mais especial da sua vida?",
        ],
        "followups": [
            "O que é que essa música lhe faz lembrar concretamente?",
            "Havia alguém especial com quem partilhava essa música?",
            "Como era essa época em termos de música — o que é que toda a gente ouvia?",
            "Consegue cantar ou cantarolar algum pedacinho dessa música?",
            "Essa música ainda o/a emociona quando a ouve?",
            "E os seus filhos ou netos, que música ouvem? Gosta?",
        ],
        "encerramento": (
            "A música que descreveu diz muito sobre quem é. "
            "Obrigado/a por esta viagem musical. "
            "Podemos continuar com outro tema quando quiser."
        ),
    },
 
    # ── 6. RECEITAS ──────────────────────────────────────────────────────────
    "receitas": {
        "descricao": "A cozinha, os sabores da infância, as receitas de família e o prazer de cozinhar.",
        "abertura": (
            "Dizem que o cheiro da comida é a memória mais forte que temos. "
            "Qual é o prato que, quando come ou cheira, o/a leva imediatamente de volta à infância?"
        ),
        "perguntas": [
            "Quem cozinhava melhor na sua família? O que é que essa pessoa fazia de especial?",
            "Há alguma receita de família que só vocês sabem fazer — um segredo de cozinha?",
            "Qual era o prato que pedia sempre quando fazia anos ou em dias especiais?",
            "Como aprendeu a cozinhar? Havia alguém que o/a ensinou?",
            "Havia ingredientes ou produtos que usavam muito na sua região e que são difíceis de encontrar hoje?",
            "Como era a matança do porco ou a produção de azeite, vinho ou outros produtos na sua terra?",
            "Havia diferença entre a comida do dia a dia e a comida das festas?",
            "Qual é o prato que mais gosta de cozinhar hoje?",
            "Há algum prato que já não se faz como antigamente e que sente falta?",
            "A cozinha era um lugar de convívio na sua casa? Quem aparecia por lá?",
            "Havia pão caseiro, chouriço ou produtos feitos em casa? Como se fazia?",
            "Que receita gostaria que os seus netos aprendessem e não deixassem perder?",
        ],
        "followups": [
            "Como se fazia isso exatamente? Pode descrever-me os ingredientes?",
            "Essa receita ainda existe na família ou foi-se perdendo?",
            "Havia um cheiro especial nessa cozinha que ainda se recorda?",
            "Quem mais estava presente quando se fazia isso?",
            "Essa receita vinha de onde — da sua mãe, da sua avó?",
            "O que é que tornava essa comida tão especial — os ingredientes, a pessoa que fazia, a ocasião?",
            "Se me quisesse ensinar essa receita, como começaríamos?",
        ],
        "encerramento": (
            "Que riqueza gastronómica e afectiva. "
            "As receitas que partilhou são um tesouro que merece ser preservado. "
            "Podemos continuar com outro tema quando estiver pronto/a."
        ),
    },
 
    # ── 7. VALORES ───────────────────────────────────────────────────────────
    "valores": {
        "descricao": "As crenças, os princípios de vida, a fé e o que guiou as grandes decisões.",
        "abertura": (
            "Ao longo da vida vamos percebendo o que realmente nos guia. "
            "Quais são os valores ou princípios que sente que sempre o/a acompanharam?"
        ),
        "perguntas": [
            "O que é que os seus pais lhe ensinaram que nunca esqueceu?",
            "A fé ou a religião foi importante na sua vida? De que forma?",
            "Houve alguma situação difícil que pôs à prova os seus valores? Como agiu?",
            "O que é para si uma boa pessoa? Conheceu alguém assim que foi um exemplo?",
            "O que pensa sobre o trabalho — é um dever, uma paixão, uma necessidade?",
            "Como via a família — o papel do marido, da mulher, dos filhos?",
            "O que é que mudou nas suas crenças ao longo da vida?",
            "Havia algo que nunca faria, independentemente das circunstâncias?",
            "Como lidava com as injustiças — na vida, no trabalho, na sociedade?",
            "O que pensa sobre a amizade? O que é um verdadeiro amigo para si?",
            "Houve algum livro, alguma pessoa ou alguma experiência que mudou a sua forma de ver o mundo?",
            "O que gostaria que os seus filhos e netos guardassem de si — que valor ou ensinamento?",
        ],
        "followups": [
            "Pode dar-me um exemplo concreto de uma situação em que viveu esse valor?",
            "Como chegou a essa conclusão — foi algo que aprendeu ou que sentiu?",
            "Isso era diferente do que as pessoas à sua volta pensavam?",
            "Esse valor custou-lhe alguma coisa a manter — houve um momento difícil?",
            "Como acha que os tempos de hoje afectam esses valores?",
            "Transmitiu isso aos seus filhos? Como?",
            "Se pudesse dizer uma coisa aos mais novos sobre isso, o que seria?",
        ],
        "encerramento": (
            "Os valores que partilhou reflectem uma vida vivida com muita consciência e carácter. "
            "Obrigado/a por esta conversa tão profunda. "
            "Podemos continuar com outro tema quando quiser."
        ),
    },
 
    # ── 8. LIÇÕES DE VIDA ────────────────────────────────────────────────────
    "licoes_de_vida": {
        "descricao": "A sabedoria acumulada, os erros, os arrependimentos e os conselhos para as gerações futuras.",
        "abertura": (
            "Uma vida longa é uma escola enorme. "
            "Olhando para tudo o que viveu, qual é a lição mais importante que a vida lhe ensinou?"
        ),
        "perguntas": [
            "Houve algum momento na sua vida que o/a mudou completamente — para melhor ou para pior?",
            "Qual foi a decisão mais difícil que tomou? Arrependeu-se ou ficou em paz com ela?",
            "Houve alguém que o/a magoou muito? Conseguiu perdoar?",
            "O que é que faria de forma diferente se pudesse voltar atrás?",
            "Qual foi o momento de maior alegria da sua vida?",
            "E o momento mais doloroso — consegue falar sobre ele?",
            "O que aprendeu sobre si próprio/a nos momentos mais difíceis?",
            "Como se manteve de pé quando as coisas correram muito mal?",
            "Há algo que sempre quis fazer e nunca fez? Porquê?",
            "O que é a felicidade para si? Encontrou-a?",
            "Que conselho daria a um jovem de 20 anos que está a começar a vida?",
            "Que mensagem gostaria de deixar aos seus filhos, netos ou às gerações futuras?",
            "Como gostaria de ser recordado/a?",
        ],
        "followups": [
            "Isso foi um ponto de viragem na sua vida?",
            "Como é que chegou a essa conclusão?",
            "O que sente quando pensa nesse momento hoje — já consegue olhar para ele com paz?",
            "Essa lição mudou a forma como tratou as pessoas à sua volta?",
            "Partilhou alguma vez esse pensamento com alguém da família?",
            "O que acha que as gerações de hoje não compreendem que a sua geração compreendia?",
            "Se pudesse escrever uma carta para o/a jovem que foi, o que lhe diria?",
        ],
        "encerramento": (
            "A sabedoria que partilhou hoje é um presente verdadeiro. "
            "Obrigado/a por ter aberto o seu coração desta forma. "
            "A sua história merece ser preservada e lembrada."
        ),
    },
}
 
 
# ─────────────────────────────────────────────────────────────────────────────
# FUNÇÕES AUXILIARES
# ─────────────────────────────────────────────────────────────────────────────
 
TEMAS_DISPONIVEIS = list(GUIOES.keys())
TEMAS_LABELS = {
    "infancia":        "Infância",
    "trabalho":        "Trabalho",
    "migracao":        "Migração",
    "tradicoes":       "Tradições",
    "musica":          "Música",
    "receitas":        "Receitas",
    "valores":         "Valores",
    "licoes_de_vida":  "Lições de Vida",
}
 
 
def get_abertura(tema: str) -> str:
    """Devolve a mensagem de abertura para um dado tema."""
    if tema not in GUIOES:
        raise ValueError(f"Tema '{tema}' não existe. Temas disponíveis: {TEMAS_DISPONIVEIS}")
    return GUIOES[tema]["abertura"]
 
 
def get_system_prompt(tema: str, perguntas_feitas: list[str] | None = None) -> str:
    """
    Gera o system prompt completo para o Groq dado um tema.
 
    Args:
        tema              : chave do tema (ex: "infancia")
        perguntas_feitas  : lista de perguntas já colocadas nesta sessão
                            (para o LLM não repetir)
 
    Returns:
        String com o system prompt completo em PT-PT.
    """
    if tema not in GUIOES:
        raise ValueError(f"Tema '{tema}' não existe.")
 
    guiao = GUIOES[tema]
    feitas_str = ""
    if perguntas_feitas:
        feitas_str = (
            "\n\nPERGUNTAS JÁ FEITAS NESTA SESSÃO (não repitas):\n"
            + "\n".join(f"- {p}" for p in perguntas_feitas)
        )
 
    perguntas_str = "\n".join(f"- {p}" for p in guiao["perguntas"])
    followups_str = "\n".join(f"- {p}" for p in guiao["followups"])
 
    return f"""És um assistente conversacional empático chamado Memórias Vivas.
A tua missão é ajudar pessoas idosas a partilhar e preservar as suas memórias de vida.
 
TEMA ACTUAL: {TEMAS_LABELS.get(tema, tema)}
{guiao['descricao']}
 
PERGUNTAS DISPONÍVEIS PARA ESTE TEMA:
{perguntas_str}
 
PERGUNTAS DE APROFUNDAMENTO (followups):
{followups_str}{feitas_str}
 
REGRAS OBRIGATÓRIAS:
1. Faz SEMPRE apenas UMA pergunta de cada vez. Nunca duas.
2. Usa linguagem simples, frases curtas e um tom caloroso e paciente.
3. Após cada resposta do utilizador, começa por confirmar o que ouviste
   com uma frase curta do tipo "Que memória bonita..." ou "Percebi bem que...".
4. Só depois de confirmar é que colocas a próxima pergunta.
5. Escolhe a pergunta que flua mais naturalmente dado o que foi dito.
6. Se a resposta for rica em detalhes, usa primeiro um followup antes de
   avançar para a próxima pergunta principal.
7. Fala sempre em Português de Portugal (PT-PT). Evita expressões do Brasil.
8. Nunca apresses o utilizador. Se ele/ela não souber responder, normaliza
   com "Não há problema, às vezes é difícil recordar..." e oferece outra pergunta.
9. Se o utilizador ficar emocionado, reconhece com empatia antes de continuar.
10. Nunca inventes factos sobre a vida do utilizador.
"""
 
 
def get_encerramento(tema: str) -> str:
    """Devolve a frase de encerramento de um tema."""
    if tema not in GUIOES:
        raise ValueError(f"Tema '{tema}' não existe.")
    return GUIOES[tema]["encerramento"]
 
 
def listar_temas() -> list[dict]:
    """Devolve lista de temas com label e descrição para mostrar na UI."""
    return [
        {
            "id": key,
            "label": TEMAS_LABELS[key],
            "descricao": GUIOES[key]["descricao"],
        }
        for key in TEMAS_DISPONIVEIS
    ]
 
 
# ─────────────────────────────────────────────────────────────────────────────
# EXEMPLO DE USO
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Ver todos os temas disponíveis
    print("=== TEMAS DISPONÍVEIS ===")
    for t in listar_temas():
        print(f"  [{t['id']}] {t['label']} — {t['descricao']}")
 
    print("\n=== ABERTURA DO TEMA: INFÂNCIA ===")
    print(get_abertura("infancia"))
 
    print("\n=== SYSTEM PROMPT (primeiros 500 chars) ===")
    prompt = get_system_prompt("infancia", perguntas_feitas=["Como era a sua casa em criança?"])
    print(prompt[:500] + "...")