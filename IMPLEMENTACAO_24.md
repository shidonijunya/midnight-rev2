# Midnight Sun — lote aprovado de 24 melhorias

**Referência:** 23/11/2026. Este documento descreve implementação, limitações
e regras **ainda não alteradas**. Os cinco aplicativos Streamlit e o Supabase
existentes são mantidos; não criar um novo projeto.

## Entregas técnicas deste lote

- Falha ao carregar ficha passa a interromper a inicialização; nunca faz UPSERT
  de defaults no lugar de uma ficha existente.
- Atualizações de recurso de ataques/defesas usam CAS em `updated_at` e
  **recalculam o desconto com valores recentes** em toda tentativa.
- Histórico das últimas 30 versões por jogador no `app_state`. Registro
  por edição e restauração condicionados à ativação do modo seguro; antes disso,
  nenhum snapshot histórico é exposto nas tabelas ainda públicas. Restaurar
  exige mestre autenticado e confirmação; não são criadas novas tabelas.
- Estado dos chefes salvo em `app_state.boss_runtime` com revisão CAS.
  HP, turnos, condições e rolagens do histórico são serializados.
- Removidas as escritas passivas do simulador: não sobrescrever o boss só
  porque o Streamlit atualizou a tela.
- Fórmulas de atributo, HP, mana, estamina, peso e perícia centralizadas
  em `game_rules.py`, sem mudança dos resultados.
- Código legado das fichas removido: JSON em disco, planejador de ações,
  antigos pontos e XP sem uso, mantendo dados legados no Supabase.
- Ficha mais compacta e editor de arma com básico/avançado; de 1 a 12 slots
  de arma, com 5 visíveis inicialmente. Reduzir quantidade **não apaga**
  valores de slots escondidos.
- Chefes podem ter 1 a 20 ataques, inclusive apenas físicos ou de área,
  com os chefes existentes compatíveis.
- Ferramentas de névoa de guerra e área (círculo, cone, linha) no mapa;
  persistência reutiliza `app_state.battle_effects`.
- Menos consultas simultâneas do mapa: tokens e efeitos no mesmo poll.
- Biblioteca de chefes com opção de duplicar modelo salvo.

## Limites e segurança antes do corte

A antiga política pública do Supabase **não muda somente com um commit**.
O acesso seguro só será ativado após executar com backup
`security_cutover.sql` no SQL Editor do Supabase **existente** e fornecer
Secrets nos **cinco aplicativos existentes**. A ferramenta GitHub não possui
credenciais nem acesso administrativo ao projeto Supabase para executar isso.

Cada app deve receber:
```toml
SUPABASE_URL = "URL_DO_PROJETO_EXISTENTE"
SUPABASE_SERVICE_ROLE_KEY = "CHAVE_PRIVADA_DO_SERVIDOR"
MIDNIGHT_SECURE_MODE = true

[ACCESS_PASSWORD_HASHES]
jogador_1 = "HASH_KURO"
jogador_2 = "HASH_ANDRIAS"
jogador_3 = "HASH_BONDOBO"
mestre = "HASH_MESTRE"
```

**Gerar cada hash localmente**, sem incluir senhas no GitHub:
```sh
python -c "from auth_unified import hash_password; import getpass; print(hash_password(getpass.getpass('Senha: ')))"
```

Mapeamento legado **preservado**:

| Papel da senha | Entrada Streamlit | Registro Supabase |
|---|---|---|
| jogador_1 | Kuro, ficha 1 | jogador_2 |
| jogador_2 | Andrias, ficha 2 | jogador_3 |
| jogador_3 | Bondobo, ficha 3 | jogador_1 |
| mestre | app_boss | Todas as fichas |

Nunca renomear os IDs do Supabase sem migração planejada.

**Atenção crítica:** no modo seguro, o iframe legado do mapa deixa de fazer
gravações anônimas, portanto o mapa fica **local ao navegador** até ser
migrado para um componente bidirecional seguro do Streamlit (v2) que envie
as ações ao Python com validação server-side. Ativar esse corte agora
interromperia a sincronização atual do mapa. O bucket `rpg-assets` permanece
público para preservar as URLs das imagens antigas; proteger também o
conteúdo das imagens exige um passo adicional com URLs assinadas.

O acesso ao histórico armazenado em `app_state` é sujeito ao mesmo risco
de acesso público enquanto as políticas antigas estiverem habilitadas.

## Garantias e limites de concorrência

- O CAS protege a linha toda enquanto os **cinco apps** gravarem `updated_at`
  e respeitarem a revisão. Outros clientes que não sigam essa convenção
  devem ser migrados.
- A gravação do gasto de recurso e a postagem do resultado no chat ainda
  são duas operações distintas. Se o chat cair depois do gasto, o recurso
  pode ter sido consumido sem registro no chat. Uma transação PostgreSQL
  única seria necessária para garantir ambas as ações.
- O histórico é **best effort**: sua escrita ocorre depois da alteração
  principal, portanto uma falha independente em `app_state` pode impedir o
  registro de uma versão sem desfazer o ataque. Um trigger de auditoria na
  mesma transação PostgreSQL tornaria o histórico totalmente confiável.
- O controle de revisão do boss impede **sobrescrever silenciosamente** outra
  sessão, mas o mestre pode precisar atualizar a tela se houver conflito.
- A ferramenta de névoa/áreas usa as permissões do mapa antigo quando
  as senhas não estão ativas; somente um componente server-side pode
  impedir que qualquer pessoa com acesso público modifique a névoa.
- Supabase Realtime foi analisado, mas não se deve adicioná-lo ao iframe
  anônimo e afirmar que isso traz segurança. Recomenda-se substituir o
  iframe por componente Streamlit v2 com ida/volta ao Python.

## Conceitos de mecânicas: especificações a aprovar antes de programar

**Ataque carregado:** manter a regra atual de dados ×3 e custo ×2,
mas introduzir preparação de uma ação/turno, com possibilidade de interrupção.
Definir quando se paga o custo caso seja interrompido.

**Postura:** propor barra de 100, Parry bem-sucedido +20, golpe carregado +15,
normal +5; quebra em 100 interrompe uma ação e reinicia postura. Valores
exclusivamente propostos, sujeitos a ajuste e aprovação.

**Peso:** duas opções: (A) só aviso e nenhuma penalidade; (B) entre 70–100%
da capacidade a esquiva custa +25% de estamina, acima de 100% fica impedida
até aliviar a carga. Precisa de aprovação antes de alterar as fichas.

**Fases dos chefes:** permitir efeitos de entrada, condições temporárias
e diferentes probabilidades de combos por fase. Definir efeitos e limites.

**Estilos:** Agressivo = 70/20/10 (físico/misto/área);
Técnico = 35/45/20; Arcano = 20/30/50. Distribuições propostas,
não são as probabilidades atuais do sistema.

**Dificuldade:** permitir Normal (modificadores atuais), Brutal (+2 às
dificuldades da matriz) e Implacável (+4), sem modificar a ficha do jogador;
sugestão que requer aprovação.

**Nenhuma dessas seis mudanças de regras foi implementada neste lote.**

## Validação

CI: `python -m compileall -q .`, regressão `unittest`, extração e
`node --check` do JavaScript. Testes funcionais adicionais cobrem perda
de conexão, desconto sob corrida e serialização do estado do boss.

O código do repositório e os testes automatizados não substituem testes
manuais no Streamlit com o Supabase real. Nunca afirmar que uma migração
SQL foi aplicada sem autorização e acesso confirmado ao projeto.
