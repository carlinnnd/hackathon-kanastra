# Integração do frontend final com o backend

Base: `origin/main` em `35579f7`. A interface do cliente foi preservada: CSS inalterado e JSX visual do login idêntico. Foram corrigidos os vínculos de sessão, API e pacote estático; não houve deploy.

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
