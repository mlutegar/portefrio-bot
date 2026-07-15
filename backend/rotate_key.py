"""Rotaciona a chave-mestra do cofre (CREDENTIALS_KEY) re-cifrando as credenciais.

Uso:
    python rotate_key.py <CHAVE_ANTIGA> <CHAVE_NOVA>

Passos seguros:
  1. Gere a nova chave:
       python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
  2. Rode este script com (chave_atual, chave_nova).
  3. Atualize CREDENTIALS_KEY no .env para a nova chave e reinicie o backend.

Se as credenciais não puderem ser decifradas com a chave antiga, nada é alterado.
"""
from __future__ import annotations

import sys

from cryptography.fernet import Fernet, InvalidToken

from app import db


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    chave_antiga, chave_nova = sys.argv[1].encode(), sys.argv[2].encode()
    f_old, f_new = Fernet(chave_antiga), Fernet(chave_nova)

    db.init_db()
    with db._conn() as c:
        rows = c.execute(
            "SELECT id, email_enc, senha_enc, senha2_enc FROM credenciais"
        ).fetchall()

        if not rows:
            print("Nenhuma credencial no cofre. Nada a fazer.")
            return 0

        recifradas = []
        for r in rows:
            try:
                email = f_old.decrypt(bytes(r["email_enc"]))
                senha = f_old.decrypt(bytes(r["senha_enc"]))
                senha2 = (
                    f_old.decrypt(bytes(r["senha2_enc"]))
                    if r["senha2_enc"] is not None
                    else None
                )
            except InvalidToken:
                print(
                    f"ERRO: credencial id={r['id']} não decifra com a chave antiga. "
                    "Abortando sem alterar nada."
                )
                return 1
            recifradas.append(
                (
                    f_new.encrypt(email),
                    f_new.encrypt(senha),
                    f_new.encrypt(senha2) if senha2 is not None else None,
                    r["id"],
                )
            )

        for email_enc, senha_enc, senha2_enc, rid in recifradas:
            c.execute(
                "UPDATE credenciais SET email_enc=?, senha_enc=?, senha2_enc=? WHERE id=?",
                (email_enc, senha_enc, senha2_enc, rid),
            )

    print(
        f"OK: {len(recifradas)} credencial(is) re-cifrada(s). "
        "Atualize CREDENTIALS_KEY no .env para a nova chave e reinicie o backend."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
