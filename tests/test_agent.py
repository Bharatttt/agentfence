import json

import httpx
import pytest
from fastapi.testclient import TestClient

from agentfence.app import create_app
from demo.openai_agent import run_agent

TOKENS = {r: r + '-' + 't' * 40 for r in ['analyst', 'responder', 'reviewer']}


def action(tool='get_asset_metadata', **args):
    return {'type': 'function_call', 'name': 'propose_tool', 'call_id': 'call_1',
            'arguments': json.dumps({'tool': tool, 'arguments_json': json.dumps({
                'tenant_id': 'tenant-a', 'case_id': 'case-1', **args})})}


def execute(tmp_path, outputs, role='analyst', task='investigation-1', turns=4):
    sent = []
    def respond(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={'status': 'completed', 'output': outputs[len(sent)-1]})
    app = create_app(tmp_path / 'db.sqlite', TOKENS)
    with TestClient(app, headers={'Authorization': 'Bearer ' + TOKENS[role]}) as gateway, \
         httpx.Client(base_url='https://api.openai.com', transport=httpx.MockTransport(respond)) as model:
        result = run_agent(model, gateway, model='offline-test', task_id=task,
                           prompt='Inspect the assigned incident.', max_turns=turns)
    return result, sent, app.state.gateway


def test_model_read_result_roundtrip(tmp_path):
    result, sent, _ = execute(tmp_path, [[action(asset_id='asset-1')], [
        {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Read completed.'}]}]])
    assert result['status'] == 'completed'
    assert result['events'][0]['decision'] == 'allow'
    assert sent[1]['input'][-1]['type'] == 'function_call_output'
    assert 'asset-1' in sent[1]['input'][-1]['output']
    assert all(s['store'] is False and s['parallel_tool_calls'] is False for s in sent)
    assert not any(token in json.dumps(sent) for token in TOKENS.values())


@pytest.mark.parametrize('call', [action(asset_id='asset-2'),
    action(asset_id='asset-1', bypass_policy=True), action('shell', command='anything'),
    action('read_document', document_id='poisoned-1'),
    action('export_asset_report', asset_id='asset-1', destination='https://unapproved.example')])
def test_model_attack_stops_at_gateway(tmp_path, call):
    result, sent, _ = execute(tmp_path, [[call]])
    assert result['events'][0]['decision'] == 'deny'
    assert len(sent) == 1


def test_approval_pauses_without_execution(tmp_path):
    result, sent, gateway = execute(tmp_path, [[action('disable_access_key', key_id='key-1',
        reason='suspected_compromise')]], 'responder', 'response-1')
    assert result['status'] == 'pending'
    assert len(sent) == 1
    with gateway.store.connect() as c:
        assert c.execute("SELECT value FROM resources WHERE id='key-1'").fetchone()[0] == 'active'


@pytest.mark.parametrize('outputs', [
    [[{'type': 'function_call', 'name': 'shell'}]],
    [[action(asset_id='asset-1'), action(asset_id='asset-2')]],
    [[{'type': 'function_call', 'name': 'propose_tool', 'arguments': '{bad'}]],
])
def test_malformed_calls_never_execute(tmp_path, outputs):
    result, _, gateway = execute(tmp_path, outputs)
    assert result['status'] == 'invalid_model_call'
    with gateway.store.connect() as c:
        assert c.execute('SELECT count(*) FROM requests').fetchone()[0] == 0


def test_duplicate_is_not_reexecuted(tmp_path):
    result, _, _ = execute(tmp_path, [[action(asset_id='asset-1')]] * 2)
    assert result['status'] == 'duplicate_proposal'
    assert len(result['events']) == 1


def test_turn_budget(tmp_path):
    result, sent, _ = execute(tmp_path, [[action(asset_id='asset-1')]], turns=1)
    assert result['status'] == 'turn_limit'
    assert len(sent) == 1


def test_reviewer_not_usable_as_agent(tmp_path):
    with pytest.raises(ValueError, match='never reviewer'):
        execute(tmp_path, [], 'reviewer')


def test_task_cannot_be_spoofed(tmp_path):
    with pytest.raises(ValueError, match='not assigned'):
        execute(tmp_path, [], task='response-1')
