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
