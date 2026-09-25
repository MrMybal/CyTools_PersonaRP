"""A real MCP session over stdio: list the tools, call operations, read their results.

Operations are asynchronous over MCP: a call returns a job descriptor and the client polls
cy_get_job, exactly as an AI client would. Nothing here is simulated.

Run: runtime/python/Scripts/python.exe app/tests/acceptance_mcp.py
Writes data/reports/mcp-acceptance.json.
"""
import asyncio
import json
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
sys.path.insert(0, str(APP))

from mcp import ClientSession, StdioServerParameters               # noqa: E402
from mcp.client.stdio import stdio_client                          # noqa: E402

DONE = ('Completed', 'Failed', 'Cancelled')


async def _payload(session, name, parameters):
    # Business operations take their arguments under "parameters"; the cy_* protocol tools
    # take theirs directly.
    arguments = parameters if name.startswith('cy_') else {'parameters': parameters}
    result = await session.call_tool(name, arguments)
    if result.isError:
        raise RuntimeError('%s: %s' % (name, result.content[0].text))
    return json.loads(result.content[0].text)


async def run(session, operation, parameters, timeout=600):
    """Call an operation and wait for its job, the way a real client does."""
    job = await _payload(session, 'op_' + operation, parameters)
    if 'jobId' not in job:
        return job
    deadline = time.monotonic() + timeout
    while job['state'] not in DONE:
        if time.monotonic() > deadline:
            raise TimeoutError(operation + ' timed out')
        await asyncio.sleep(0.2)
        job = await _payload(session, 'cy_get_job', {'jobId': job['jobId']})
    if job['state'] != 'Completed':
        raise RuntimeError('%s: %s' % (operation, json.dumps(job.get('error'))))
    return job['outputs']


async def main():
    server = StdioServerParameters(
        command=str(ROOT / 'runtime/python/Scripts/python.exe'),
        args=[str(APP / 'tool.py'), 'mcp'], cwd=str(ROOT))
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = sorted(tool.name for tool in listed.tools)

            personas = (await run(session, 'list_personas', {}))['personas']
            target = personas[0]['id'] if personas else ''
            preview = await run(session, 'preview_prompt',
                                {'persona_id': target, 'text': 'Bonjour, qui etes-vous ?'})
            sheet = await run(session, 'get_persona', {'persona_id': target})
            # The headline capability, over the same transport an AI client would use.
            reply = await run(session, 'chat',
                              {'persona_id': target, 'save': False,
                               'text': 'En une phrase : que gardez-vous sous le plancher ?'})

    report = {
        'date': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'transport': 'MCP over stdio, real client session',
        'toolCount': len(names),
        'operationTools': [n for n in names if n.startswith('op_')],
        'protocolTools': [n for n in names if n.startswith('cy_')],
        'list_personas': personas,
        'get_persona': {'id': sheet['persona']['id'], 'name': sheet['persona']['name'],
                        'world': (sheet.get('world') or {}).get('name', ''),
                        'revision': sheet['persona']['revision'],
                        'visualTags': sheet['persona']['appearance']['visual_tags']},
        'chat': {'dialogue': reply['dialogue'], 'seconds': reply['seconds'],
                 'sceneBeat': (reply.get('scene') or {}).get('beat', ''),
                 'imagePrompt': (reply.get('prompts') or {}).get('image_prompt', ''),
                 'annotations': reply.get('annotations', []),
                 'device': reply['context'].get('device'),
                 'model': reply['context'].get('model')},
        'preview_prompt': {
            'promptCharacters': preview['context']['promptCharacters'],
            'droppedSections': preview['context']['droppedSections'],
            'systemPromptExcerpt': preview['messages'][0]['content'][:600],
        },
    }
    output = ROOT / 'data/reports/mcp-acceptance.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('tools exposed:', len(names),
          '(%d operations, %d protocol)' % (len(report['operationTools']),
                                            len(report['protocolTools'])))
    print('characters:', [p['id'] for p in personas])
    print('sheet read over MCP:', report['get_persona']['name'],
          'revision', report['get_persona']['revision'])
    print('prompt characters:', report['preview_prompt']['promptCharacters'])
    print('chat over MCP (%ss, %s/%s):' % (report['chat']['seconds'], report['chat']['model'],
                                           report['chat']['device']))
    print('  ', ' '.join(report['chat']['dialogue'][:200].split()))
    print('   scene beat:', report['chat']['sceneBeat'])
    print('report:', output)


if __name__ == '__main__':
    asyncio.run(main())
