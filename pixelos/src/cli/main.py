#!/usr/bin/env python3
"""
PixelOS CLI - Interface de gestion complète du système agricole.
Usage: pixelos <commande> [options]
"""

import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import PixelOSConfig
from core.mqtt import PixelOSMQTT

config = PixelOSConfig()


def cmd_status(args):
    """État global du système."""
    from core.mqtt import PixelOSMQTT

    print("╔══════════════════════════════════════════╗")
    print("║        PixelOS - État du système        ║")
    print("╚══════════════════════════════════════════╝")
    print()

    # MQTT
    mqtt = PixelOSMQTT()
    try:
        mqtt.connect()
        mqtt_status = "✅ Connecté" if mqtt.connected else "❌ Déconnecté"
    except:
        mqtt_status = "❌ Erreur connexion"
    print(f"  MQTT Broker : {mqtt_status}")

    # Base de données
    print(f"  MySQL       : {'✅ OK' if _check_mysql() else '❌ Erreur'}")
    print(f"  MongoDB     : {'✅ OK' if _check_mongodb() else '❌ Erreur'}")

    # Backend
    print(f"  API Backend : {'✅ OK' if _check_backend() else '❌ Erreur'}")

    # Nœuds
    print()
    online = sum(1 for n in config.nodes.values() if _ping_node(n))
    total = len(config.nodes)
    print(f"  Nœuds       : {online}/{total} en ligne")

    if args.node:
        n = config.get_node(args.node)
        if n:
            print(f"\n  Détail {args.node}:")
            print(f"    Type   : {n['type']}")
            print(f"    Adresse: {n['addr']}")
            print(f"    Loc.   : {n.get('location', 'N/A')}")
            print(f"    Com.   : {n['communication']}")


def cmd_node(args):
    """Gestion des nœuds."""
    if args.action == "list":
        print(f"{'ID':<20} {'Type':<15} {'Adr':<5} {'Location':<20} {'Com':<8} {'Status'}")
        print("-" * 90)
        for n in config.nodes.values():
            online = _ping_node(n)
            status = "🟢" if online else "🔴"
            print(f"{n['id']:<20} {n['type']:<15} {n['addr']:<5} "
                  f"{n.get('location','?'):<20} {n['communication']:<8} {status}")

    elif args.action == "config":
        n = config.get_node(args.node_id)
        if not n:
            print(f"❌ Nœud {args.node_id} introuvable")
            return
        print(json.dumps(n, indent=2, ensure_ascii=False))


def cmd_irrigate(args):
    """Gestion de l'irrigation."""
    mqtt = PixelOSMQTT()
    mqtt.connect()

    if args.action == "status":
        print("État irrigation par zone :")
        print("-" * 50)
        for n in config.get_nodes_by_type("capteur_sol"):
            irr = n.get("irrigation", {})
            seuil = irr.get("seuil_secheresse", "N/A")
            valve = irr.get("valve_addr", "N/A")
            print(f"  {n['id']:<15} seuil={seuil:<5} vanne={valve}")

    elif args.action in ("open", "close"):
        cmd = "OUVRIR" if args.action == "open" else "FERMER"
        for n in config.nodes.values():
            if n["type"] == "vanne" and (args.zone in n["id"] or args.zone == "all"):
                topic = f"agricol/commande/vanne/{n['id']}"
                mqtt.publish(topic, {"cmd": cmd})
                print(f"  → {topic}: {cmd}")
        mqtt.disconnect()


def cmd_firmware(args):
    """Gestion des firmwares."""
    from core.ota import FirmwareOTA

    ota = FirmwareOTA()

    if args.action == "list":
        versions = ota.list_versions()
        if not versions:
            print("Aucun firmware disponible")
            return
        for node_type, vers in versions.items():
            print(f"\n{node_type}:")
            for v in vers:
                print(f"  └─ {v['variant']} ({v['modified']})")
                for f in v['files']:
                    print(f"      └─ {Path(f).name}")

    elif args.action == "build":
        fw_path = ota.build(args.type)
        print(f"✅ Firmware compilé: {fw_path}")


def cmd_monitor(args):
    """Monitoring du système."""
    if args.action == "health":
        checks = {
            "mqtt": _check_mqtt(),
            "mysql": _check_mysql(),
            "mongodb": _check_mongodb(),
            "backend": _check_backend(),
            "disk": _check_disk(),
            "memory": _check_memory(),
        }
        print(f"{'Composant':<15} {'Status':<10} {'Détail'}")
        print("-" * 60)
        for comp, (ok, detail) in checks.items():
            icon = "✅" if ok else "❌"
            print(f"{comp:<15} {icon:<10} {detail}")

    elif args.action == "alerts":
        alerts = config.alerts
        if not alerts:
            print("Aucune règle d'alerte configurée")
            return
        print(f"{'Alerte':<30} {'Severité':<10} {'Condition'}")
        print("-" * 80)
        for a in alerts:
            sev = a.get("severity", "info")
            print(f"{a['name']:<30} {sev:<10} {a.get('condition','')[:50]}")


def cmd_backup(args):
    """Backup du système."""
    from core.backup import BackupManager

    bk = BackupManager(path=config.get("backup.path", "/var/backups/pixelos"))

    if args.action == "create" or args.action is None:
        path = bk.create()
        print(f"✅ Backup créé: {path}")

    elif args.action == "list":
        backups = bk.list_backups()
        if not backups:
            print("Aucun backup")
            return
        print(f"{'Date':<25} {'Taille':<10} {'Path'}")
        print("-" * 70)
        for b in backups:
            print(f"{b['date']:<25} {b['size']:<10} {b['path']}")

    elif args.action == "restore":
        bk.restore(args.backup_id if args.backup_id != "latest" else None)


def cmd_config(args):
    """Gestion de la configuration."""
    if args.action == "show":
        print(config.to_json())

    elif args.action == "set" and args.key and args.value:
        config.set(args.key, args.value)
        print(f"✅ {args.key} = {args.value}")


# ─── Utilitaires ───

def _check_mqtt() -> tuple[bool, str]:
    try:
        m = PixelOSMQTT()
        m.connect()
        ok = m.connected
        m.disconnect()
        return ok, "Connecté" if ok else "Timeout"
    except Exception as e:
        return False, str(e)

def _check_mysql() -> tuple[bool, str]:
    try:
        import mysql.connector
        c = mysql.connector.connect(
            host=config.get("database.mysql.host", "localhost"),
            port=config.get("database.mysql.port", 3306),
            user=config.get("database.mysql.user", "agricol"),
            database=config.get("database.mysql.database", "agricol"),
        )
        c.close()
        return True, "Connecté"
    except Exception as e:
        return False, str(e)

def _check_mongodb() -> tuple[bool, str]:
    try:
        from pymongo import MongoClient
        client = MongoClient(config.get("database.mongodb.uri",
                                         "mongodb://localhost:27017/"))
        client.admin.command("ping")
        return True, "Connecté"
    except Exception as e:
        return False, str(e)

def _check_backend() -> tuple[bool, str]:
    import requests
    try:
        r = requests.get(f"{config.get('backend.api_url')}/health", timeout=5)
        return r.ok, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)

def _check_disk() -> tuple[bool, str]:
    import shutil
    usage = shutil.disk_usage("/")
    pct = usage.used / usage.total * 100
    return pct < 90, f"{pct:.0f}% utilisé"

def _check_memory() -> tuple[bool, str]:
    try:
        import psutil
        mem = psutil.virtual_memory()
        return mem.percent < 90, f"{mem.percent:.0f}% utilisé"
    except:
        return True, "N/A"

def _ping_node(node: dict) -> bool:
    """Vérification simple de l'état du nœud."""
    return True  # TODO: implémenter heartbeat MQTT


def main():
    parser = argparse.ArgumentParser(
        description="PixelOS - Système de Gestion Agricole Connecté",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version="PixelOS 2.0")

    sub = parser.add_subparsers(dest="command")

    # status
    p = sub.add_parser("status", help="État du système")
    p.add_argument("--node", help="Détail d'un nœud spécifique")
    p.set_defaults(func=cmd_status)

    # node
    p = sub.add_parser("node", help="Gestion des nœuds")
    p.add_argument("action", choices=["list", "config"])
    p.add_argument("node_id", nargs="?")
    p.set_defaults(func=cmd_node)

    # irrigate
    p = sub.add_parser("irrigate", help="Contrôle irrigation")
    p.add_argument("action", choices=["status", "open", "close"])
    p.add_argument("zone", nargs="?", default="all")
    p.set_defaults(func=cmd_irrigate)

    # firmware
    p = sub.add_parser("firmware", help="Gestion firmware OTA")
    p.add_argument("action", choices=["list", "build", "flash"])
    p.add_argument("--type", help="Type de nœud (sensor_node, valve_node...)")
    p.set_defaults(func=cmd_firmware)

    # monitor
    p = sub.add_parser("monitor", help="Monitoring")
    p.add_argument("action", choices=["health", "alerts"])
    p.set_defaults(func=cmd_monitor)

    # backup
    p = sub.add_parser("backup", help="Backup/Restore")
    p.add_argument("action", choices=["create", "list", "restore"], nargs="?")
    p.add_argument("backup_id", nargs="?")
    p.set_defaults(func=cmd_backup)

    # config
    p = sub.add_parser("config", help="Configuration")
    p.add_argument("action", choices=["show", "set"])
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p.set_defaults(func=cmd_config)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
