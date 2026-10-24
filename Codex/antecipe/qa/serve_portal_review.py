"""Inspecao local isolada. Provedor sintetico somente com --stub-auth e loopback."""
import argparse
import os
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stub-auth', action='store_true')
    parser.add_argument('--port', type=int, default=8015)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project))
    with tempfile.TemporaryDirectory(prefix='antecipe-portal-review-') as temp:
        os.environ['DATABASE_URL'] = f"sqlite:///{(Path(temp)/'review.db').as_posix()}"
        os.environ['PUBLIC_DEMO_MODE'] = 'true'
        os.environ['ENABLE_DEMO_CADASTRO'] = 'true'
        from backend.vercel_app import app
        if args.stub_auth:
            from backend.api import auth_routes
            auth_routes.config = lambda: {'domain': 'review.invalid', 'client_id': 'review-public', 'client_secret': '', 'connection': 'review'}
            def synthetic_provider(cfg, path, body=None, token=None):
                if path == 'userinfo':
                    return {'sub': 'auth0|review', 'name': 'Pessoa de teste', 'email': 'qa@example.invalid'}
                if path == 'dbconnections/signup':
                    return {'_id': 'review'}
                if body.get('password') != 'review-password':
                    auth_routes.fail('AUTH0_AUTENTICACAO_RECUSADA', 'Credenciais de teste inválidas.')
                return {'access_token': 'review-opaque-token', 'expires_in': 600}
            auth_routes.provider = synthetic_provider
            from backend.api import policy_routes
            import copy
            os.environ['AUTH0_MANAGEMENT_API_CLIENT_ID'] = 'synthetic-review'
            metadata = {}
            def synthetic_management(subject, patch=None):
                current = metadata.setdefault(subject, {})
                if patch is not None:
                    current.update(copy.deepcopy(patch))
                return copy.deepcopy(current)
            policy_routes.management = synthetic_management
        from fastapi.staticfiles import StaticFiles
        import mimetypes
        mimetypes.add_type('application/javascript', '.js')
        mimetypes.add_type('text/css', '.css')
        app.mount('/', StaticFiles(directory=project/'frontend/dist', html=True), name='review-frontend')
        import uvicorn
        uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)


if __name__ == '__main__':
    main()
