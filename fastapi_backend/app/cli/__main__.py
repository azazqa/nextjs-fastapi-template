import argparse
import asyncio

from app.cli.grant_role import grant_role
from app.cli.seed_rbac import seed_rbac_cmd


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    grant_parser = subparsers.add_parser("grant-role")
    grant_parser.add_argument("--email", required=True)
    grant_parser.add_argument("--role", required=True)

    subparsers.add_parser("seed-rbac")

    args = parser.parse_args()
    if args.command == "grant-role":
        asyncio.run(grant_role(email=args.email, role_code=args.role))
    elif args.command == "seed-rbac":
        asyncio.run(seed_rbac_cmd())


if __name__ == "__main__":
    main()
