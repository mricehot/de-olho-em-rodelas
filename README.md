# De Olho em Rodelas

Site cidadão que mostra, com dados oficiais, para onde vai o dinheiro público de Rodelas (BA).
Os dados são coletados sozinhos todo dia pelo GitHub e o site é publicado de graça no GitHub Pages.

| Seção do site | Fonte oficial | O que mostra |
|---|---|---|
| Gastos | Siconfi / Tesouro Nacional (RREO, anexos 1 e 2) | Receita arrecadada, despesa liquidada, gastos por área (saúde, educação…) |
| Gastos, item por item | Portal de despesas da Prefeitura e da Câmara (Fator Sistemas) | Cada empenho: credor, valor empenhado e pago, secretaria, o que foi comprado |
| Salários | Siconfi / Tesouro Nacional (RGF, anexo 1) | Gasto com pessoal e % da receita (limite da LRF: 54%) |
| Transferências | Tesouro Nacional (Transferências Constitucionais) | FPM, FUNDEB, ITR, royalties: repasses obrigatórios da União, por mês e por tipo |
| Licitações e contratos | PNCP | Cada licitação e contrato, com valor, empresa e link para o edital |
| Recursos federais | Portal da Transparência (CGU) | Convênios, Bolsa Família e BPC pagos na cidade |
| Câmara | Siconfi (RGF do Poder Legislativo) + portal de despesas da Câmara | Gasto com pessoal e % da receita (limite: 6%) e cada empenho da Câmara |

## Como colocar no ar (uns 15 minutos, tudo grátis)

1. **Crie o repositório.** Em github.com, clique em *New repository*, dê um nome (ex.: `de-olho-em-rodelas`), deixe **Public** e crie. Depois envie todos os arquivos desta pasta (*Add file → Upload files*, arrastando a pasta inteira, inclusive `.github`).
2. **Pegue a chave da CGU.** Cadastre seu e-mail em https://portaldatransparencia.gov.br/api-de-dados (botão "Cadastre-se") e a chave chega por e-mail.
3. **Guarde a chave no GitHub.** No repositório: *Settings → Secrets and variables → Actions → New repository secret*. Nome: `CGU_API_KEY`. Valor: a chave. (Nunca coloque a chave dentro de um arquivo.)
4. **Ligue o site.** *Settings → Pages → Source:* escolha **GitHub Actions**.
5. **Rode a primeira coleta.** Aba *Actions → Coletar dados e publicar site → Run workflow*. A primeira vez demora (o PNCP só aceita uma consulta a cada ~5 segundos). Depois disso roda sozinho todo dia às 06:37.
6. **Pronto.** O endereço aparece em *Settings → Pages*, no formato `https://SEU-USUARIO.github.io/de-olho-em-rodelas/`.

Se uma fonte falhar num dia, as outras continuam e o site mostra na página inicial quando cada fonte foi atualizada pela última vez. Os detalhes do erro ficam na aba *Actions*.

## Estrutura

```
config.json              código IBGE, CNPJ da prefeitura e ano inicial
coletores/
  siconfi.py             gastos e pessoal da Prefeitura e da Câmara (Tesouro Nacional)
  transferencias.py      FPM, FUNDEB e outras transferências constitucionais
  despesas.py            cada empenho da Prefeitura e da Câmara (lê o portal da Fator Sistemas)
  pncp.py                licitações e contratos
  cgu.py                 recursos federais (precisa da chave)
  coletar_tudo.py        roda todos e registra o status em site/data/meta.json
site/
  index.html             o site inteiro (HTML + CSS + JS, sem dependências)
  data/                  JSONs gerados pelos coletores
testes/teste_coletores.py  testa os coletores sem internet, com respostas simuladas
.github/workflows/coletar.yml  coleta diária + publicação
```

## Rodar no seu computador

```bash
pip install -r requirements.txt
python testes/teste_coletores.py          # confere a lógica sem internet
python coletores/coletar_tudo.py siconfi pncp
CGU_API_KEY=sua_chave python coletores/coletar_tudo.py cgu
cd site && python -m http.server 8000     # abra http://localhost:8000
```

Para usar com outra cidade, troque `config.json` (código IBGE de 7 dígitos e CNPJ da prefeitura) e os textos do `site/index.html`.

## Cuidados

- **Privacidade:** contratos com pessoa física mostram o nome, mas o CPF aparece mascarado (`***.456.789-**`), no mesmo padrão do Portal da Transparência federal.
- **Fidelidade:** o site mostra os relatórios como a prefeitura os enviou, sem recalcular nada. Sempre aponte para a fonte oficial em caso de dúvida.
- **Independência:** deixe claro que o site não é da prefeitura (o rodapé já diz isso).

## Ideias para depois

- Folha de pagamento individual: a da Prefeitura só está em rodelas.ba.gov.br (que bloqueia coleta automática); a da Câmara parou em março de 2020. O caminho é pedir pelo e-SIC.

## Sobre as fontes da Prefeitura e da Câmara

- **Despesas detalhadas:** a Prefeitura (`pm_rodelas`) e a Câmara (`cm_rodelas`) publicam a execução da despesa no portal "Transparência 131" da Fator Sistemas. Não há API oficial: o coletor lê a mesma tabela que o portal carrega, um mês por vez, com pausa de 2 s entre consultas. O CPF já vem mascarado pela fonte.
- **API da Câmara (api.imap.org.br, código do órgão 1848):** existe e responde, mas está desatualizada (folha até 02/2020, empenhos vazios, contratos até 2023). Por isso não é usada.
