"""Model load, embedding, indexing and retrieval must work with outbound network blocked."""
import socket

import pytest

from deal_prep import index

LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def test_pipeline_runs_with_network_blocked(monkeypatch, tmp_path, chunks):
    attempts = []
    real_connect = socket.socket.connect
    real_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in LOOPBACK:
            attempts.append(("connect", host))
            raise OSError(f"network blocked by test: {host}")
        return real_connect(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host not in LOOPBACK and host is not None:
            attempts.append(("dns", host))
            raise socket.gaierror(f"DNS blocked by test: {host}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    monkeypatch.setattr(index, "_model", None)  # force a fresh model load under the block

    try:
        index.build_index(chunks, chroma_dir=tmp_path)
    except index.EmbeddingModelUnavailable as e:
        pytest.skip(f"cached embedding model unavailable: {e}")
    results = index.query("Engineering Vault price", k=3, chroma_dir=tmp_path)

    assert results, "query returned nothing"
    assert attempts == [], f"outbound network attempted: {attempts}"
