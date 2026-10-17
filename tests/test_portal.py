import json

import httpx
import pytest
from fastapi.testclient import TestClient

from agentfence.app import create_app as gateway_app
from demo.chat_runner import create_app as runner_app
from demo.gemini_agent import GeminiAdapter
from demo.openai_agent import run_agent
from portal.app import create_app as portal_app
from portal.auth import password_record

ROLES = ['analyst', 'responder', 'reviewer']
TOKENS = {r: r + '-private-' + 'x'*40 for r in ROLES}
PASSWORDS = {r: 'unique-password-for-' + r for r in ROLES}
HEADERS = {'Origin': 'http://127.0.0.1:8001', 'X-AgentFence': 'portal'}
SHARED = 'private-runner-secret-' + 'z'*40


def relay(client):
    def handle(request):
        response = client.request(request.method, request.url.path,
                                  content=request.content, headers=dict(request.headers))
        return httpx.Response(response.status_code, content=response.content,
                              headers={'content-type': 'application/json'})
    return httpx.MockTransport(handle)


@pytest.fixture
def system(tmp_path):
    gateway = TestClient(gateway_app(tmp_path/'db', TOKENS))
    calls = []

    def execute(body):
        calls.append(body)
        def model(request):
            payload = json.loads(request.content)
            if payload['messages'][-1]['role'] == 'tool':
                return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
                    'message': {'role': 'assistant', 'content': 'Demo task complete.'}}]})
            sensitive = body.prompt == 'disable'
            tool = 'disable_access_key' if sensitive else 'get_asset_metadata'
            args = {'tenant_id': 'tenant-a', 'case_id': 'case-1'}
            args.update({'key_id': 'key-1', 'reason': 'suspected_compromise'} if sensitive
                        else {'asset_id': 'asset-2' if body.prompt == 'restricted' else 'asset-1'})
            return httpx.Response(200, json={'choices': [{'finish_reason': 'tool_calls',
                'message': {'role': 'assistant', 'tool_calls': [{'id': 'call-1', 'type': 'function',
                    'function': {'name': 'propose_tool', 'arguments': json.dumps({
                        'tool': tool, 'arguments_json': json.dumps(args)})}}]}}]})
        with httpx.Client(base_url='https://generativelanguage.googleapis.com/v1beta/openai/',
                          transport=httpx.MockTransport(model)) as provider, \
             httpx.Client(base_url='http://gateway:8000', transport=relay(gateway),
                          headers={'Authorization': 'Bearer ' + body.token}) as gw:
            return run_agent(GeminiAdapter(provider), gw, model='offline',
                             task_id=body.task, prompt=body.prompt)
    runner = TestClient(runner_app({'runner_secret': SHARED}, execute=execute))
    config = {'tokens': TOKENS, 'runner_secret': SHARED,
              'accounts': {r: password_record(PASSWORDS[r]) for r in ROLES}}
    now = [1000]
    portal = TestClient(portal_app(config, relay(gateway), relay(runner), clock=lambda: now[0]),
                        base_url='http://127.0.0.1:8001', headers=HEADERS)
    return portal, gateway, runner, calls, now


def login(portal, role):
    response = portal.post('/api/login', json={'username': role, 'password': PASSWORDS[role]})
    assert response.status_code == 200
    return response


def test_cookie_and_read_roundtrip(system):
    portal, _, _, calls, _ = system
    cookie = login(portal, 'analyst').headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie
    assert all(token not in cookie for token in TOKENS.values())
    result = portal.post('/api/chat', json={'prompt': 'read'})
    assert result.status_code == 200
    assert result.json()['events'][0]['status'] == 'executed'
    assert calls[0].token == TOKENS['analyst']
    assert calls[0].task == 'investigation-1'
    assert TOKENS['analyst'] not in result.text
    assert portal.get('/api/requests').json()[0]['owner'] == 'analyst'


def test_restricted_resource_blocked(system):
    portal, _, _, _, _ = system
    login(portal, 'analyst')
    result = portal.post('/api/chat', json={'prompt': 'restricted'}).json()
    assert result['status'] == 'denied'
    assert result['events'][0]['reason'] == 'resource_not_in_scope'


@pytest.mark.parametrize('approve', [True, False])
def test_exact_review_and_audit_end_to_end(system, approve):
    portal, gateway, _, calls, _ = system
    login(portal, 'responder')
    result = portal.post('/api/chat', json={'prompt': 'disable'}).json()
    assert result['status'] == 'pending'
    event = result['events'][0]
    payload = {'approve': approve, 'request_digest': event['request_digest']}
    assert portal.post('/api/review/'+event['request_id'], json=payload).status_code == 403
    login(portal, 'reviewer')
    assert portal.post('/api/chat', json={'prompt': 'read'}).status_code == 403
    assert len(calls) == 1
    wrong = {**payload, 'request_digest': '0'*64}
    assert portal.post('/api/review/'+event['request_id'], json=wrong).status_code == 409
    response = portal.post('/api/review/'+event['request_id'], json=payload)
    assert response.json()['status'] == ('executed' if approve else 'rejected')
    assert portal.post('/api/review/'+event['request_id'], json=payload).status_code == 409
    audit = portal.get('/api/audit').json()
    assert audit[0]['event'] == ('executed' if approve else 'rejected')
    with gateway.app.state.gateway.store.connect() as c:
        assert c.execute("SELECT value FROM resources WHERE id='key-1'").fetchone()[0] == ('disabled' if approve else 'active')


def test_login_logout_expiry_and_throttle(system):
    portal, _, _, _, now = system
    assert portal.get('/api/requests').status_code == 401
    login(portal, 'analyst')
    assert portal.get('/api/audit').status_code == 403
    portal.post('/api/logout', json={})
    assert portal.get('/api/session').status_code == 401
    login(portal, 'analyst')
    now[0] += 8*3600+1
    assert portal.get('/api/session').status_code == 401
    for _ in range(5):
        assert portal.post('/api/login', json={'username': 'reviewer', 'password': 'bad'}).status_code == 401
    assert portal.post('/api/login', json={'username': 'reviewer', 'password': 'bad'}).status_code == 429


def test_csrf_unknown_fields_and_secret_redaction(system):
    portal, _, runner, calls, _ = system
    assert portal.post('/api/login', headers={'Origin': 'http://evil.example'},
                       json={'username': 'analyst', 'password': PASSWORDS['analyst']}).status_code == 403
    login(portal, 'analyst')
    result = portal.post('/api/chat', json={'prompt': 'read', 'role': 'reviewer', 'token': 'private-supplied-token'})
    assert result.status_code == 422
    assert 'private-supplied-token' not in result.text
    assert not calls
    response = runner.post('/run', json={'prompt': 'read'})
    assert response.status_code == 401
    response = runner.post('/run', headers={'Authorization': 'Bearer '+SHARED},
                           json={'prompt': 'read', 'token': TOKENS['reviewer'], 'task': 'bogus'})
    assert response.status_code == 422
    assert TOKENS['reviewer'] not in response.text
    assert portal.post('/api/chat', content='x'*20001).status_code == 413
    assert portal.get('/', headers={'Host': 'evil.example'}).status_code == 400


def test_runner_busy_and_failure_unlock():
    import threading
    entered, release = threading.Event(), threading.Event()
    def execute(body):
        entered.set()
        release.wait(5)
        return {'status': 'completed', 'events': []}
    client = TestClient(runner_app({'runner_secret': SHARED}, execute=execute))
    args = {'headers': {'Authorization': 'Bearer '+SHARED},
            'json': {'prompt':'read','token':TOKENS['analyst'],'task':'investigation-1'}}
    result = []
    worker = threading.Thread(target=lambda: result.append(client.post('/run', **args)))
    worker.start()
    try:
        assert entered.wait(3)
        assert client.post('/run', **args).status_code == 429
    finally:
        release.set()
        worker.join(5)
    assert result[0].status_code == 200
    assert client.post('/run', **args).status_code == 200
