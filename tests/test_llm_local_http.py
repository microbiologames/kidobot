"""Verifie le backend local contre un faux llama-server (SSE compatible OpenAI)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from kidobot import llm
from kidobot.config import LlmLocal


class FauxLlamaServer(BaseHTTPRequestHandler):
    MORCEAUX = ["Le ciel ", "est bleu ", "a cause de la lumiere."]

    def do_GET(self):  # noqa: N802 - impose par BaseHTTPRequestHandler
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def do_POST(self):  # noqa: N802
        longueur = int(self.headers.get("Content-Length", 0))
        self.corps = json.loads(self.rfile.read(longueur))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for morceau in self.MORCEAUX:
            evenement = {"choices": [{"delta": {"content": morceau}}]}
            self.wfile.write(f"data: {json.dumps(evenement)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def log_message(self, *args):
        pass


@pytest.fixture()
def serveur():
    srv = HTTPServer(("127.0.0.1", 0), FauxLlamaServer)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_sante_et_streaming(serveur):
    backend = llm.LlmLocalHttp(LlmLocal(url=serveur))
    assert backend.disponible()
    assert "".join(backend.repondre("systeme", "pourquoi ?")) == (
        "Le ciel est bleu a cause de la lumiere."
    )


def test_bascule_si_le_serveur_local_tombe(serveur):
    local = llm.LlmLocalHttp(LlmLocal(url="http://127.0.0.1:1", timeout_s=1))
    distant = llm.LlmLocalHttp(LlmLocal(url=serveur))
    auto = llm.LlmAuto(local, distant)
    assert "ciel" in "".join(auto.repondre("s", "q"))
    assert auto.dernier_utilise == "claude"
