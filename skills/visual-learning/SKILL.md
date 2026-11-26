---
name: visual-learning
description: Cria aulas visuais executáveis. Use quando o aluno quiser manipular um mecanismo, prever o resultado e observar a causa, ou quando pedir uma trilha de certificação ensinada por simulações.
---

# Visual learning

1. Escolha uma decisão que o aluno deva conseguir tomar sozinho. Abra com um caso, uma restrição e duas soluções plausíveis. Para uma trilha, associe cada decisão a um objetivo oficial e a uma questão inédita que avalie transferência.
2. Esboce a experiência em três quadros. Registre o estado inicial, a ação do aluno e o efeito observável. Abra uma janela sobre o mecanismo invisível, como a fila de mensagens em voo ou o atraso da replicação. Desenhe apenas as peças necessárias à pergunta. Em mecanismos espaciais, use a skill Anatomy, se disponível, para a ilustração. Uma linha do tempo costuma explicar melhor uma eleição, um prazo ou uma sequência.
3. Escreva a transição de estado antes de animar. Use entradas explícitas, unidades, relógio simulado e uma fonte de verdade para desenho, números e histórico. Identifique hipóteses didáticas junto aos controles e vincule comportamentos reais à documentação primária. Um botão deve mudar o modelo e produzir uma consequência que o aluno consiga apontar.
4. Peça uma previsão antes do primeiro evento decisivo. Ofereça avanço manual, reprodução automática pausável e reinício reproduzível. Após a demonstração, libere uma variável para comparar duas execuções sob a mesma carga. Exponha a sequência por teclado e em texto. Respeite movimento reduzido e use forma ou legenda além de cor.
5. Troque uma restrição e peça uma decisão com justificativa. Explique cada alternativa pelo evento observado. Conclua com uma frase que o aluno possa usar em outro problema.
6. Execute o caminho principal, uma escolha equivocada e o reinício. Compare os estados manual e automático no mesmo instante. Inspecione capturas no início, durante a transição mais rápida e ao fim, em tela estreita e larga. Verifique texto cortado, saltos de posição, foco, leitura da sequência e acordo entre histórico e medidores. Corrija e repita o caso que falhou. Registre o que de fato foi executado.

## Verificação de uma rodada

Antes de renderizar, escreva uma tabela pequena com instante, ação e resultado previsto. Inclua um caso de fronteira: consulte a réplica um instante antes de aplicar o evento e novamente no instante em que ele se torna visível. Conte separadamente pedidos do usuário e operações internas. Rode as duas alternativas com as mesmas entradas e zere os contadores entre elas. Entregue a aula quando desenho e histórico reproduzirem cada linha da tabela.

## Exemplo de granularidade

Pedido: mostrar por que um consumidor recebe o mesmo pedido de novo. O aluno prevê o que acontece se o processo cair depois de gravar a fatura e antes de confirmar a mensagem. Mostre o ID do pedido, o prazo de invisibilidade e o número de faturas. Avance o relógio, observe a reentrega e repita com uma chave de idempotência persistida atomicamente com a gravação. O critério é conseguir explicar por que duas entregas podem resultar em uma única fatura.

## Origem do método

A janela interna e a figura operável se inspiram em [Anatomy, de wheresryan22, MIT](https://github.com/wheresryan22/anatomy) e no [artigo de Elvar](https://x.com/elvar_official/status/2111831136171151589). Esta implementação acrescenta previsão, comparação controlada, questão de transferência e cobertura curricular.
