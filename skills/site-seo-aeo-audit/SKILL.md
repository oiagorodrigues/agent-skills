---
name: site-seo-aeo-audit
description: Auditar SEO e visibilidade em respostas de IA (AEO) de um ou mais sites informados por URL, com evidências, prioridades e ações verificáveis, incluindo o que robôs e agentes de IA conseguem ler (HTML sem JavaScript, robots.txt por finalidade, sitemap, cópias em Markdown, IndexNow, llms.txt). Use quando o pedido for uma auditoria de sites ou de prontidão para IA; não acione para uma edição pontual de metadados.
---

# Auditoria de SEO e AEO para URLs fornecidas

Receba uma ou mais URLs como entrada. Identifique o domínio, as páginas e os idiomas a avaliar. Se o usuário não delimitar mercado ou público, declare o recorte adotado; não transforme esse recorte em decisão de negócio.

## Evidências

- Consulte o site publicado: redirecionamentos, status HTTP, `robots.txt`, sitemap, HTML renderizado, canonical, `hreflang`, título, descrição, headings, links internos, conteúdo principal e dados estruturados. Use o código-fonte quando disponível para explicar achados, mas diferencie código de comportamento publicado.
- Busque as páginas importantes também como um robô que não executa JavaScript (por exemplo `curl` com `User-Agent: ClaudeBot`) e leia o conteúdo do `<main>`, não os primeiros caracteres da resposta, que costumam ser `<head>` e scripts. Os comandos de verificação estão em `references/ai-discovery.md`.
- Se o ambiente bloquear requisições ao site, peça ao usuário para rodar os comandos e colar a saída; no Claude Code, sugira o prefixo `!`. Não conclua sobre o site publicado só pelo código.
- Use Search Console quando a propriedade estiver acessível. Registre propriedade, tipo de pesquisa, país, dispositivo e datas. Examine consultas e páginas separadamente, além dos totais; compare períodos equivalentes. Com poucas impressões ou consultas ocultadas, não trate posição média ou CTR como tendência firme.
- Para desempenho e experiência móvel, use dados reais ou uma ferramenta de medição identificada. Não atribua um problema a Core Web Vitals sem medição.
- Verifique recomendações que possam mudar em fontes oficiais atuais. Comece pelo [Guia de SEO para iniciantes do Google](https://developers.google.com/search/docs/fundamentals/seo-starter-guide?hl=pt_BR); use a documentação específica do mecanismo de pesquisa para sitemap, dados estruturados e recursos de IA. Cite o URL de cada fonte externa usada.
- Se o acesso ao site, Search Console ou alguma ferramenta falhar, informe a limitação e continue com as evidências disponíveis. Não invente resultados de rastreamento, indexação, ranking ou tráfego.

## Julgamento

- Separe problemas de rastreamento e indexação de problemas de relevância, conteúdo e conversão. Confirme URLs importantes por inspeção quando possível; um contador agregado de sitemap não substitui a inspeção de URL.
- Avalie se cada página responde à intenção de busca com informação própria, específica e verificável. Revise títulos, snippets, estrutura, links e autoria quando fizer sentido. Não proponha conteúdo repetitivo, credenciais fictícias, casos sem prova nem inserção artificial de termos.
- Em AEO, avalie se as respostas principais são claras e acessíveis em texto, se entidades e autoria são identificáveis, se afirmações têm suporte e se dados estruturados descrevem o conteúdo visível. Trate marcação schema, `llms.txt` e menções em respostas de IA como sinais de efeito incerto, sem promessa de citação ou ranking.
- Priorize pelo impacto provável no objetivo do usuário, confiança na evidência e esforço. Diferencie fato observado, inferência e hipótese a validar. Uma meta de “top 5” precisa de consultas, país, período e página definidos; não prometa posição.

## Descoberta por IA

Avalie e priorize nesta ordem, que segue o que robôs e agentes buscam de fato; os critérios e comandos de cada item estão em `references/ai-discovery.md`:

1. Texto principal no HTML do servidor, num único `<main>` com headings reais, e JSON-LD gerado do mesmo conteúdo.
2. `robots.txt` que responde por finalidade: índice de busca, busca disparada por uma pessoa num assistente, treino de modelos. `Content-Signal` é opcional e só declara preferência.
3. Sitemap com `lastmod` que reflete a última mudança real do conteúdo, nunca a data do build, e IndexNow avisado das URLs alteradas a cada deploy.
4. Cópia em Markdown de cada página, ligada no `<head>` com `rel="alternate" type="text/markdown"`, com `noindex` e canonical para a página.
5. Feeds com o texto completo, quando o site publica conteúdo com data.
6. `llms.txt`, barato e útil para agentes de código, sem efeito comprovado em busca.
7. Servidor MCP e AI Catalog, só quando houver quem vá usar o endereço.

Liberar ou bloquear treino de modelos, ter servidor MCP e publicar `Content-Signal` são decisões do dono do site. Apresente o efeito de cada opção e pergunte; não as trate como achado nem decida no lugar dele. Ao implementar, gere essas peças a partir da mesma fonte de conteúdo do site, para não ficarem desatualizadas, e registre as regras na documentação do projeto para que páginas novas as sigam.

Para medir, não use analytics em JavaScript: ele não vê robôs de IA. Use logs de borda ou do servidor contando só robôs verificados pelo CDN, o relatório de IA generativa do Search Console e o AI Performance do Bing Webmaster Tools.

## Entrega

Para cada site, informe o recorte e a data da coleta, o estado atual, os achados com URLs e evidências, as correções já feitas (se autorizadas), as prioridades restantes e como medir o resultado. Relacione cada recomendação importante ao problema que ela resolve. Se o pedido incluir implementação, faça as correções pertinentes e verifique o resultado antes de encerrar; publicar ou mudar serviços externos segue a autorização do usuário e as regras do ambiente.
