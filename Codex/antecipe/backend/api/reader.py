class LimitedReader(io.RawIOBase):
    """Wrapper para limitar a contagem de bytes lidos do stream em tempo de execução."""
    def __init__(self, stream, max_bytes: int):
        self.stream = stream
        self.max_bytes = max_bytes
        self.bytes_read = 0

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:
        data = self.stream.read(len(b))
        if not data:
            return 0
        n = len(data)
        self.bytes_read += n
        if self.bytes_read > self.max_bytes:
            raise HTTPException(
                status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={"codigo": "ARQUIVO_MUITO_GRANDE", "mensagem": f"O tamanho do arquivo excede o limite máximo permitido de {self.max_bytes} bytes."}
            )
        b[:n] = data
        return n
