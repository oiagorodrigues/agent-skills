# Descoberta por IA: o que verificar e como

Lista ordenada pelo que robôs e agentes de IA de fato buscam, segundo logs publicados em outubro de 2026 (https://pournasserian.com/writing/ai-friendly-website-2026) e a documentação dos operadores. Os padrões mais novos (llms.txt v2, Content Signals, IETF AI Preferences, Web Bot Auth, MCP Server Cards) ainda mudam; confira a fonte oficial antes de recomendar um formato exato e cite a data da consulta.

Troque `$SITE` pela origem auditada (ex.: `https://exemplo.com`) e `$PAGE` por uma página importante.

## 1. Texto no HTML do servidor

Os robôs da OpenAI, da Anthropic e da Perplexity não executam JavaScript; Googlebot e Applebot executam. Texto que só aparece depois da hidratação não existe para os primeiros.

```bash
curl -s -A "ClaudeBot/1.0" "$SITE$PAGE" \
  | sed 's/<script[^>]*>[^<]*<\/script>//g' \
  | grep -o '<main.*' | sed 's/<[^>]*>/ /g' | tr -s ' \n' | head -c 1500
```

Passa quando o H1, os parágrafos e as listas da página aparecem na saída. Cuidado com amostras curtas: os primeiros caracteres costumam ser `<head>`, scripts de tema e JSON-LD, o que não prova nada sobre o conteúdo. Confira também que há um único `<main>`, headings reais e nada essencial escondido em `<aside>`, `<footer>` ou elementos ocultos, que extratores como Readability e trafilatura descartam.

## 2. JSON-LD coerente com a página

Gerado das mesmas fontes que o texto visível e sem afirmar o que a página não mostra. O Google diz que AI Overviews e AI Mode não pedem marcação especial; estudos de schema e citação em IA não acharam ganho. Trate como requisito de consistência, não como alavanca de citação.

## 3. robots.txt por finalidade

Os operadores separam robôs por finalidade. A política de cada grupo é decisão do dono do site: apresente as consequências e pergunte, nunca escolha por ele.

| Finalidade | Robôs | Efeito de bloquear |
| --- | --- | --- |
| Índice de busca, inclusive o que respostas de IA citam | Googlebot, Bingbot, Applebot, OAI-SearchBot, Claude-SearchBot, PerplexityBot | Some da busca e das citações |
| Busca disparada por uma pessoa num assistente | ChatGPT-User, Claude-User, Perplexity-User | O assistente não lê a página quando pedem. OpenAI e Perplexity dizem que esses podem ignorar o robots.txt; a Anthropic diz que respeita |
| Treino de modelos | GPTBot, ClaudeBot, Google-Extended, Applebot-Extended, Amazonbot, Meta-ExternalAgent, CCBot | Sai de treinos futuros. Bloquear o Google-Extended não tira o site da busca nem dos AI Overviews |

```bash
curl -s "$SITE/robots.txt"
```

Verifique: grupos coerentes com a política declarada; `Sitemap:` absoluto; nenhuma regra bloqueando CSS, JS, cópias em Markdown ou páginas importantes por engano. Um robô usa só o grupo mais específico que o nomeia, então uma linha posta apenas em `User-agent: *` não vale para robôs com grupo próprio.

`Content-Signal: search=yes, ai-input=yes, ai-train=no` (Cloudflare, https://blog.cloudflare.com/content-signals-policy/) declara a preferência por finalidade. Nenhum operador se comprometeu a ler. Recomende só como declaração, repetida em cada grupo, e avise que o robots.txt gerenciado da Cloudflare acrescenta `ai-train=no` sozinho.

## 4. Sitemap com `lastmod` honesto

```bash
curl -s "$SITE/sitemap.xml" | grep -o '<lastmod>[^<]*</lastmod>' | sort | uniq -c | head
```

Sinal de problema: todas as URLs com a mesma data, ou com a data do último build. Google e Bing usam `lastmod` só quando ele é consistentemente correto e ignoram `changefreq` e `priority`. Sem uma fonte real (data de publicação, hash do conteúdo, histórico do CMS), é melhor omitir `lastmod` do que inventar. Uma solução que funciona em sites estáticos: guardar o hash do texto de cada página e a data em que ele mudou, com um teste que falha quando o hash fica desatualizado.

## 5. IndexNow

Bing, Yandex, Seznam, Naver, Yep e outros (lista em https://www.indexnow.org/searchengines.json) compartilham o aviso entre si; o Google não participa. O Bing liga IndexNow ao Copilot.

```bash
curl -s -o /dev/null -w "%{http_code}\n" "$SITE/<chave>.txt"
```

Verifique: arquivo de chave na raiz com a própria chave; envio automático só das URLs alteradas, logo depois do deploy, por `POST` com `host`, `key`, `keyLocation` e `urlList`. Respostas 200 e 202 são sucesso. Reenviar todas as URLs a cada deploy é erro. Que o IndexNow alcance o ChatGPT search não está documentado.

## 6. Cópia em Markdown de cada página

Foi o item novo que robôs verificados buscaram de verdade (OAI-SearchBot, GPTBot, Applebot, Amazonbot, ClaudeBot), em geral pelo link no `<head>`.

```bash
curl -s "$SITE$PAGE" | grep -o '<link rel="alternate" type="text/markdown"[^>]*>'
curl -s -D - -o /dev/null "$SITE$PAGE.md" | grep -iE '^(HTTP|content-type|x-robots-tag|link)'
curl -s -D - -o /dev/null -H "Accept: text/markdown" "$SITE$PAGE" | grep -iE '^(HTTP|content-type|vary)'
```

Passa quando: há `<link rel="alternate" type="text/markdown" href="...">` na página; a cópia responde 200 com `text/markdown`, `X-Robots-Tag: noindex` e `Link: <URL da página>; rel="canonical"`; o texto é gerado das mesmas fontes que a página (não convertido do HTML) e acompanha cada seção visível. Opcional: responder `Accept: text/markdown` na própria URL com `Vary: Accept` (Claude Code, OpenCode e o chat do VS Code pedem Markdown primeiro).

As cópias não são indexadas: `noindex`, fora do sitemap e sem `Disallow` no robots.txt (o bloqueio impediria a leitura, que é o objetivo).

## 7. Feeds com o texto completo

Leitores de feed são o maior público; Google e Bing aceitam um feed como sitemap. Verifique `content:encoded` com o texto inteiro, datas reais, `atom:link rel="self"` e o link de descoberta `<link rel="alternate" type="application/rss+xml">`. Em sites sem blog, é prioridade baixa.

## 8. llms.txt

Mapa em Markdown na raiz (https://llmstxt.org). Nenhum robô de busca verificado o buscou nos logs citados e o Google diz que não usa. Agentes de código abrem às vezes. Recomende como item barato, nunca como alavanca de busca ou citação. Se existir: só o H1 é obrigatório, links absolutos, sem afirmações que o site não sustenta, e erros de servidor no arquivo contam contra no Lighthouse (404 é tratado como "não se aplica"). A v2 aceita descoberta por `rel="describedby"` em cada página.

## 9. MCP, AI Catalog e server card

Servidor MCP só se alguém vai usar: nenhum cliente comum descobre um servidor a partir do site, a pessoa precisa colar o endereço. Se o site já tem um assistente próprio ou o conteúdo é pequeno, normalmente não compensa o endpoint a mais. Se existir: `/.well-known/ai-catalog.json` e o server card (`<endpoint>/server-card`) precisam apontar para um endpoint que funciona, as ferramentas devem ser só de leitura, e o endpoint precisa recusar `Origin` de outro domínio e ter limite de taxa.

## 10. Medição

Analytics em JavaScript (GA, GTM, Vercel Web Analytics, Cloudflare Web Analytics) não vê robôs de IA. Peça logs de borda ou do servidor e conte só robôs verificados pelo CDN (IP publicado, DNS reverso ou Web Bot Auth), não o nome no `User-Agent`, que muitos falsificam. Para citações: o relatório de IA generativa do Search Console (só impressões; cliques de AI Overviews e AI Mode vêm misturados aos da web) e o AI Performance do Bing Webmaster Tools (citações e consultas de grounding, sem cliques).
