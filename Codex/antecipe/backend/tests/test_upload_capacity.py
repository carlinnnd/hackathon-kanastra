"""Frames maiores preservam negociação, confirmação e limite por mensagem."""
from backend.config import settings
from backend.tests.test_result_reporting import isolated, lote


def test_larger_negotiated_frame_and_oversize_rejection(isolated):
    _, client, _ = isolated
    text = lote([{} for _ in range(2500)]).encode()
    assert 256 * 1024 < len(text) <= settings.STREAM_CHUNK_BYTES
    with client.websocket_connect('/api/simulations/stream') as ws:
        ws.send_json({'type':'start','filename':'lote.csv','size_bytes':len(text),'protocol_version':1})
        ready=ws.receive_json()
        assert ready['chunk_bytes'] == 768 * 1024
        assert ready['window_bytes'] == 12 * 1024 * 1024
        ws.send_bytes(text)
        while True:
            msg=ws.receive_json()
            assert msg['type'] != 'error'
            if msg['type']=='ack':
                assert msg['received_bytes']==len(text);break
        ws.send_json({'type':'finish'})
        while True:
            msg=ws.receive_json()
            assert msg['type'] != 'error'
            if msg['type']=='complete':break
        assert msg['simulation']['total_itens']==2500
        assert msg['simulation']['aprovados']+msg['simulation']['recusados']==2500
        ws.send_json({'type':'close'})
    with client.websocket_connect('/api/simulations/stream') as ws:
        ws.send_json({'type':'start','filename':'lote.csv','size_bytes':settings.STREAM_CHUNK_BYTES+1,'protocol_version':1})
        assert ws.receive_json()['type']=='ready'
        ws.send_bytes(b' '*(settings.STREAM_CHUNK_BYTES+1))
        while True:
            msg=ws.receive_json()
            if msg['type']=='error':break
        assert msg.get('codigo')


def test_cursor_reader_preserves_multiline_csv_across_chunks():
    import asyncio
    import csv
    import io
    from backend.application.stream_upload import BoundedStreamTextIO
    text = 'nome;valor\r\n"Razão\nSocial";10,00\r\nÚltima;20,00'
    async def run():
        queue = asyncio.Queue()
        for chunk in [text[:9], text[9:19], text[19:31], text[31:]]:
            await queue.put(chunk)
        await queue.put(None)
        reader = BoundedStreamTextIO(queue, asyncio.get_running_loop())
        return await asyncio.to_thread(lambda: list(csv.reader(reader, delimiter=';')))
    assert asyncio.run(run()) == list(csv.reader(io.StringIO(text), delimiter=';'))
