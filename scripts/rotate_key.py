import os
import sys
import asyncio
import argparse
import subprocess
from urllib.parse import urlparse
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models import InstanceRegistry

def convert_to_sync_dsn(async_url: str) -> str:
    parsed = urlparse(async_url)
    netloc = parsed.netloc
    if "@" in netloc and "+asyncpg" in parsed.scheme:
        return f"postgresql://{netloc}{parsed.path}"
    return async_url

async def backup_db(db_url: str):
    print("[*] Launching database pre-backup...")
    sync_dsn = convert_to_sync_dsn(db_url)
    proc = await asyncio.to_thread(
        subprocess.run,
        ["pg_dump", sync_dsn, "-f", "manager_db_backup.sql"],
        capture_output=True,
    )
    if proc.returncode != 0:
        print(f"[!] pg_dump failed: {proc.stderr.decode()}")
        raise RuntimeError("Database backup failed. Aborting.")
    print("[+] Backup created: manager_db_backup.sql")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-key", required=True)
    parser.add_argument("--new-key", required=True)
    args = parser.parse_args()

    db_url = os.environ.get("MANAGER_DATABASE_URL")
    if not db_url:
        print("[!] MANAGER_DATABASE_URL environment variable is required")
        sys.exit(1)

    try:
        f_old = Fernet(args.old_key.encode())
        f_new = Fernet(args.new_key.encode())
        assert f_old.decrypt(f_old.encrypt(b"test")) == b"test"
        assert f_new.decrypt(f_new.encrypt(b"test")) == b"test"
    except Exception:
        print("[!] Key sanity check failed. Verify the keys.")
        sys.exit(1)

    try:
        await backup_db(db_url)
    except Exception as e:
        print(e)
        sys.exit(1)

    engine = create_async_engine(db_url)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        async with session.begin():
            try:
                instances = (await session.execute(select(InstanceRegistry))).scalars().all()
                for inst in instances:
                    if inst.encrypted_tg_bot_token:
                        dec = f_old.decrypt(inst.encrypted_tg_bot_token.encode()).decode()
                        inst.encrypted_tg_bot_token = f_new.encrypt(dec.encode()).decode()
                    if inst.encrypted_db_password:
                        dec = f_old.decrypt(inst.encrypted_db_password.encode()).decode()
                        inst.encrypted_db_password = f_new.encrypt(dec.encode()).decode()
                print(f"[+] Re-encrypted {len(instances)} instances.")
            except Exception as ex:
                print(f"[!] Error during rotation. Transaction rolled back: {ex}")
                sys.exit(1)

    print("\n✅ Rotation successful!")
    print("1. Оновіть ENCRYPTION_KEY в .env на новий ключ.")
    print("2. Перезапустіть Manager API та ARQ Worker.")

if __name__ == "__main__":
    asyncio.run(main())
