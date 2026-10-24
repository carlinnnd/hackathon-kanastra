"""
Adaptador de streaming e leitor assíncrono com fila limitada (Bounded Queue Reader).
Conecta frames binários WebSocket ao gerador síncrono iterar_csv_recebiveis:
- Mantém fila limitada para controle de backpressure e memória (< 4 MiB buffers).
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
        self.closed_flag = False
        self.aborted = False

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> str:
        if self.aborted:
            raise RuntimeError("Streaming abortado devido a desconexão ou erro do cliente.")

        while not self.buffer and not self.closed_flag and not self.aborted:
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
            self.buffer += chunk

        if self.aborted:
            raise RuntimeError("Streaming abortado devido a desconexão ou erro do cliente.")

        if not self.buffer:
            return ""

        if size is None or size < 0 or size >= len(self.buffer):
            data = self.buffer
            self.buffer = ""
            return data
        else:
            data = self.buffer[:size]
            self.buffer = self.buffer[size:]
            return data

    def readline(self, size: int = -1) -> str:
        if self.aborted:
            raise RuntimeError("Streaming abortado devido a desconexão ou erro do cliente.")

        while "\n" not in self.buffer and not self.closed_flag and not self.aborted:
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
            self.buffer += chunk

        if self.aborted:
            raise RuntimeError("Streaming abortado devido a desconexão ou erro do cliente.")

        if not self.buffer:
            return ""

        pos = self.buffer.find("\n")
        if pos != -1:
            line = self.buffer[:pos + 1]
            self.buffer = self.buffer[pos + 1:]
            return line
        else:
            line = self.buffer
            self.buffer = ""
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
