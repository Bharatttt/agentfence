import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from agentfence.app import create_app
from demo.gemini_agent import GeminiAdapter
from demo.openai_agent import run_agent

TOKENS = {r: r + '-' + 't' * 40 for r in ['analyst', 'responder', 'reviewer']}


def tool_message(tool='get_asset_metadata', **args):
    return {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': 'call_1', 'type': 'function', 'function': {
            'name': 'propose_tool', 'arguments': json.dumps({
                'tool': tool, 'arguments_json': json.dumps({
                    'tenant_id': 'tenant-a', 'case_id': 'case-1', **args})})},
         'extra_content': {'google': {'thought_signature': 'synthetic-signature'}}}]}


def execute(tmp_path, responses, role='analyst', task='investigation-1'):
    requests = []
    def transport(request):
        assert request.url.host == 'generativelanguage.googleapis.com'
        assert request.url.path == '/v1beta/openai/chat/completions'
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=responses[len(requests)-1])
    app = create_app(tmp_path / 'db', TOKENS)
    with httpx.Client(base_url='https://generativelanguage.googleapis.com/v1beta/openai/',
                      transport=httpx.MockTransport(transport)) as provider, \
         TestClient(app, headers={'Authorization': 'Bearer ' + TOKENS[role]}) as gateway:
        result = run_agent(GeminiAdapter(provider), gateway, model='offline-gemini',
                           task_id=task, prompt='Inspect asset-1.')
    return result, requests, app.state.gateway


def response(message, finish='tool_calls'):
    return {'choices': [{'message': message, 'finish_reason': finish}]}


def test_gemini_roundtrip_preserves_signature(tmp_path):
    message = tool_message(asset_id='asset-1')
    result, sent, _ = execute(tmp_path, [response(message), response({
        'role': 'assistant', 'content': 'Metadata read completed.'}, 'stop')])
    assert result['status'] == 'completed'
    assert result['events'][0]['decision'] == 'allow'
    assert sent[1]['messages'][-2] == message
    assert sent[1]['messages'][-1]['role'] == 'tool'
    assert 'asset-1' in sent[1]['messages'][-1]['content']
    assert all(token not in json.dumps(sent) for token in TOKENS.values())


@pytest.mark.parametrize('message', [tool_message(asset_id='asset-2'),
    tool_message(asset_id='asset-1', bypass_policy=True), tool_message('shell', command='x'),
    tool_message('read_document', document_id='poisoned-1'),
    tool_message('export_asset_report', asset_id='asset-1', destination='https://unapproved.example')])
def test_gemini_attacks_denied(tmp_path, message):
    result, sent, _ = execute(tmp_path, [response(message)])
    assert result['events'][0]['decision'] == 'deny'
    assert len(sent) == 1


def test_gemini_sensitive_action_pauses(tmp_path):
    result, sent, gateway = execute(tmp_path, [response(tool_message('disable_access_key',
        key_id='key-1', reason='suspected_compromise'))], 'responder', 'response-1')
    assert result['status'] == 'pending'
    assert len(sent) == 1
    with gateway.store.connect() as c:
        assert c.execute("SELECT value FROM resources WHERE id='key-1'").fetchone()[0] == 'active'


@pytest.mark.parametrize('data', [{'choices': []}, response(tool_message(asset_id='asset-1'), 'length'),
    response({'role': 'assistant', 'content': None}, 'content_filter')])
def test_incomplete_gemini_response_never_executes(tmp_path, data):
    result, _, gateway = execute(tmp_path, [data])
    assert result['status'] == 'model_incomplete'
    with gateway.store.connect() as c:
        assert c.execute('SELECT count(*) FROM requests').fetchone()[0] == 0


def test_parallel_gemini_calls_never_execute(tmp_path):
    message = tool_message(asset_id='asset-1')
    other = copy.deepcopy(message['tool_calls'][0])
    other['id'] = 'call_2'
    message['tool_calls'].append(other)
    result, _, gateway = execute(tmp_path, [response(message)])
    assert result['status'] == 'invalid_model_call'
    with gateway.store.connect() as c:
        assert c.execute('SELECT count(*) FROM requests').fetchone()[0] == 0


def test_quota_failure_no_retry():
    count = []
    def fail(request):
        count.append(1)
        return httpx.Response(429, json={'error': {'message': 'synthetic quota limit'}})
    with httpx.Client(base_url='https://generativelanguage.googleapis.com/v1beta/openai/',
                      transport=httpx.MockTransport(fail)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            GeminiAdapter(client).post('/v1/responses', json={
                'instructions': 'test', 'input': [], 'model': 'offline', 'max_output_tokens': 1024,
                'tools': [{'name': 'propose_tool', 'description': 'test', 'parameters': {}}]})
    assert len(count) == 1
