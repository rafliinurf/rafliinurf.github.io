"""Offline accounts with locally hashed passwords."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import tempfile


ACCOUNT_VERSION = 1
PASSWORD_ITERATIONS = 310_000
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,20}$")
DEVELOPER_USERNAME = "rafli"
ACCOUNT_TAGS = frozenset({"developer", "player"})


class AccountError(ValueError):
    """An account could not be created or authenticated."""


class AccountStore:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else self.default_data_dir()
        self.accounts_path = self.data_dir / "accounts.json"
        self.profiles_dir = self.data_dir / "profiles"

    @staticmethod
    def default_data_dir():
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / "FarmerReplica"

    def register(self, username, password):
        username = self._validate_credentials(username, password)
        accounts = self._read_accounts()
        key = username.lower()
        if key in accounts:
            raise AccountError("Username tersebut sudah terdaftar.")
        salt = secrets.token_bytes(16)
        accounts[key] = {
            "username": username,
            "salt": salt.hex(),
            "password_hash": self._hash_password(password, salt),
            "tag": self._default_tag(key),
        }
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._write_accounts(accounts)
        return username

    def authenticate(self, username, password):
        if not isinstance(username, str) or not isinstance(password, str):
            raise AccountError("Username atau kata sandi tidak cocok.")
        accounts = self._read_accounts()
        account = accounts.get(username.strip().lower())
        if account is None:
            raise AccountError("Username atau kata sandi tidak cocok.")
        salt = bytes.fromhex(account["salt"])
        candidate = self._hash_password(password, salt)
        if not hmac.compare_digest(candidate, account["password_hash"]):
            raise AccountError("Username atau kata sandi tidak cocok.")
        return account["username"]

    def tag_for(self, username):
        if not isinstance(username, str) or not USERNAME_PATTERN.fullmatch(username):
            raise AccountError("Username tidak valid.")
        accounts = self._read_accounts()
        key = username.lower()
        account = accounts.get(key)
        if account is None:
            raise AccountError("Akun tidak ditemukan.")
        tag = account.get("tag")
        if tag is None:
            tag = self._default_tag(key)
            account["tag"] = tag
            self._write_accounts(accounts)
        return tag

    def profile_path(self, username):
        if not isinstance(username, str) or not USERNAME_PATTERN.fullmatch(username):
            raise AccountError("Username tidak valid.")
        return self.profiles_dir / f"{username.lower()}.json"

    def _validate_credentials(self, username, password):
        if not isinstance(username, str):
            raise AccountError("Username hanya boleh 3-20 karakter: huruf, angka, atau _.")
        username = username.strip()
        if not USERNAME_PATTERN.fullmatch(username):
            raise AccountError("Username hanya boleh 3-20 karakter: huruf, angka, atau _.")
        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            raise AccountError("Kata sandi harus terdiri dari 8-128 karakter.")
        return username

    def _read_accounts(self):
        if not self.accounts_path.exists():
            return {}
        try:
            with self.accounts_path.open(encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as exc:
            raise AccountError("Data akun lokal rusak dan tidak dapat dibaca.") from exc
        if (
            not isinstance(data, dict)
            or isinstance(data.get("version"), bool)
            or not isinstance(data.get("version"), int)
            or data.get("version") != ACCOUNT_VERSION
            or not isinstance(data.get("accounts"), dict)
        ):
            raise AccountError("Format data akun lokal tidak dikenal.")
        accounts = data["accounts"]
        for key, account in accounts.items():
            if (
                not isinstance(key, str)
                or not isinstance(account, dict)
                or not isinstance(account.get("username"), str)
                or not USERNAME_PATTERN.fullmatch(account["username"])
                or account["username"].lower() != key
                or account.get("username") != account["username"].strip()
                or not _is_hex(account.get("salt"), 32)
                or not _is_hex(account.get("password_hash"), 64)
                or (
                    "tag" in account
                    and (
                        not isinstance(account["tag"], str)
                        or account["tag"] not in ACCOUNT_TAGS
                    )
                )
            ):
                raise AccountError("Data akun lokal berisi entri yang tidak valid.")
        return accounts

    @staticmethod
    def _default_tag(username):
        return "developer" if username.lower() == DEVELOPER_USERNAME else "player"

    def _write_accounts(self, accounts):
        self._write_json_atomically(
            self.accounts_path,
            {"version": ACCOUNT_VERSION, "accounts": accounts},
        )

    @staticmethod
    def _hash_password(password, salt):
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PASSWORD_ITERATIONS,
        ).hex()

    @staticmethod
    def _write_json_atomically(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temp_path = Path(file.name)
                json.dump(data, file, ensure_ascii=False, allow_nan=False)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()


def _is_hex(value, length):
    if not isinstance(value, str) or len(value) != length:
        return False
    try:
        decoded = bytes.fromhex(value)
    except ValueError:
        return False
    return len(decoded) == length // 2
