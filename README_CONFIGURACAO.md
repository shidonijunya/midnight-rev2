# Midnight Sun — pacote Streamlit integrado

## Arquivos
- `ficha_jogador.py`: ficha única para os três jogadores. O mesmo arquivo é implantado três vezes.
- `app_boss.py`: painel do mestre, baseado no script de chefe original, com publicação da cena/chefe e sincronização do JSON.
- `painel_geral.py`: painel compartilhado com cena, três personagens, barras, ataques/defesas, recursos, rolador e chat.
- `shared_backend.py`: acesso comum ao Supabase.
- `supabase_schema.sql`: tabelas, políticas e bucket de imagens.
- `requirements.txt`: dependências.

## Configuração inicial
1. Crie um projeto Supabase.
2. No SQL Editor do Supabase, execute todo o conteúdo de `supabase_schema.sql`.
3. Em Storage, confira se existe o bucket público `rpg-assets`.
4. Publique os cinco apps a partir do mesmo repositório, escolhendo o arquivo de entrada correspondente.
5. Em **Settings → Secrets** de cada app, configure:

```toml
SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
SUPABASE_ANON_KEY = "SUA_CHAVE_ANON_PUBLICA"
```

6. Nas três implantações de `ficha_jogador.py`, adicione também um identificador diferente:

Ficha 1:
```toml
PLAYER_ID = "jogador_1"
```
Ficha 2:
```toml
PLAYER_ID = "jogador_2"
```
Ficha 3:
```toml
PLAYER_ID = "jogador_3"
```

O app do chefe e o painel geral não precisam de `PLAYER_ID`.

## Publicar a cena
No app do chefe, use a seção **Cena compartilhada** na barra lateral. Escolha o modo Chefe/Cena narrativa, nome da cena e envie as imagens. Clique em **Publicar cena no painel**. No modo Chefe, a barra no painel geral oculta o valor numérico de HP.

## Sincronização
- A ficha individual salva os dados no registro do jogador indicado por `PLAYER_ID`.
- O painel geral lê esses mesmos registros e salva alterações de HP, mana e estamina no mesmo local.
- A estamina é resetada individualmente nos cards do painel geral.
- As mensagens são compartilhadas pelo banco; o histórico local do rolador é apenas da sessão do navegador.
- O app do chefe continua aceitando o formato JSON atual, mas ao salvar bosses também publica os dados no Supabase.

## Limitação importante de segurança
Este pacote segue a decisão de não usar login nem código individual. As políticas do SQL permitem leitura e escrita pública usando a chave anon. Portanto, é adequado apenas para uma mesa de confiança: qualquer pessoa com os links pode tentar alterar dados de qualquer personagem. O identificador `PLAYER_ID` separa as três instalações por padrão, mas não autentica a pessoa que está usando o link.

## Observações de implementação
- O painel tenta atualizar os dados automaticamente a cada poucos segundos. O Streamlit pode reexecutar a interface durante edição de texto; se isso incomodar, aumente o intervalo de atualização no `painel_geral.py`.
- A visualização dos dados usa dados reais dos dados rolados, mas a animação 3D é uma representação visual CSS, não um motor físico de dados.
- A Weapon Art permanece textual e consome os custos configurados, sem inventar fórmula de ataque/dano.
- Ataques calculam teste/dano e críticos usando os campos da ficha, mas não aplicam dano automaticamente ao chefe ou a outro personagem.
- A ficha original usa campos JSON para persistência; os novos campos de defesa e imagem são compatíveis com o JSON exportado, sem exigir que os arquivos antigos tenham esses campos.


## Três fichas individuais no Streamlit Cloud

Use estes arquivos como entradas separadas:
- `ficha_jogador_1.py` usa fixamente `jogador_1`.
- `ficha_jogador_2.py` usa fixamente `jogador_2`.
- `ficha_jogador_3.py` usa fixamente `jogador_3`.

Os três arquivos compartilham `shared_backend.py` e o mesmo projeto Supabase. Não é necessário configurar `PLAYER_ID` nos Secrets de cada ficha, porque o identificador está definido no arquivo. Configure `SUPABASE_URL` e `SUPABASE_ANON_KEY` nos Secrets de cada app, além de manter as dependências de `requirements.txt`.


---

## Revisão de 19/11/2026 — atualização dos aplicativos existentes

**Não é necessário criar novos apps ou outro projeto Supabase** para testar as
melhorias do painel e das fichas. Os arquivos de entrada atuais seguem iguais:

| Aplicativo existente | Script |
|---|---|
| Kuro | `ficha_jogador_1.py` |
| Andrias | `ficha_jogador_2.py` |
| Bondobo | `ficha_jogador_3.py` |
| Mesa e rolador | `painel_geral.py` |
| Mestre / Boss | `app_boss.py` |

Depois de o Streamlit Cloud terminar o redeploy da `main`, recarregue os
apps existentes (F5). A base existente e as tabelas não são migradas nem
apagadas. A autenticação por senha **não é ativada automaticamente**:
não há forma segura de derivar as quatro senhas individuais a partir das
credenciais de Supabase já existentes. Ela é opcional por enquanto, e precisa
de hashes em `ACCESS_PASSWORD_HASHES` nos Secrets de cada deployment
que se deseja proteger. O novo `app_unificado.py` continua disponível
para uma migração futura para URL única, porém **não substitui** as URLs
atuais sem mudar as configurações dos deployments.

A implementação atual mantém a chave `SUPABASE_ANON_KEY` porque os
aplicativos já publicados dependem dela. **Os acessos públicos do banco
continuam públicos** até uma migração consciente de RLS. Não execute
`supabase_private_migration.sql` ou troque para `service_role` nos apps
existentes sem planejar a mudança das permissões.

Melhorias: correção do modificador (20 = +5), salvamento de recursos
por campos modificados com controle de concorrência, sem botão Salvar;
cinco ataques, defesa e perícias, dados em botões e notação `2d20+7`,
chat com anexos e GIFs convertidos para WebP animado, prévia e recorte de
retrato e cena, boss com barra atualizada por polling e mapa 20×20 usando
a tabela `app_state` já existente.

**Limitações:** sincronização visual ocorre por consulta periódica (normalmente
1–2 segundos), não por eventos push garantidos. O mapa compartilhado
aproveita as políticas públicas existentes e não oferece isolamento por
usuário antes da autenticação/migração de segurança. O som dos dados pode
exigir clique no ícone de alto-falante quando o navegador bloqueia autoplay.
Em alterações simultâneas do mesmo token, a última gravação ainda prevalece.

### Backup e restauração
Os arquivos anteriores estão preservados na branch
`backup/main-before-midnight-revision-2026-11-19`.
Para reverter sem perder o histórico, restaure os scripts dessa branch
por um commit de reversão na `main`. Nenhuma migração de banco foi
executada por esta revisão.
