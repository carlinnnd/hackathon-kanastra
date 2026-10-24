"""Verifica permissões de políticas sem imprimir credenciais, tokens ou perfis."""
import json
import os
import urllib.request
import urllib.error

required = {'read:users', 'update:users_app_metadata'}
domain = (os.getenv('AUTH0_DOMAIN') or os.getenv('AUTH0_ISSUER_BASE_URL') or '').removeprefix('https://').rstrip('/')
client = os.getenv('AUTH0_MANAGEMENT_API_CLIENT_ID')
secret = os.getenv('AUTH0_MANAGEMENT_API_CLIENT_SECRET')
if not (domain and client and secret):
    print(json.dumps({'local_env_values_available': False, 'present_nonempty': {k: bool(os.getenv(k)) for k in os.environ if k.startswith('AUTH0_')}})); raise SystemExit(1)
body = {'grant_type': 'client_credentials', 'client_id': client, 'client_secret': secret,
    'audience': f'https://{domain}/api/v2/', 'scope': ' '.join(sorted(required))}
request = urllib.request.Request(f'https://{domain}/oauth/token', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(request, timeout=15) as response:
        token = json.load(response)
    allowed = set(token.get('scope', '').split())
    print(json.dumps({'configured': True, 'required_scopes_granted': required.issubset(allowed)}))
    raise SystemExit(0 if required.issubset(allowed) else 1)
except (OSError, ValueError):
    print(json.dumps({'configured': True, 'required_scopes_granted': False, 'reason': 'provider_rejected_or_unavailable'}))
    raise SystemExit(1)
