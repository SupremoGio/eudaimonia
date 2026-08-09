"""
migrate_strip_emoji_rutina.py — limpia el emoji sembrado en rutina_bloques.nombre.

Las 36 filas de `rutina_bloques` (rutina de sábado/domingo, ver
modules/ataraxia/routes.py) traían un emoji al inicio del nombre como dato
histórico ("🪟 Ventilación Fast Track...") en vez de en código. Hasta ahora
solo se recortaba al mostrar (`_strip_emoji_prefix()`), dejando el dato
crudo sin tocar en la base — esta migración lo limpia de verdad en la
tabla.

Reutiliza el mismo regex que ya usa `_strip_emoji_prefix()` en
ataraxia/routes.py, así que es exactamente equivalente a lo que el usuario
ya ve renderizado. `_strip_emoji_prefix()` se deja en el código a propósito:
una vez migrado el dato es un no-op idempotente, y sirve de red de
seguridad para instalaciones (Railway/Turso) donde esta migración todavía
no se haya corrido.

Idempotente vía migration_log — segura de llamar más de una vez.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
import re

_EMOJI_PREFIX_RE = re.compile(r'^[\U0001F300-\U0001FAFF\U00002600-\U000027BF]️?\s*')


def run_migration():
    from database import get_db

    with get_db() as db:
        if db.execute(
            "SELECT id FROM migration_log WHERE version='strip_emoji_rutina_bloques'"
        ).fetchone():
            return {"status": "already_applied", "version": "strip_emoji_rutina_bloques"}

        rows = db.execute("SELECT id, nombre FROM rutina_bloques").fetchall()
        updated = 0
        for r in rows:
            cleaned = _EMOJI_PREFIX_RE.sub('', r["nombre"])
            if cleaned != r["nombre"]:
                db.execute(
                    "UPDATE rutina_bloques SET nombre=? WHERE id=?", (cleaned, r["id"])
                )
                updated += 1

        db.execute(
            "INSERT INTO migration_log (version, description, applied_at) VALUES (?,?,?)",
            (
                "strip_emoji_rutina_bloques",
                f"Limpia el emoji sembrado en rutina_bloques.nombre ({updated} filas)",
                datetime.datetime.now().isoformat(),
            ),
        )
        db.commit()

    return {"status": "ok", "version": "strip_emoji_rutina_bloques", "updated": updated}


if __name__ == "__main__":
    result = run_migration()
    status = result.get("status")
    if status == "ok":
        print(f"[OK] Migration strip_emoji_rutina_bloques applied — {result.get('updated', '?')} filas limpiadas")
    elif status == "already_applied":
        print("[OK] Migration strip_emoji_rutina_bloques already applied — nada que hacer")
    else:
        print(f"[FAIL] Migration strip_emoji_rutina_bloques failed: {result}")
        sys.exit(1)
