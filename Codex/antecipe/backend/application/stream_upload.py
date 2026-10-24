"""
Adaptador de streaming e leitor assíncrono com fila limitada (Bounded Queue Reader).
Conecta frames binários WebSocket ao gerador síncrono iterar_csv_recebiveis:
- Mantém fila limitada para controle de backpressure e memória (fila limitada; capacidade negociada pelo servidor).
- Tratamento incremental de decodificação UTF-8 seguro em fronteiras de chunks.
- Aborta leitor em caso de desconexão ou cancelamento sem deadlock via loop.call_soon_threadsafe:
  drena fila ativamente e insere sentinela de forma não-bloqueante.
"""
import asyncio
import codecs
import io
from typing import Iterator, Optional


class BoundedStreamTextIO(io.TextIOBase):
    """
    Simula TextIOBase síncrono alimentado por uma fila assíncrona limitada de chunks decodificados.
    Permite que o parser síncrono csv.reader / iterar_csv_recebiveis execute em thread/worker
    enquanto os frames WebSocket chegam de forma assíncrona.
    """
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self.queue = queue
        self.loop = loop
        self.buffer = ""
        self.position = 0
        self.closed_flag = False
        self.aborted = False

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> str:
        if self.aborted:
            raise RuntimeError("Streaming abortado devido a desconexão ou erro do cliente.")

        while self.position >= len(self.buffer) and not self.closed_flag and not self.aborted:
            future = asyncio.run_coroutine_threadsafe(self.queue.get(), self.loop)
            try:
                chunk = future.result()
            except Exception:
                self.aborted = True
                raise RuntimeError("Fila de streaming interrompida.")

            if self.aborted:
                raise RuntimeError("Streaming abortado devido a desconexão ou erro do cliente.")

            if chunk is None:  # Sinal de EOF (finish)
                self.closed_flag = True
                break
            self.buffer = self.buffer[self.position:] + chunk
            self.position = 0

        if self.aborted:
            raise RuntimeError("Streaming abortado devido a desconexão ou erro do cliente.")

        if self.position >= len(self.buffer):
            return ""

        end = len(self.buffer) if size is None or size < 0 else min(len(self.buffer), self.position + size)
        data = self.buffer[self.position:end]
        self.position = end
        return data

    def readline(self, size: int = -1) -> str:
        if self.aborted:
            raise RuntimeError("Streaming abortado devido a desconexão ou erro do cliente.")

        while self.buffer.find("\n", self.position) == -1 and not self.closed_flag and not self.aborted:
            future = asyncio.run_coroutine_threadsafe(self.queue.get(), self.loop)
            try:
                chunk = future.result()
            except Exception:
                self.aborted = True
                raise RuntimeError("Fila de streaming interrompida.")

            if self.aborted:
                raise RuntimeError("Streaming abortado devido a desconexão ou erro do cliente.")

            if chunk is None:
                self.closed_flag = True
                break
            self.buffer = self.buffer[self.position:] + chunk
            self.position = 0

        if self.aborted:
            raise RuntimeError("Streaming abortado devido a desconexão ou erro do cliente.")

        if self.position >= len(self.buffer):
            return ""

        pos = self.buffer.find("\n", self.position)
        end = pos + 1 if pos != -1 else len(self.buffer)
        if size is not None and size >= 0:
            end = min(end, self.position + size)
        line = self.buffer[self.position:end]
        self.position = end
        return line

    def abort(self):
        """
        Acorda a thread síncrona sem agendar corrotinas em fila cheia:
        Drena a fila com get_nowait() e insere sentinela None com put_nowait()
        através de loop.call_soon_threadsafe.
        """
        self.aborted = True
        self.closed_flag = True

        def _wake_and_drain():
            # Drena a fila para liberar chunks retidos e garantir espaço
            while True:
                try:
                    self.queue.get_nowait()
                except (asyncio.QueueEmpty, Exception):
                    break
            # Insere sentinela para destravar o future.result()
            try:
                self.queue.put_nowait(None)
            except (asyncio.QueueFull, Exception):
                pass

        try:
            self.loop.call_soon_threadsafe(_wake_and_drain)
        except Exception:
            pass
