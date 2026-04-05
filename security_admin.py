from __future__ import annotations

import argparse
import json
import os
from typing import Any

from security_audit import SecurityEventLogger
from security_controls import FileAbusePrevention, FileCircuitBreaker


def _default_actor() -> str:
    return os.getenv("QT_ADMIN_ACTOR") or os.getenv("USERNAME") or "cli_admin"


def _print_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No data.")
        return
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))


def _log_admin_action(action: str, actor: str, fields: dict[str, Any]) -> None:
    SecurityEventLogger().log_event(
        event_type="admin_action",
        action=action,
        actor=actor,
        fields=fields,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Administra eventos y controles de seguridad de Quantum Tutor."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_events = subparsers.add_parser("events", help="Muestra eventos recientes de seguridad.")
    parser_events.add_argument("--limit", type=int, default=50)
    parser_events.add_argument("--json", action="store_true", dest="as_json")

    parser_abuse_list = subparsers.add_parser("abuse-list", help="Lista identidades observadas por abuso.")
    parser_abuse_list.add_argument("--limit", type=int, default=100)
    parser_abuse_list.add_argument("--json", action="store_true", dest="as_json")

    parser_abuse_unblock = subparsers.add_parser("abuse-unblock", help="Desbloquea una identidad manualmente.")
    parser_abuse_unblock.add_argument("identifier")
    parser_abuse_unblock.add_argument("--actor", default=_default_actor())

    parser_breaker_list = subparsers.add_parser("breaker-list", help="Lista circuit breakers registrados.")
    parser_breaker_list.add_argument("--json", action="store_true", dest="as_json")

    parser_breaker_reset = subparsers.add_parser("breaker-reset", help="Resetea manualmente un circuit breaker.")
    parser_breaker_reset.add_argument("provider")
    parser_breaker_reset.add_argument("--actor", default=_default_actor())

    return parser


def main() -> int:
    args = _build_parser().parse_args()
    audit_logger = SecurityEventLogger()
    abuse_store = FileAbusePrevention()
    breaker_store = FileCircuitBreaker()

    if args.command == "events":
        rows = audit_logger.read_recent_events(limit=max(args.limit, 1))
        if args.as_json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            _print_rows(rows)
        return 0

    if args.command == "abuse-list":
        rows = abuse_store.list_entries(limit=max(args.limit, 1))
        if args.as_json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            _print_rows(rows)
        return 0

    if args.command == "abuse-unblock":
        cleared = abuse_store.clear_identifier(args.identifier)
        if cleared:
            _log_admin_action(
                "manual_abuse_unblock",
                args.actor,
                {"identity": args.identifier, "channel": "cli"},
            )
            print(f"Unlocked identity: {args.identifier}")
            return 0
        print(f"Identity not found: {args.identifier}")
        return 1

    if args.command == "breaker-list":
        rows = breaker_store.list_entries()
        if args.as_json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            _print_rows(rows)
        return 0

    if args.command == "breaker-reset":
        decision = breaker_store.reset(args.provider)
        _log_admin_action(
            "manual_circuit_breaker_reset",
            args.actor,
            {"provider": args.provider, "channel": "cli"},
        )
        print(json.dumps(decision.as_metadata(), ensure_ascii=False))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
