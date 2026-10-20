# API de teste para o Peticiona

Protótipo local independente para demonstrar o contrato da API que o Peticiona poderia consumir. O modo padrão consulta dados reais do DJEN. O modo `modo=mock` continua disponível para testes offline.

## Executar

```powershell
python .\server.py
```

A API ficará disponível em `http://127.0.0.1:8765`.

## Demonstracao publica

Entrada publica pelo GitHub Pages:

<https://thierrydevsimplea.github.io/peticiona-bridge-api/>

O link acima encaminha para o ambiente operacional completo, sem instalar o projeto:

<https://peticiona-bridge-api.vercel.app/dashboard>

O codigo-fonte publico esta em:

<https://github.com/thierryDevSimplea/peticiona-bridge-api>

## Painel de demonstracao

Abra `http://127.0.0.1:8765/dashboard` para acessar o painel Simplea / Peticiona Bridge. Ele possui:

- configuracao da OAB, UF, periodo e fontes habilitadas;
- cinco fontes prioritarias: DJEN, DataJud, DEJT, DOU/INLABS e DEOAB;
- conector separado da AASP, com link para a documentacao oficial;
- teste de disponibilidade dos portais;
- tela de resultados com a origem de cada publicacao e o status de cada fonte.

A configuracao feita pelo painel fica somente na memoria do processo local (`persisted: false`). A chave da AASP nao e gravada no projeto nem devolvida pelo endpoint de configuracao.

## Exemplos

```text
GET http://127.0.0.1:8765/health
GET http://127.0.0.1:8765/v1/publicacoes?oab=196088&uf=SP
GET http://127.0.0.1:8765/v1/publicacoes?oab=196088&uf=SP&data_inicio=2026-10-18&data_fim=2026-10-19
GET http://127.0.0.1:8765/v1/publicacoes?oab=196088&uf=SP&modo=mock
GET http://127.0.0.1:8765/v1/publicacoes/pub-0001
GET http://127.0.0.1:8765/v1/processos?oab=196088&uf=SP
GET http://127.0.0.1:8765/v1/fontes
GET http://127.0.0.1:8765/v1/fontes?probe=true
GET http://127.0.0.1:8765/v1/config
POST http://127.0.0.1:8765/v1/config
```

## O que este teste demonstra

- Identificação da OAB/SP `196088`.
- Consulta real do DJEN por OAB, UF e intervalo de datas.
- Consulta complementar real do DataJud por numero de processo, com capa e movimentacoes.
- Indicacao de credencial necessaria para consultar a API da AASP.
- Consulta de publicações com fonte, tribunal, processo, texto e prazo.
- Agrupamento das publicações por processo.
- Paginação simples por `limit` e `offset`.
- Filtro por status.
- Contrato inicial documentado em `openapi.json`.
- Catalogo das cinco fontes priorizadas e diagnostico opcional de disponibilidade.
- Painel visual para demonstracao e configuracao do conector.

## Próxima etapa

O conector real do DJEN ja esta ativo. O DataJud possui integracao parcial para consulta de capa e movimentacoes por numero de processo; ele nao e uma busca direta de publicacoes por OAB. A AASP sera consultada quando a chave oficial for configurada por variavel de ambiente ou pelo painel. DEJT, INLABS e DEOAB permanecem como fontes complementares a serem implementadas; o endpoint `fontes?probe=true` apenas testa alcance dos portais e nao equivale a uma integracao de dados.

## Documentacao oficial das fontes

- [DJEN / CNJ Swagger](https://hcomunicaapi.cnj.jus.br/swagger/index.html)
- [DataJud - endpoints publicos](https://datajud-wiki.cnj.jus.br/api-publica/endpoints/)
- [DEJT](https://dejt.jt.jus.br/dejt/dejt)
- [INLABS](https://inlabs.in.gov.br/acessar.php)
- [DEOAB](https://deoab.oab.org.br/)
- [AASP - documentacao da API](https://intimacaoapi.aasp.org.br/docapi/index.html)

No DEJT, a proxima etapa e validar o servico/WSDL, o formato da consulta e a disponibilidade dos dados antes de estimar o desenvolvimento do conector. No INLABS, a integracao devera baixar e processar arquivos XML/PDF. No DEOAB, nao foi identificada API publica para consumo direto.
