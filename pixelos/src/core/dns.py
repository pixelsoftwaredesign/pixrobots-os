# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""dns — Serveur DNS autoritaire PixelOS pour résolution privée.

TLD privé PixelOS : .pxl
Records configurables dans pixelos.yaml → dns.records

Fonctionnalités :
  - Répond aux requêtes A, AAAA, PTR pour le domaine privé
  - Forward les autres requêtes vers un DNS public (8.8.8.8)
  - Cache, logging, statistical queries
  - Mode daemon : écoute UDP, thread pool
"""

import json
import structlog
import socket
import threading
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import dns.message
import dns.name
import dns.query
import dns.flags
import dns.rdatatype
import dns.rdataclass
import dns.resolver
import dns.exception
import dns.rdtypes.IN.A
import dns.rdtypes.ANY.PTR


log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TLD = "pxl"
DEFAULT_PORT = 5300  # non-privileged, éviter conflit mDNS (5353)
DEFAULT_FORWARDER = "8.8.8.8"

DEFAULT_RECORDS = {
    f"pixelos.{DEFAULT_TLD}": "127.0.0.1",
    f"web.{DEFAULT_TLD}": "127.0.0.1",
    f"api.{DEFAULT_TLD}": "127.0.0.1",
    f"mqtt.{DEFAULT_TLD}": "127.0.0.1",
    f"db.{DEFAULT_TLD}": "127.0.0.1",
    f"auth.{DEFAULT_TLD}": "127.0.0.1",
    f"storage.{DEFAULT_TLD}": "127.0.0.1",
}


class PixelDNSServer:
    """Serveur DNS privé PixelOS avec forwarding."""

    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        self.tld = cfg.get("domain", DEFAULT_TLD).rstrip(".").lstrip(".")
        self.port = cfg.get("port", DEFAULT_PORT)
        self.address = cfg.get("address", "0.0.0.0")
        self.forwarder = cfg.get("forwarder", DEFAULT_FORWARDER)

        raw_records = cfg.get("records", {})
        self.records = {}
        for name, ip in {**DEFAULT_RECORDS, **raw_records}.items():
            qname = name if name.endswith(".") else name + "."
            self.records[qname] = ip

        self._sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.stats = {"queries": 0, "answered": 0, "forwarded": 0, "errors": 0}

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            log.warning("DNS deja en cours")
            return
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.bind((self.address, self.port))
        except PermissionError:
            log.error("Permission refusee pour le port DNS", port=self.port)
            raise
        except OSError as e:
            log.error("Impossible de lier le port DNS", port=self.port, error=str(e))
            self._running = False
            raise
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        log.info("DNS demarre", addr=self.address, port=self.port, tld=self.tld)

    def stop(self) -> None:
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        log.info("DNS arrete")

    def _serve(self) -> None:
        while self._running:
            try:
                data, addr = self._sock.recvfrom(4096)
                self.stats["queries"] += 1
                threading.Thread(
                    target=self._handle_query, args=(data, addr), daemon=True
                ).start()
            except OSError:
                if self._running:
                    log.warning("Erreur socket DNS", exc_info=True)
                break

    def _handle_query(self, data: bytes, addr: tuple) -> None:
        try:
            request = dns.message.from_wire(data)
            response = dns.message.make_response(request)
            response.flags |= dns.flags.RA

            for question in request.question:
                qname = question.name.to_text()
                qtype = question.rdtype

                if qname in self.records:
                    ip = self.records[qname]
                    if qtype == dns.rdatatype.A:
                        self._add_a_record(response, qname, ip)
                        self.stats["answered"] += 1
                    elif qtype == dns.rdatatype.PTR:
                        self._try_ptr(response, qname, ip)
                    elif qtype == dns.rdatatype.ANY:
                        self._add_a_record(response, qname, ip)
                        self.stats["answered"] += 1
                    else:
                        self._forward_query(response, qname, qtype)
                elif qname.endswith("." + self.tld + "."):
                    ip = self.records.get(f"pixelos.{self.tld}.", "127.0.0.1")
                    if qtype == dns.rdatatype.A:
                        self._add_a_record(response, qname, ip)
                        self.stats["answered"] += 1
                    else:
                        self._forward_query(response, qname, qtype)
                else:
                    self._forward_query(response, qname, qtype)

            self._sock.sendto(response.to_wire(), addr)

        except dns.exception.DNSException as e:
            self.stats["errors"] += 1
            log.warning("Erreur DNS", error=str(e))
        except Exception as e:
            self.stats["errors"] += 1
            log.warning("Erreur traitement DNS", error=str(e))

    def _add_a_record(self, response: dns.message.Message, qname: str, ip: str) -> None:
        rrset = response.find_rrset(
            response.answer, dns.name.from_text(qname),
            dns.rdataclass.IN, dns.rdatatype.A, create=True,
        )
        rrset.add(dns.rdtypes.IN.A.A(dns.rdataclass.IN, dns.rdatatype.A, ip))

    def _try_ptr(self, response: dns.message.Message, qname: str, ip: str) -> None:
        try:
            rev_name = dns.reversename.from_address(ip)
            rrset = response.find_rrset(
                response.answer, rev_name,
                dns.rdataclass.IN, dns.rdatatype.PTR, create=True,
            )
            rrset.add(dns.rdtypes.ANY.PTR.PTR(
                dns.rdataclass.IN, dns.rdatatype.PTR,
                dns.name.from_text(qname),
            ))
            self.stats["answered"] += 1
        except Exception:
            self._forward_query(response, qname, dns.rdatatype.PTR)

    def _forward_query(self, response: dns.message.Message,
                       qname: str, qtype: int) -> None:
        try:
            req = dns.message.make_query(qname, qtype)
            req.flags |= dns.flags.RD
            resp = dns.query.udp(req, self.forwarder, timeout=3)
            for section in (resp.answer, resp.authority, resp.additional):
                for rrset in section:
                    response.answer.add(rrset)
            response.flags |= dns.flags.RA
            self.stats["forwarded"] += 1
        except Exception as e:
            log.warning("Echec forwarding DNS", qname=qname, error=str(e))
            response.flags |= dns.flags.RA

    def status(self) -> dict:
        return {
            "running": self._running,
            "tld": self.tld,
            "port": self.port,
            "forwarder": self.forwarder,
            "records": {k.rstrip("."): v for k, v in self.records.items()},
            "stats": {**self.stats},
        }


dns_server = PixelDNSServer()
