# Integração do frontend final com o backend

Base: `origin/main` em `35579f7`. A interface do cliente foi preservada: CSS inalterado e JSX visual do login idêntico. Foram corrigidos os vínculos de sessão, API e pacote estático; a publicação foi autorizada posteriormente e consta abaixo.

O frontend React é a única tela de entrada. O bundle anterior com `antecipe-auth-gate.js` sobreposto não é mais carregado pelo HTML gerado. Login e cadastro por e-mail usam `/api/auth/login`; Google usa PKCE, `state` aleatório e `/auth/callback`, concluído por `/api/auth/exchange`. O servidor confirma o perfil no Auth0 e mantém o token em cookie HttpOnly (Secure em HTTPS, SameSite=Lax), sem token ou senha em localStorage. Falhas do provedor não criam login local. Restauração e logout usam `/api/auth/session` e `/api/auth/logout`.

As regras de elegibilidade foram preservadas. A análise individual deixou de enviar 22/10/2026; What-if também usa o relógio atual. Os lotes de homologação passam pelo mesmo transporte de upload e conservam sua conexão para paginação/exportações. O gerador agora integra o pacote do backend, e o CSV é servido em streaming sem gravar arquivos na função. Os nomes visuais das modalidades de recebível continuam iguais, com seus valores traduzidos para os códigos aceitos pela API.

## Configuração externa

Use variáveis de ambiente do servidor ou `Codex/antecipe/.env` ignorado pelo Git: `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` e, se necessário, `AUTH0_DB_CONNECTION`. Os arquivos antigos `login/.env` continuam sendo lidos como compatibilidade. Nenhum segredo fornecido na conversa foi copiado para fontes, arquivos de exemplo ou bundle.

O segredo compartilhado na conversa deve ser rotacionado no Auth0 e atualizado pelo responsável diretamente no ambiente. A confirmação real do SSO depende dessa configuração externa; os testes de navegador utilizaram provedor sintético isolado, sem se passarem por autenticação real no tenant.

No Auth0, configure o callback `<origem>/auth/callback`, as origens da aplicação e a conexão Google. Para preservar o formulário existente de e-mail/senha, a conexão de banco e o grant Password Realm devem estar habilitados para essa aplicação confiável. Caso não estejam, a operação retorna erro; não há aprovação automática de login. Referências: [PKCE](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce), [Password Realm](https://auth0.com/docs/get-started/authentication-and-authorization-flow/resource-owner-password-flow).

Em `PUBLIC_DEMO_MODE=true`, a API demonstrativa continua pública e usa dados sintéticos. Com Auth0 configurado e modo público desativado, HTTP e WebSocket exigem sessão confirmada pelo servidor ou Bearer do provedor. O perfil selecionado na tela não concede privilégios. Alterações persistentes de regras no modo privado continuam exigindo `X-Admin-Token`; não foi implementado um cadastro novo de permissões ou multiempresa.

## Verificação e execução

Os testes de integração estão em `backend/tests/test_portal_integration.py` e `frontend/scripts/test_auth.cjs`. O pacote restrito inclui o módulo Auth0, gerador e callback; não depende da pasta de laboratório `login/` para iniciar.

Para inspecionar a interface local com dados e provedor sintéticos isolados, execute a partir da raiz do repositório: `python Codex/antecipe/qa/serve_portal_review.py --stub-auth --port 8015`. Esse stub existe somente no servidor de revisão, exige flag explícita e escuta apenas loopback; não é carregado no aplicativo nem incluído no pacote de publicação.

O build foi conferido na árvore de dependências controlada já existente, sem novas dependências de runtime. A instalação limpa das versões do manifesto não foi revalidada nesta integração.

## Publicação autorizada

Em24/10/2026, a pedido do usuário, a integração foi enviada à main (25c2761) e à Vercel (dpl_BNuMdSCHGeZ73nheEL4X1KkoXffR, READY). Frontend final, auth/config, callback e APIs foram conferidos no domínio público. Credenciais e tenant não foram alterados; login com conta real ainda não foi concluído na verificação.

## Ajustes para uso operacional — 24/10/2026

- Credenciais e título individual iniciam vazios. Os atalhos de homologação, casos de teste, indicador Motor Ativo e botão de sincronização foram retirados. XML incompleto não recebe valores fictícios. CSV completo usa a mesma apresentação secundária das outras exportações.
- Simular Impacto limpa resultados anteriores e sinaliza OK ou Erro. Políticas podem receber nome, ser salvas como novas opções e alternadas pelo seletor Minhas políticas salvas; padrão é uma opção separada.
- Decisão de persistência: o SQLite efêmero não atende salvar por conta; localStorage não fornece persistência entre dispositivos. Usamos app_metadata do Auth0 já existente, acessado somente pelo backend com Management API. Não foi adicionado banco/serviço/dependência. Cada opção imutável ocupa chave independente e a seleção tem chave própria. Alterações em duas abas não sobrescrevem outras opções; seleções concorrentes seguem a última gravação confirmada. O limite operacional é 20 opções/conta, configuração até12KB, nome até100 caracteres; o limite por contagem não é transacional entre instâncias.
- Identidade vem de sessão/Bearer verificado em userinfo. IDs do cliente não concedem acesso a opções de outra conta. Necessita AUTH0_MANAGEMENT_API_CLIENT_ID/SECRET com read:users e update:users_app_metadata. Falhas remotas não simulam salvamento: retornam erro explícito. Listagem e regras pessoais usam no-store.
- Referência do provedor: https://auth0.github.io/auth0.net/api/Auth0.ManagementApi.UsersClient.html (PATCH mescla metadados no primeiro nível). Chaves independentes preservam campos de outros aplicativos. Reverter consiste em selecionar padrão; opções existentes são preservadas, sem migração destrutiva.
- A política selecionada alimenta CSV, JSON individual, baseline What-if e WebSocket. Uma cópia é capturada por lote, com hash da configuração efetiva; trocar a seleção não altera análises concluídas/em andamento. A versão do banco identifica o regulamento base.
- PDF usa marca Kanastra/Antecipe, indicadores financeiros, referência da simulação, data-base, gráficos reais, regras e hash. Amostra sintética renderizada e inspecionada:4páginas/9046bytes, sem páginas vazias. Arquivo de inspeção local fica em .data/pdf-review/executivo.pdf, não enviado ao Git.
- Verificação de permissões reais via vercel env run foi inconclusiva: a CLI listou as seis chaves Auth0, mas entregou valores vazios ao processo local inclusive para as credenciais de login que funcionam no runtime. Não é evidência de ausência em produção. Não foram impressos valores/tokens; o teste com conta real permanece pendente. Testes de isolamento e persistência usam provedor sintético remoto em memória, sem alegar garantia observada de persistência real após restart.
