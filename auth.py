#!/usr/bin/env python3
"""
Credential management via macOS Keychain.

Credentials are stored under the service name 'icloud-mcp' and never
written to disk, environment variables, or source code.

Usage:
    uv run python3 auth.py store   # interactively store credentials
    uv run python3 auth.py verify  # test credentials against iCloud
    uv run python3 auth.py clear   # remove stored credentials
"""

from __future__ import annotations

import getpass
import sys

import keyring

SERVICE = "icloud-mcp"
KEY_APPLE_ID = "apple_id"
KEY_APP_PASSWORD = "app_specific_password"


def store_credentials() -> None:
    """Interactively prompt for and store credentials in the Keychain."""
    print("iCloud MCP — Store Credentials")
    print("=" * 40)
    print("Enter your Apple ID and an app-specific password.")
    print("Generate an app-specific password at: https://appleid.apple.com")
    print("(Account > Sign-In and Security > App-Specific Passwords)\n")

    apple_id = input("Apple ID (email): ").strip()
    if not apple_id:
        print("Error: Apple ID cannot be empty.")
        sys.exit(1)

    app_password = getpass.getpass("App-specific password: ").strip()
    if not app_password:
        print("Error: Password cannot be empty.")
        sys.exit(1)

    keyring.set_password(SERVICE, KEY_APPLE_ID, apple_id)
    keyring.set_password(SERVICE, KEY_APP_PASSWORD, app_password)

    print(f"\nCredentials stored in macOS Keychain under service '{SERVICE}'.")
    print("Run 'uv run python3 auth.py verify' to test them.")


def get_credentials() -> tuple[str, str]:
    """
    Retrieve credentials from the Keychain.

    Returns:
        (apple_id, app_password)

    Raises:
        RuntimeError: if credentials have not been stored yet.
    """
    apple_id = keyring.get_password(SERVICE, KEY_APPLE_ID)
    app_password = keyring.get_password(SERVICE, KEY_APP_PASSWORD)

    if not apple_id or not app_password:
        raise RuntimeError(
            "iCloud credentials not found in Keychain.\n"
            "Run: uv run python3 auth.py store"
        )

    return apple_id, app_password


def clear_credentials() -> None:
    """Remove stored credentials from the Keychain."""
    keyring.delete_password(SERVICE, KEY_APPLE_ID)
    keyring.delete_password(SERVICE, KEY_APP_PASSWORD)
    print("Credentials removed from Keychain.")


def verify_credentials() -> bool:
    """Test stored credentials by authenticating with iCloud."""
    try:
        from pyicloud import PyiCloudService
        from pyicloud.exceptions import PyiCloudFailedLoginException
    except ImportError:
        print("Error: pyicloud not installed. Run: uv sync")
        return False

    apple_id, app_password = get_credentials()
    print(f"Testing credentials for {apple_id} ...")

    try:
        api = PyiCloudService(apple_id, app_password)
        if api.requires_2fa:
            print(
                "Two-factor authentication required.\n"
                "The server will prompt for the 2FA code on first startup."
            )
        else:
            print("Authentication successful.")
        return True
    except PyiCloudFailedLoginException:
        print("Authentication failed. Check your Apple ID and app-specific password.")
        return False


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "help"

    if command == "store":
        store_credentials()
    elif command == "verify":
        verify_credentials()
    elif command == "clear":
        clear_credentials()
    else:
        print(__doc__)
