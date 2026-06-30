# Pixel Software Design � Copyright 2026
import argparse
import json
import sys
import subprocess
from .pixstat import PixStat
from .pixdefend import PixDefend
from .pixscudo import PixScudo
from ..process_manager.pixmanager import PixManager


class PixUtil:
    def __init__(self):
        self.pixstat = PixStat()
        self.pixdefend = PixDefend()
        self.pixscudo = PixScudo()
        self.pixmanager = PixManager()

    def cmd_status(self, args):
        s = self.pixstat.summary()
        d = self.pixdefend.stats()
        sc = self.pixscudo.summary()

        print("=" * 50)
        print("  Pixel OS — Security Status")
        print("=" * 50)
        print(f"  Connections:     {s['connections']} active")
        print(f"  Blocked IPs:     {d['blocked']}")
        print(f"  PF Enabled:      {d['pf_enabled']}")
        print(f"  Syspatches:      {sc['patches_available']} available")
        print(f"  Package issues:  {sc['package_issues']}")
        print(f"  Open ports:      {sc['open_ports']}")
        if sc['unexpected_ports']:
            print(f"  ⚠ Unexpected:    {sc['unexpected_ports']}")
        if sc['warnings']:
            for w in sc['warnings']:
                print(f"  ⚠ {w}")
        print(f"  Interfaces:")
        for iface in s.get("interfaces", []):
            ips = ", ".join(iface.get("inet", []))
            print(f"    {iface['name']}: {iface['status']} [{ips}]")
        if args.json:
            return json.dumps({"status": s, "defend": d, "scudo": sc}, indent=2)

    def cmd_net_stats(self, args):
        s = self.pixstat.snapshot()
        if args.json:
            print(json.dumps(s, indent=2))
            return
        print("--- Network Stats ---")
        print(f"Active connections: {s['connections']}")
        print(f"Bandwidth: RX {s['bandwidth']['rx_bytes_per_sec']} B/s, TX {s['bandwidth']['tx_bytes_per_sec']} B/s")
        if s.get("by_ip"):
            print("Top talkers:")
            for ip, count in sorted(s["by_ip"].items(), key=lambda x: -x[1])[:10]:
                print(f"  {ip}: {count} connections")

    def cmd_defend(self, args):
        if args.action == "start":
            self.pixdefend.ensure_table()
            r = self.pixdefend.reload_pf()
            print(f"PF reloaded: {r['status']}")
        elif args.action == "stop":
            print("PixDefend: pass in all (disable) — not implemented")
        elif args.action == "block":
            if not args.ip:
                print("Usage: pixutil --defend block --ip X.X.X.X")
                return
            r = self.pixdefend.block_ip(args.ip)
            print(f"Block {args.ip}: {r['status']}")
        elif args.action == "unblock":
            if not args.ip:
                print("Usage: pixutil --defend unblock --ip X.X.X.X")
                return
            r = self.pixdefend.unblock_ip(args.ip)
            print(f"Unblock {args.ip}: {r['status']}")
        elif args.action == "list":
            r = self.pixdefend.list_blocked()
            print(f"Blocked IPs ({r['count']}):")
            for ip in r.get("ips", []):
                print(f"  {ip}")
        elif args.action == "status":
            pf = self.pixdefend.get_pf_status()
            print(f"PF enabled: {pf.get('enabled')}")
            rules = self.pixdefend.get_pf_rules()
            print(f"Rules: {rules.get('count', 0)}")
        else:
            print(f"Unknown action: {args.action}")

    def cmd_task(self, args):
        if args.action == "list":
            procs = self.pixmanager.list_processes(sort_by=args.sort or "cpu", limit=args.limit or 50)
            if args.json:
                print(json.dumps(procs, indent=2))
                return
            print(f"--- Processus ({procs['total']} total, {procs['total_cpu']}% CPU, {procs['total_mem']}% MEM) ---")
            print(f"{'PID':>6} {'CPU%':>5} {'MEM%':>5} {'RSS':>8} {'État':>4}  {'Nom'}")
            print("-" * 60)
            for p in procs["processes"][:30]:
                wl = "✓" if p["whitelisted"] else "?"
                print(f"{p['pid']:>6} {p['cpu_pct']:>5.1f} {p['mem_pct']:>5.1f} {p['rss_bytes']//1024:>6}K {p['state']:>4}  {wl} {p['name']}")
        elif args.action == "kill":
            if args.pid:
                r = self.pixmanager.kill_process(args.pid, args.signal or 15)
                print(f"Kill PID {args.pid}: {r['status']}")
            elif args.name:
                r = self.pixmanager.kill_by_name(args.name, args.signal or 15)
                print(f"Kill {args.name}: {r['status']}")
            else:
                print("Usage: pixutil --task kill --pid PID ou --name NAME")
        elif args.action == "trace":
            if not args.pid:
                print("Usage: pixutil --task trace --pid PID")
                return
            r = self.pixmanager.trace_process(args.pid, args.duration or 15)
            if args.json:
                print(json.dumps(r, indent=2))
                return
            print(f"Trace PID {args.pid} ({r.get('count', 0)} appels):")
            for line in r.get("syscalls", r.get("snapshots", []))[:20]:
                print(f"  {line}")
        elif args.action == "new":
            r = self.pixmanager.detect_new_processes()
            new = r.get("new", [])
            if args.json:
                print(json.dumps(r, indent=2))
                return
            if new:
                print(f"Nouveaux processus ({len(new)}):")
                for p in new:
                    wl = "✓" if p["whitelisted"] else "⚠️"
                    print(f"  PID {p['pid']:>6} {wl} {p['name']} (cat: {p['whitelist_category']})")
            else:
                print("Aucun nouveau processus détecté" if r.get("initialized") else "Initialisation...")
        elif args.action == "monitor":
            if args.monitor_action == "start":
                r = self.pixmanager.start_monitoring(args.interval or 5)
                print(f"Monitoring: {r['status']}")
            elif args.monitor_action == "stop":
                r = self.pixmanager.stop_monitoring()
                print(f"Monitoring: {r['status']}")
            elif args.monitor_action == "status":
                s = self.pixmanager.monitoring_status()
                print(f"Monitoring: {'✅ Actif' if s['monitoring'] else '⏸️ Inactif'}")
                print(f"PIDs connus: {s['known_pids']}")
                print(f"Nouveaux: {s['new_processes_logged']}")
        elif args.action == "whitelist":
            if args.whitelist_action == "list":
                wl = self.pixmanager.whitelist_list()
                print(f"Whitelist ({wl['total']} processus):")
                for cat, procs in wl["by_category"].items():
                    print(f"  [{cat}] {', '.join(procs)}")
            elif args.whitelist_action == "add" and args.name:
                r = self.pixmanager.whitelist_add(args.name, args.category or "custom")
                print(f"Whitelist add {args.name}: {r['status']}")
            elif args.whitelist_action == "remove" and args.name:
                r = self.pixmanager.whitelist_remove(args.name)
                print(f"Whitelist remove {args.name}: {r['status']}")
        else:
            print(f"Unknown action: {args.action}")

    def cmd_scudo(self, args):
        if args.action == "check" or args.action == "audit":
            audit = self.pixscudo.run_full_audit()
            if args.json:
                print(json.dumps(audit, indent=2))
                return
            print("--- PixScudo Audit ---")
            print(f"Score: {audit['score']}/100")
            for check_name, check_data in audit["checks"]:
                if isinstance(check_data, dict):
                    if check_data.get("available", 0) > 0:
                        print(f"  ⚠ {check_name}: {check_data['available']} issues")
                    elif check_data.get("count", 0) > 0:
                        print(f"  ⚠ {check_name}: {check_data['count']} issues")
                    else:
                        print(f"  ✓ {check_name}: OK")
                elif isinstance(check_data, list):
                    warnings = [c for c in check_data if c.get("warnings")]
                    if warnings:
                        print(f"  ⚠ {check_name}: {len(warnings)} warnings")
                    else:
                        print(f"  ✓ {check_name}: OK")
        elif args.action == "patches":
            p = self.pixscudo.check_syspatch()
            print(f"Available patches: {p.get('available', 0)}")
            for patch in p.get("patches", []):
                print(f"  {patch}")
        else:
            print(f"Unknown action: {args.action}")

    def run(self, argv=None):
        if argv is None:
            argv = sys.argv[1:]

        parser = argparse.ArgumentParser(
            description="Pixel OS Security Utility (PixUtil)"
        )
        parser.add_argument("--status", action="store_true", help="Afficher l'état général")
        parser.add_argument("--net", choices=["stats"], help="Stats réseau")
        parser.add_argument("--defend", choices=["start", "stop", "block", "unblock", "list", "status"], help="Action PixDefend")
        parser.add_argument("--scudo", choices=["check", "audit", "patches"], help="Action PixScudo")
        parser.add_argument("--task", choices=["list", "kill", "trace", "new", "monitor", "whitelist"], help="Action PixManager (processus)")
        parser.add_argument("--pid", type=int, help="PID du processus")
        parser.add_argument("--name", help="Nom du processus")
        parser.add_argument("--signal", type=int, default=15, help="Signal pour kill (défaut: 15=TERM)")
        parser.add_argument("--duration", type=int, default=15, help="Durée trace en secondes")
        parser.add_argument("--sort", choices=["cpu", "mem", "pid", "name", "priority"], default="cpu", help="Tri liste processus")
        parser.add_argument("--limit", type=int, default=50, help="Nombre max de processus")
        parser.add_argument("--interval", type=int, default=5, help="Intervalle monitoring (s)")
        parser.add_argument("--monitor-action", choices=["start", "stop", "status"], default="status", help="Action monitoring")
        parser.add_argument("--whitelist-action", choices=["list", "add", "remove"], default="list", help="Action whitelist")
        parser.add_argument("--category", default="custom", help="Catégorie whitelist")
        parser.add_argument("--ip", help="Adresse IP pour block/unblock")
        parser.add_argument("--json", action="store_true", help="Sortie JSON")
        parser.add_argument("--all", action="store_true", help="Tout afficher")

        args = parser.parse_args(argv)

        if args.status:
            self.cmd_status(args)
        elif args.net == "stats":
            self.cmd_net_stats(args)
        elif args.defend:
            self.cmd_defend(args)
        elif args.scudo:
            self.cmd_scudo(args)
        elif args.task:
            self.cmd_task(args)
        elif args.all:
            self.cmd_status(args)
            print()
            self.cmd_net_stats(args)
            print()
            d = argparse.Namespace(action="status", json=args.json)
            self.cmd_defend(d)
            s = argparse.Namespace(action="check", json=args.json)
            self.cmd_scudo(s)
        else:
            parser.print_help()


def main():
    PixUtil().run()


if __name__ == "__main__":
    main()
