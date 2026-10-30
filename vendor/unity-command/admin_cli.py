"""
Operator CLI for managing Unity AI Lab admin credentials.

Run from the bot host to issue temp passwords, list current admin state, or
seed the credentials store. The four founders are hardcoded in
`admin_credentials.FOUNDERS` — this CLI doesn't add new admins, it only
manages credentials for the existing roster.

Usage:
    python admin_cli.py bootstrap
        Create logs/admin_credentials.json with the 4 founders (no passwords).
        Idempotent — refuses to overwrite an existing file.

    python admin_cli.py issue <email>
        Generate + store a 16-char temp password for <email>, print it ONCE.
        Hand the printed password to the admin via a secure channel; the
        admin redeems it on first Claude Code → Unity MCP connect.

    python admin_cli.py list
        Show the current admin roster + status (has-password, force-reset,
        last-login). NEVER prints password hashes.

    python admin_cli.py whoami <email>
        Print the founder record (email + handle + role) for an identity
        string. Useful for verifying alt-handle resolution.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

# Windows cp1252 stdout chokes on the U+00B7 separator used in founder role
# strings. Reconfigure to UTF-8 before any print() runs.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

import admin_credentials


def cmd_bootstrap(_args: argparse.Namespace) -> int:
    created = admin_credentials.bootstrap_if_missing()
    if created:
        print("[+] Bootstrapped admin credentials store with 4 founders.")
        print(f"    Path: {admin_credentials.DEFAULT_CREDENTIALS_PATH}")
        print("    Passwords: NOT set — issue temps via `admin_cli.py issue <email>`.")
        return 0
    print("[=] Credentials store already exists — nothing to do.")
    print(f"    Path: {admin_credentials.DEFAULT_CREDENTIALS_PATH}")
    return 0


def cmd_issue(args: argparse.Namespace) -> int:
    email: str = args.email
    temp: Optional[str] = admin_credentials.issue_temp_password(email)
    if temp is None:
        print(f"[!] {email} is not a known Unity AI Lab founder.", file=sys.stderr)
        print("    Known emails:", file=sys.stderr)
        for founder in admin_credentials.FOUNDERS:
            print(f"      - {founder['email']} ({founder['handle']})", file=sys.stderr)
        return 1

    print("=" * 64)
    print(f"  TEMP PASSWORD ISSUED  — {email}")
    print("=" * 64)
    print(f"  Password:  {temp}")
    print()
    print("  This is shown ONCE. Hand it to the admin via secure channel.")
    print("  On first MCP connect the admin MUST set a real password via")
    print("  the `unity_admin_set_password` tool — temp is single-use only.")
    print("=" * 64)
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    admins = admin_credentials.list_admins()
    if not admins:
        print("[!] Credentials store is empty. Run `admin_cli.py bootstrap` first.")
        return 1

    print(f"{'EMAIL':<32} {'HANDLE':<14} {'HAS_PW':<7} {'RESET':<6} {'LAST_LOGIN'}")
    print("-" * 90)
    for admin in admins:
        print(
            f"{admin['email']:<32} "
            f"{admin['handle']:<14} "
            f"{'yes' if admin['has_password'] else 'no':<7} "
            f"{'YES' if admin['force_reset'] else 'no':<6} "
            f"{admin.get('last_login') or '—'}"
        )
    return 0


def cmd_whoami(args: argparse.Namespace) -> int:
    founder = admin_credentials.resolve_handle_from_identity(args.identity)
    if not founder:
        print(f"[!] '{args.identity}' does not resolve to any founder.", file=sys.stderr)
        return 1
    print(json.dumps(founder, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="admin_cli.py",
        description="Operator CLI for Unity AI Lab admin credentials.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("bootstrap", help="Seed credentials store with 4 founders.")

    issue = subparsers.add_parser("issue", help="Generate temp password for an admin.")
    issue.add_argument("email", help="Admin email (e.g. Gee@unityailab.com).")

    subparsers.add_parser("list", help="Show admin roster + status.")

    whoami = subparsers.add_parser("whoami", help="Resolve identity to founder record.")
    whoami.add_argument("identity", help="Email, handle, or alt-handle (e.g. Sponge, hackall360).")

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    commands = {
        "bootstrap": cmd_bootstrap,
        "issue": cmd_issue,
        "list": cmd_list,
        "whoami": cmd_whoami,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
