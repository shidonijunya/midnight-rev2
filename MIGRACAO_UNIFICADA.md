# Midnight Sun — revisão unificada (branch de implementação)

> **NÃO publicar em produção antes de migrar as políticas do Supabase e validar os testes.**
> A branch mantém a main original intacta, inclusive dados persistidos no banco.

## Entrada única
Execute com \`streamlit run app_unificado.py\`. Use os cinco scripts legados como
páginas internas, não como cinco implantações separadas. O mestre acessa todas as
fichas, boss e painel. Cada jogador acessa sua ficha e o painel.

### Senhas
Gere quatro hashes diferentes, em ambiente local:

\`\`\`bash
python -c "from auth_unified import hash_password; import getpass; print(hash_password(getpass.getpass('Senha: ')))"
\`\`\`

Configure os Secrets no Streamlit Cloud (NÃO inserir os valores reais no Git):

\`\`\`toml
SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "SUA_CHAVE_PRIVADA_DO_SERVIDOR"

[ACCESS_PASSWORD_HASHES]
jogador_1 = "pbkdf2_sha256$600000$SALT$HASH"
jogador_2 = "pbkdf2_sha256$600000$SALT$HASH"
jogador_3 = "pbkdf2_sha256$600000$SALT$HASH"
mestre = "pbkdf2_sha256$600000$SALT$HASH"
\`\`\`

As strings acima são placeholders, não credenciais válidas.
A chave SERVICE_ROLE deve existir **apenas nos Secrets do servidor**;
nunca ser enviada ao navegador ou incluída num script cliente.

## Migração de banco (etapa obrigatória)
1. Faça backup completo de \`characters\`, \`app_state\`, \`chat_messages\`
   e do Storage \`rpg-assets\`.
2. Execute \`supabase_private_migration.sql\` no projeto correto.
   Isso revoga permissões públicas das tabelas e uploads, preservando os registros.
3. Configure \`SUPABASE_SERVICE_ROLE_KEY\` no **único** app Streamlit.
4. Desative os links antigos, para impedir uso de apps não atualizados.
5. Teste as quatro senhas, leitura e escrita por perfil, chat e imagens.
6. Gere senhas únicas de alta entropia, gerencie rotação e limite tentativas de login
   no proxy/plataforma. Não há ainda proteção distribuída contra brute force.

## Melhorias implementadas
- Modificador de atributo usa \`(valor - 10) // 2\`: 20 → +5.
- Removidos pontos por nível, importação/exportação de ficha JSON, planejador
  de ações e restauração em branco da interface.
- Removido travamento de recursos atuais no máximo derivado.
- Importação **por arma** de JSON, preservando edição manual depois do import.
  Exemplo de JSON:
  \`\`\`json
  {"nome":"Espada longa","test_dados":1,"test_lados":20,"bonus_ataque":5,
   "dano_dados":2,"dano_lados":6,"bonus_dano":3,"crit_min":20,
   "crit_mult":2,"custo_estamina":4,"wa_texto":"Golpe especial",
   "wa_estamina":8,"wa_mana":2}
  \`\`\`
- Painel com cinco ataques, salvamento imediato dos recursos, defesas,
  perícias, rolador \`NdM±K\`, imagens/GIF no chat e cena dentro do painel.
- Chefe com seção reservada mesmo sem um chefe ativo.
- Grid 20×20 com zoom, tokens locais e medição Ctrl+arrastar.

## Limitações ainda em aberto
- O grid nesta branch **não compartilha** tokens ou posições entre navegadores.
  Para isso é necessário um componente Streamlit bidirecional e persistência
  dos tokens no Supabase, com conflito de edição resolvido.
- A sincronização de cena/boss e animação do rolador usa polling de 1 s,
  **não é transmissão instantânea garantida** nem Supabase Realtime.
  Navegadores podem restringir o som automático em outras sessões.
- A autorização ocorre no código Python do servidor; testar a implantação
  contra bypass é obrigatório antes de produção.
- O novo editor de retratos suporta recorte, enquadramento e prévia, mas
  a interface do simulador de bosses será redesenhada em outra etapa.
- A migração de segurança remove as políticas públicas; se houver outras
  aplicações usando a chave anon, elas perderão acesso.

## Verificação antes de merge
- Verificar que alterações concorrentes em ficha/painel não revertam HP/mana/estamina.
- Conferir importação de JSON válido/inválido e persistência das edições manuais.
- Exercitar upload JPG/PNG/WebP/GIF e chat em múltiplas sessões.
- Conferir rolador e ações de defesa, crítico, dano e consumo de recursos.
- Conferir políticas após a migração, tokens e permissões.
- Executar CI, smoke test Streamlit e teste manual em 3 navegadores.

**Sem validação no aplicativo em execução, estas alterações devem permanecer em
Pull Request de rascunho, não devem ser descritas como release estável.**
