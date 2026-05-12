import asyncio
from app.services.gemini_service import gerar_resumo_narrativo

async def main():
    historico = [
        {"role": "user", "content": 'Lembro-me bem de um ano — devia ser por volta de setenta e tal — em que a geada queimou tudo logo em março. O meu pai, que Deus tem, olhou para o campo e disse: "Joaquim, este ano vamos comer pó". Eu era um rapazito de vinte anos, com as costas direitas como um pinheiro, e não aceitei aquilo. Fui para o monte, a pé, buscar água a uma nascente que todos diziam estar seca. Cavei com a enxada até os dedos sangrarem, dia e noite, debaixo de luar. O povo da aldeia passava e dizia que eu estava doido, que a terra estava morta. Mas eu sentia o coração da terra a bater ali por baixo. E não é que a água brotou? Pouca, mas viva. Naquele verão, enquanto os campos vizinhos estavam cinzentos, a minha horta era o único sítio verde que se via de cima do campanário da igreja. As batatas saíram da terra tão grandes que pareciam pedras do rio. Hoje, vês-me assim, devagarinho, a precisar deste cajado para não cair. A gente pensa que é dono da terra, mas é ao contrário: a terra é que é nossa dona. Ela deixa-nos andar por cima dela uns anos, pede-nos o suor, e no fim... bem, no fim ela reclama o que é dela. Mas sabes que mais? Se voltasse atrás, fazia os mesmos calos. Porque não há sono mais descansado do que o de um homem que chega a casa com o cheiro da terra agarrado à pele.'}
    ]
    resumo = await gerar_resumo_narrativo(historico)
    print("RESUMO:", resumo)

asyncio.run(main())
