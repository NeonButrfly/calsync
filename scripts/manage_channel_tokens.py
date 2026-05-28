import argparse
import sys

from calsync.config import get_settings
from calsync.services.channel_tokens import ChannelTokenManager


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage CalSync channel tokens for Cloudflare edge access.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap")
    bootstrap.add_argument("--channels", required=True)

    rotate = subparsers.add_parser("rotate")
    rotate.add_argument("--channel", required=True)

    show = subparsers.add_parser("show")
    show.add_argument("--channel", required=True)

    subparsers.add_parser("sync-cloudflare")

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    settings = get_settings()
    manager = ChannelTokenManager(runtime_path=settings.channel_token_runtime_path)

    try:
        if args.command == "bootstrap":
            channels = [channel.strip() for channel in args.channels.split(",") if channel.strip()]
            for channel in channels:
                token = manager.bootstrap_channel(channel)
                print(f"{channel}={token}")
            return 0

        if args.command == "rotate":
            print(manager.rotate_channel(args.channel))
            return 0

        if args.command == "show":
            print(manager.show_channel(args.channel))
            return 0

        if args.command == "sync-cloudflare":
            if not settings.cloudflare_account_id:
                raise ValueError("CLOUDFLARE_ACCOUNT_ID is required.")
            if not settings.cloudflare_api_token:
                raise ValueError("CLOUDFLARE_API_TOKEN is required.")
            if not settings.cloudflare_token_kv_namespace_id:
                raise ValueError("CLOUDFLARE_TOKEN_KV_NAMESPACE_ID is required.")

            manager.sync_hashes_to_cloudflare(
                account_id=settings.cloudflare_account_id,
                api_token=settings.cloudflare_api_token,
                namespace_id=settings.cloudflare_token_kv_namespace_id,
            )
            print("synced")
            return 0
    except (KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
