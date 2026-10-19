from __future__ import annotations

import json
import html
import os
import re
import urllib.error
import urllib.request
import uuid
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse


ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "publicacoes.json"
EXPECTED_OAB = "196088"
EXPECTED_UF = "SP"
DATAJUD_PUBLIC_KEY = os.getenv(
    "DATAJUD_API_KEY",
    "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==",
)
DATAJUD_ALIASES = {
    "TJSP": "api_publica_tjsp",
    "TRT15": "api_publica_trt15",
    "TRT2": "api_publica_trt2",
    "TST": "api_publica_tst",
    "STJ": "api_publica_stj",
    "TRF1": "api_publica_trf1",
    "TRF2": "api_publica_trf2",
    "TRF3": "api_publica_trf3",
    "TRF4": "api_publica_trf4",
    "TRF5": "api_publica_trf5",
    "TRF6": "api_publica_trf6",
}
RUNTIME_CONFIG = {
    "aasp_key": os.getenv("AASP_CHAVE"),
    "aasp_codigo": os.getenv("AASP_CODIGO_PESSOA_ASSOCIADO"),
    "enabled_sources": {"djen": True, "aasp": True, "datajud": False, "dejt": False, "inlabs": False, "deoab": False},
}

SOURCE_CATALOG = [
    {
        "id": "cnj_djen",
        "nome": "CNJ / DJEN",
        "tipo": "api_publica",
        "url": "https://hcomunicaapi.cnj.jus.br",
        "situacao": "documentada_para_validacao",
        "observacao": "Consulta de comunicacoes e cadernos; filtro por OAB precisa ser validado.",
    },
    {
        "id": "datajud",
        "nome": "DataJud",
        "tipo": "api_publica",
        "url": "https://api-publica.datajud.cnj.jus.br",
        "situacao": "integracao_parcial",
        "observacao": "Consulta real por numero de processo retorna capa e movimentacoes; nao e busca direta por OAB.",
    },
    {
        "id": "dejt",
        "nome": "DEJT",
        "tipo": "webservice_wsdl",
        "url": "https://dejt.jt.jus.br/dejt/dejt?wsdl",
        "situacao": "documentada_para_validacao",
        "observacao": "Antes de integrar, validar o servico/WSDL, o formato da consulta e a disponibilidade dos dados.",
    },
    {
        "id": "inlabs",
        "nome": "DOU / INLABS",
        "tipo": "dados_abertos_xml_pdf",
        "url": "https://inlabs.in.gov.br/acessar.php",
        "situacao": "requer_cadastro_ou_download",
        "observacao": "Disponibiliza arquivos XML e PDF diarios; e necessario baixar, ler e filtrar os arquivos pela OAB.",
    },
    {
        "id": "deoab",
        "nome": "DEOAB",
        "tipo": "portal_publico",
        "url": "https://deoab.oab.org.br",
        "situacao": "portal_sem_api_confirmada",
        "observacao": "Portal publico com edicoes e PDFs, mas sem API publica identificada para consumo direto.",
    },
]


def load_publicacoes() -> list[dict]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def clean_html(value: str) -> str:
    value = html.unescape(value or "")
    return re.sub(r"<[^>]+>", " ", value).replace("\\n", " ").strip()


def fetch_djen(oab: str, uf: str, data_inicio: str, data_fim: str) -> dict:
    base = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"
    items = []
    page = 1
    total = None
    while page <= 10:
        query = urlencode({
            "numeroOab": oab,
            "ufOab": uf,
            "dataDisponibilizacaoInicio": data_inicio,
            "dataDisponibilizacaoFim": data_fim,
            "pagina": page,
            "itensPorPagina": 100,
        })
        request = urllib.request.Request(
            f"{base}?{query}",
            headers={"Accept": "application/json", "User-Agent": "PeticionaTestAPI/0.1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return {"fonte": "DJEN", "status": "erro_http", "http_status": exc.code, "items": []}
        except Exception as exc:
            return {"fonte": "DJEN", "status": "indisponivel", "erro": type(exc).__name__, "items": []}

        total = payload.get("count", 0)
        for item in payload.get("items", []):
            items.append({
                "id": f"djen-{item.get('id')}",
                "oab": f"{oab}/{uf}",
                "numero_processo": item.get("numero_processo") or item.get("numeroProcesso"),
                "tribunal": item.get("siglaTribunal"),
                "orgao": item.get("nomeOrgao"),
                "fonte": "DJEN",
                "data_publicacao": item.get("data_disponibilizacao") or item.get("dataDisponibilizacao"),
                "tipo": item.get("tipoComunicacao"),
                "texto": clean_html(item.get("texto", "")),
                "link": item.get("link"),
                "hash": item.get("hash"),
                "status": "pendente_analise",
            })
        if len(payload.get("items", [])) < 100 or len(items) >= total:
            break
        page += 1
    return {
        "fonte": "DJEN",
        "status": "ok",
        "total": total if total is not None else len(items),
        "items": items,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }


def fetch_aasp(data_inicio: str, chave: str | None, codigo_associado: str | None) -> dict:
    if not chave:
        return {
            "fonte": "AASP",
            "status": "credencial_necessaria",
            "mensagem": "Informe AASP_CHAVE fornecida pela AASP para consultar dados reais.",
            "items": [],
        }
    query = {"chave": chave, "data": data_inicio}
    if codigo_associado:
        query["codigoPessoaAssociado"] = codigo_associado
    url = "https://intimacaoapi.aasp.org.br/api/Empresa/intimacao/json?" + urlencode(query)
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "PeticionaTestAPI/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = json.loads(response.read().decode("utf-8"))
        items = raw if isinstance(raw, list) else raw.get("items", raw.get("publicacoes", []))
        return {"fonte": "AASP", "status": "ok", "total": len(items), "items": items}
    except urllib.error.HTTPError as exc:
        return {"fonte": "AASP", "status": "erro_http", "http_status": exc.code, "items": []}
    except Exception as exc:
        return {"fonte": "AASP", "status": "indisponivel", "erro": type(exc).__name__, "items": []}


def fetch_datajud(processo: str, tribunal: str) -> dict:
    """Consulta capa e movimentos de um processo na API publica do DataJud."""
    numero = re.sub(r"\D", "", processo or "")
    sigla = (tribunal or "").upper().replace(" ", "")
    alias = DATAJUD_ALIASES.get(sigla)
    if not alias:
        return {
            "fonte": "DataJud",
            "status": "tribunal_nao_mapeado",
            "processo": numero,
            "tribunal": tribunal,
            "mensagem": "Informe uma sigla de tribunal mapeada para consultar o DataJud.",
            "movimentos": [],
        }
    if len(numero) != 20:
        return {
            "fonte": "DataJud",
            "status": "processo_invalido",
            "processo": numero,
            "tribunal": tribunal,
            "mensagem": "O numero do processo deve conter 20 digitos.",
            "movimentos": [],
        }

    endpoint = f"https://api-publica.datajud.cnj.jus.br/{alias}/_search"
    body = json.dumps({
        "query": {"match": {"numeroProcesso": numero}},
        "size": 1,
    }).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"APIKey {DATAJUD_PUBLIC_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "PeticionaTestAPI/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        status = "credencial_necessaria" if exc.code in {401, 403} else "erro_http"
        return {
            "fonte": "DataJud",
            "status": status,
            "processo": numero,
            "tribunal": tribunal,
            "http_status": exc.code,
            "mensagem": "A chave publica do DataJud foi rejeitada." if status == "credencial_necessaria" else "DataJud retornou erro HTTP.",
            "movimentos": [],
        }
    except Exception as exc:
        return {
            "fonte": "DataJud",
            "status": "indisponivel",
            "processo": numero,
            "tribunal": tribunal,
            "erro": type(exc).__name__,
            "mensagem": "A consulta ao DataJud excedeu o tempo limite ou ficou indisponivel.",
            "movimentos": [],
        }

    hits = payload.get("hits", {}).get("hits", [])
    if not hits:
        return {
            "fonte": "DataJud",
            "status": "sem_resultado",
            "processo": numero,
            "tribunal": tribunal,
            "mensagem": "Processo nao localizado na base publica do DataJud.",
            "movimentos": [],
        }
    source = hits[0].get("_source", {})
    movimentos = source.get("movimentos", []) or []
    movimentos = sorted(movimentos, key=lambda item: item.get("dataHora", ""), reverse=True)
    return {
        "fonte": "DataJud",
        "status": "ok",
        "processo": source.get("numeroProcesso", numero),
        "tribunal": source.get("tribunal", tribunal),
        "grau": source.get("grau"),
        "classe": source.get("classe", {}).get("nome"),
        "orgao_julgador": source.get("orgaoJulgador", {}).get("nome"),
        "ultima_atualizacao": source.get("dataHoraUltimaAtualizacao"),
        "total_movimentos": len(movimentos),
        "movimentos": [
            {
                "data": item.get("dataHora"),
                "nome": item.get("nome"),
                "orgao": item.get("orgaoJulgador", {}).get("nome"),
            }
            for item in movimentos
        ],
    }


def query_real_sources(oab: str, uf: str, params: dict) -> dict:
    today = date.today()
    data_inicio = params.get("data_inicio", (today - timedelta(days=1)).isoformat())
    data_fim = params.get("data_fim", today.isoformat())
    source_results = [fetch_djen(oab, uf, data_inicio, data_fim)]
    if params.get("incluir_aasp", "true").lower() == "true":
        if RUNTIME_CONFIG["enabled_sources"].get("aasp", True):
            source_results.append(fetch_aasp(
                data_inicio,
                RUNTIME_CONFIG.get("aasp_key"),
                RUNTIME_CONFIG.get("aasp_codigo"),
            ))
    items = []
    for result in source_results:
        items.extend(result.get("items", []))
    return {
        "modo": "real",
        "oab": f"{oab}/{uf}",
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "fontes": [{key: value for key, value in result.items() if key != "items"} for result in source_results],
        "items": items,
    }


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.end_headers()
    handler.wfile.write(body)


def serve_file(handler: BaseHTTPRequestHandler, file_name: str, content_type: str) -> None:
    path = ROOT / file_name
    if not path.exists():
        return json_response(handler, 404, {"error": "file_not_found"})
    body = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "PeticionaTestAPI/0.1"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") != "/v1/config":
            return json_response(self, 404, {"error": "not_found"})
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if "aasp_chave" in payload:
                RUNTIME_CONFIG["aasp_key"] = payload["aasp_chave"] or None
            if "aasp_codigo" in payload:
                RUNTIME_CONFIG["aasp_codigo"] = payload["aasp_codigo"] or None
            if isinstance(payload.get("enabled_sources"), dict):
                for key, value in payload["enabled_sources"].items():
                    if key in RUNTIME_CONFIG["enabled_sources"]:
                        RUNTIME_CONFIG["enabled_sources"][key] = bool(value)
            return json_response(self, 200, {
                "saved": True,
                "persisted": False,
                "aasp_configured": bool(RUNTIME_CONFIG.get("aasp_key")),
                "enabled_sources": RUNTIME_CONFIG["enabled_sources"],
            })
        except Exception as exc:
            return json_response(self, 400, {"error": "invalid_config", "message": str(exc)})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        request_id = str(uuid.uuid4())

        try:
            if path == "/health":
                return json_response(self, 200, {
                    "status": "ok",
                    "service": "peticiona-test-api",
                    "mock": True,
                    "request_id": request_id,
                })

            if path in {"", "/", "/dashboard"}:
                return serve_file(self, "dashboard.html", "text/html; charset=utf-8")

            if path == "/dashboard.css":
                return serve_file(self, "dashboard.css", "text/css; charset=utf-8")

            if path == "/dashboard.js":
                return serve_file(self, "dashboard.js", "application/javascript; charset=utf-8")

            if path == "/openapi.json":
                return json_response(self, 200, json.loads((ROOT / "openapi.json").read_text(encoding="utf-8")))

            if path == "/v1/publicacoes":
                return self.list_publicacoes(params, request_id)

            if path.startswith("/v1/publicacoes/"):
                publication_id = path.rsplit("/", 1)[-1]
                return self.get_publicacao(publication_id, request_id)

            if path == "/v1/processos":
                return self.list_processos(params, request_id)

            if path == "/v1/datajud":
                return self.get_datajud(params, request_id)

            if path == "/v1/fontes":
                return self.list_fontes(params, request_id)

            if path == "/v1/config":
                return json_response(self, 200, {
                    "aasp_configured": bool(RUNTIME_CONFIG.get("aasp_key")),
                    "aasp_codigo_configured": bool(RUNTIME_CONFIG.get("aasp_codigo")),
                    "enabled_sources": RUNTIME_CONFIG["enabled_sources"],
                })

            return json_response(self, 404, {
                "error": "not_found",
                "message": "Endpoint nao encontrado",
                "request_id": request_id,
            })
        except Exception as exc:
            return json_response(self, 500, {
                "error": "internal_error",
                "message": str(exc),
                "request_id": request_id,
            })

    def validate_oab(self, params: dict) -> tuple[str | None, str | None]:
        oab = params.get("oab", "").replace(".", "").replace("-", "").strip()
        uf = params.get("uf", "").strip().upper()
        if not oab or not uf:
            return "Informe os parametros oab e uf", None
        if oab != EXPECTED_OAB or uf != EXPECTED_UF:
            return f"OAB de teste nao encontrada: {oab}/{uf}", None
        return None, f"{oab}/{uf}"

    def list_publicacoes(self, params: dict, request_id: str) -> None:
        error, oab = self.validate_oab(params)
        if error:
            return json_response(self, 400, {"error": "invalid_oab", "message": error, "request_id": request_id})

        if params.get("modo", "real").lower() == "real":
            live = query_real_sources(oab[:6], oab[7:], params)
            return json_response(self, 200, {
                "mock": False,
                "fonte": "fontes_reais",
                "oab": live["oab"],
                "data_inicio": live["data_inicio"],
                "data_fim": live["data_fim"],
                "total": len(live["items"]),
                "fontes": live["fontes"],
                "items": live["items"],
                "request_id": request_id,
            })

        items = load_publicacoes()
        status = params.get("status")
        if status:
            items = [item for item in items if item["status"] == status]

        limit = min(max(int(params.get("limit", "20")), 1), 100)
        offset = max(int(params.get("offset", "0")), 0)
        page_items = items[offset:offset + limit]
        return json_response(self, 200, {
            "mock": True,
            "fonte": "dados_de_teste",
            "oab": oab,
            "data_consulta": date.today().isoformat(),
            "total": len(items),
            "offset": offset,
            "limit": limit,
            "items": page_items,
            "request_id": request_id,
        })

    def get_publicacao(self, publication_id: str, request_id: str) -> None:
        item = next((item for item in load_publicacoes() if item["id"] == publication_id), None)
        if not item:
            return json_response(self, 404, {"error": "publication_not_found", "request_id": request_id})
        return json_response(self, 200, {"mock": True, "item": item, "request_id": request_id})

    def list_processos(self, params: dict, request_id: str) -> None:
        error, oab = self.validate_oab(params)
        if error:
            return json_response(self, 400, {"error": "invalid_oab", "message": error, "request_id": request_id})

        mock = params.get("modo", "real").lower() != "real"
        live = None
        if mock:
            items = load_publicacoes()
        else:
            live = query_real_sources(oab[:6], oab[7:], params)
            items = live["items"]
        processes: dict[str, dict] = {}
        for item in items:
            process_number = item.get("numero_processo") or item.get("numeroProcesso")
            if not process_number:
                continue
            process = processes.setdefault(process_number, {
                "numero_processo": process_number,
                "tribunal": item.get("tribunal") or item.get("siglaTribunal"),
                "partes": item.get("partes", []),
                "ultima_publicacao": item.get("data_publicacao") or item.get("dataDisponibilizacao"),
                "publicacoes": 0,
                "status": item.get("status", "pendente_analise"),
            })
            process["publicacoes"] += 1
            publication_date = item.get("data_publicacao") or item.get("dataDisponibilizacao") or ""
            process["ultima_publicacao"] = max(process["ultima_publicacao"] or "", publication_date)

        response = {
            "mock": mock,
            "oab": oab,
            "total": len(processes),
            "items": list(processes.values()),
            "request_id": request_id,
        }
        if live:
            response["fontes"] = live["fontes"]
            response["data_inicio"] = live["data_inicio"]
            response["data_fim"] = live["data_fim"]
        return json_response(self, 200, response)

    def get_datajud(self, params: dict, request_id: str) -> None:
        processo = params.get("processo", "")
        tribunal = params.get("tribunal", "")
        if not processo or not tribunal:
            return json_response(self, 400, {
                "error": "invalid_datajud_query",
                "message": "Informe processo e tribunal.",
                "request_id": request_id,
            })
        result = fetch_datajud(processo, tribunal)
        result["request_id"] = request_id
        return json_response(self, 200, result)

    def list_fontes(self, params: dict, request_id: str) -> None:
        probe = params.get("probe", "false").lower() == "true"
        sources = []
        for source in SOURCE_CATALOG:
            item = dict(source)
            if probe:
                item.update(probe_source(source["url"]))
            sources.append(item)
        return json_response(self, 200, {
            "mock": not probe,
            "fontes": sources,
            "request_id": request_id,
        })


def probe_source(url: str) -> dict:
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "PeticionaTestAPI/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return {"probe": "ok", "http_status": response.status}
    except urllib.error.HTTPError as exc:
        return {"probe": "reachable", "http_status": exc.code}
    except Exception as exc:
        return {"probe": "unavailable", "error": type(exc).__name__}


def main() -> None:
    host = "127.0.0.1"
    port = 8765
    server = ThreadingHTTPServer((host, port), ApiHandler)
    print(f"API de teste em http://{host}:{port}")
    print("OAB de teste: 196088/SP")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando API")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
