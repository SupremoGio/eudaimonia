"""
Contrapartes: quién está del otro lado de una transferencia BNET.

BBVA pone la cuenta de la contraparte en la descripción («BNET …6230 cositas»).
Solo se guardan los últimos 4 dígitos (nunca la cuenta completa). Cada
contraparte tiene nombre visible, alias y la categoría que suele tener lo que
manda o lo que se le manda; se configuran desde la app (pestaña Reglas).

Resolución (resolver()): un alias en el concepto gana sobre la cuenta — a
Cornelius a veces se le paga a la cuenta de Judith (…6230) con concepto
«regreso al corner»: ese movimiento es de Cornelius. Solo cuentan alias de 4
letras o más (o de varias palabras), por palabra completa.

Columnas en est_movimientos:
  cuenta_contraparte  los 4 dígitos que trae el banco (si los trae)
  contraparte         la cuenta (4 dígitos) de la contraparte que resultó
"""
import json
import re
from datetime import datetime

# Semilla (2026-10-04, PROMPT_CLAUDE_CODE_contrapartes_y_viaje.md). Solo se
# inserta si la cuenta no existe: lo que el usuario edite en la app se respeta.
# reglas: [(palabra del concepto, lado 'abono'/'cargo', 'CATEGORIA/Subcategoría')]
SEMILLA = (
    {'cuenta': '1239', 'nombre': 'Papá', 'alias': ['Eli', 'Pops', 'Transf a ELIEN A'],
     'cat_abono': 'OTROS/', 'cat_cargo': '', 'reglas': [('SEGURO', 'cargo', 'TRANSPORTE/Seguro auto')], 'auto': 0},
    {'cuenta': '3042', 'nombre': 'Mamá', 'alias': ['Lenis', 'p'],
     'cat_abono': 'FINANZAS/Reembolso compartido', 'cat_cargo': '', 'reglas': [], 'auto': 1},
    {'cuenta': '6230', 'nombre': 'Judith', 'alias': ['Judi', 'Judicial'],
     'cat_abono': 'FINANZAS/Reembolso compartido', 'cat_cargo': '',
     'reglas': [('PRESTAMO', 'cargo', 'PRESTAMOS/Prestado')], 'auto': 0},
    {'cuenta': '5937', 'nombre': 'Cornelius', 'alias': ['Corner', 'deyvi cornelio'],
     'cat_abono': '', 'cat_cargo': '', 'reglas': [], 'auto': 0},
    {'cuenta': '6197', 'nombre': 'Gastos compartidos', 'alias': [],
     'cat_abono': 'FINANZAS/Reembolso compartido', 'cat_cargo': '', 'reglas': [], 'auto': 1},
)

# «BNET …6230», «BNET ******6230», «CUENTA: …5198», «…3042» suelto.
_CUENTA_RE = re.compile(r'(?:BNET|CUENTA:?)\s*(?:…|\.{2,}|\*+|X{2,})\s*(\d{4})\b|…\s*(\d{4})\b', re.IGNORECASE)

# Categorías «genéricas» del import: una sugerencia por contraparte puede
# reemplazarlas; cualquier otra la eligió el usuario y no se toca.
GENERICAS = {('', ''), ('OTROS', ''), ('FINANZAS', ''), ('FINANZAS', 'Transferencia'),
             ('FINANZAS', 'Transferencia recibida'), ('FINANZAS', 'Transferencia enviada')}


def asegurar(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS est_contrapartes (
                      cuenta     TEXT PRIMARY KEY,
                      nombre     TEXT NOT NULL,
                      alias      TEXT DEFAULT '[]',
                      cat_abono  TEXT DEFAULT '',
                      cat_cargo  TEXT DEFAULT '',
                      reglas     TEXT DEFAULT '[]',
                      auto       INTEGER DEFAULT 0,
                      created_at TEXT NOT NULL)""")
    for col in ('cuenta_contraparte', 'contraparte'):
        try:
            db.execute(f"ALTER TABLE est_movimientos ADD COLUMN {col} TEXT DEFAULT NULL")
        except Exception:
            pass
    db.execute("CREATE INDEX IF NOT EXISTS idx_est_mov_contraparte ON est_movimientos(contraparte)")
    for c in SEMILLA:
        db.execute("""INSERT OR IGNORE INTO est_contrapartes (cuenta, nombre, alias, cat_abono, cat_cargo, reglas, auto, created_at)
                      VALUES (?,?,?,?,?,?,?,?)""",
                   (c['cuenta'], c['nombre'], json.dumps(c['alias'], ensure_ascii=False), c['cat_abono'], c['cat_cargo'],
                    json.dumps(c['reglas'], ensure_ascii=False), c['auto'], datetime.now().isoformat(timespec='seconds')))


def cuenta_de(descripcion: str) -> str | None:
    """Últimos 4 dígitos de la cuenta de la contraparte, si la descripción los trae."""
    m = _CUENTA_RE.search(descripcion or '')
    return (m.group(1) or m.group(2)) if m else None


def _fila(r) -> dict:
    d = dict(r)
    d['alias'] = json.loads(d.get('alias') or '[]')
    d['reglas'] = [list(x) for x in json.loads(d.get('reglas') or '[]')]
    d['auto'] = bool(d.get('auto'))
    return d


def listar(db) -> list[dict]:
    return [_fila(r) for r in db.execute("SELECT * FROM est_contrapartes ORDER BY nombre").fetchall()]


def _alias_re(alias: str):
    a = alias.strip()
    if len(a) < 4 and ' ' not in a:
        return None   # «Eli», «p»: demasiado cortos para buscarlos en un concepto
    return re.compile(r'(?<![A-Z0-9ÁÉÍÓÚÑ])' + r'\s+'.join(map(re.escape, a.upper().split())) + r'(?![A-Z0-9ÁÉÍÓÚÑ])')


def resolver(descripcion: str, cuenta: str | None, cps: list[dict]) -> str | None:
    """Cuenta (4 dígitos) de la contraparte de un movimiento, o None."""
    d = (descripcion or '').upper()
    for cp in cps:
        if any((rx := _alias_re(a)) and rx.search(d) for a in cp['alias']):
            return cp['cuenta']
    if cuenta and any(cp['cuenta'] == cuenta for cp in cps):
        return cuenta
    return None


def actualizar(db, ids=None) -> int:
    """Llena cuenta_contraparte (de la descripción, si falta) y recalcula
    contraparte. ids=None: toda la base. Devuelve cuántas filas cambiaron."""
    cps = listar(db)
    q = "SELECT id, descripcion, cuenta_contraparte, contraparte FROM est_movimientos"
    params = []
    if ids is not None:
        ids = list(ids)
        if not ids:
            return 0
        q += f" WHERE id IN ({','.join('?' * len(ids))})"
        params = ids
    n = 0
    for r in db.execute(q, params).fetchall():
        cuenta = r['cuenta_contraparte'] or cuenta_de(r['descripcion'])
        cp = resolver(r['descripcion'], cuenta, cps)
        if (cuenta, cp) != (r['cuenta_contraparte'], r['contraparte']):
            db.execute("UPDATE est_movimientos SET cuenta_contraparte=?, contraparte=? WHERE id=?", (cuenta, cp, r['id']))
            n += 1
    return n


def _limpiar(data: dict) -> dict:
    cuenta = re.sub(r'\D', '', str(data.get('cuenta') or ''))[-4:]
    if len(cuenta) != 4:
        raise ValueError('La cuenta son los últimos 4 dígitos.')
    nombre = str(data.get('nombre') or '').strip()[:60]
    if not nombre:
        raise ValueError('Falta el nombre.')
    alias = data.get('alias') or []
    if isinstance(alias, str):
        alias = [a for a in (x.strip() for x in alias.split(',')) if a]
    reglas = [[str(p).upper().strip(), lado, cat] for p, lado, cat in (data.get('reglas') or [])
              if str(p).strip() and lado in ('abono', 'cargo') and '/' in str(cat)]
    cat = lambda k: str(data.get(k) or '').strip() if '/' in str(data.get(k) or '') else ''
    return {'cuenta': cuenta, 'nombre': nombre, 'alias': [str(a)[:60] for a in alias][:20],
            'cat_abono': cat('cat_abono'), 'cat_cargo': cat('cat_cargo'), 'reglas': reglas, 'auto': 1 if data.get('auto') else 0}


def guardar(db, data: dict) -> dict:
    c = _limpiar(data)
    db.execute("""INSERT INTO est_contrapartes (cuenta, nombre, alias, cat_abono, cat_cargo, reglas, auto, created_at)
                  VALUES (?,?,?,?,?,?,?,?)
                  ON CONFLICT(cuenta) DO UPDATE SET nombre=excluded.nombre, alias=excluded.alias,
                      cat_abono=excluded.cat_abono, cat_cargo=excluded.cat_cargo, reglas=excluded.reglas, auto=excluded.auto""",
               (c['cuenta'], c['nombre'], json.dumps(c['alias'], ensure_ascii=False), c['cat_abono'], c['cat_cargo'],
                json.dumps(c['reglas'], ensure_ascii=False), c['auto'], datetime.now().isoformat(timespec='seconds')))
    actualizar(db)
    return c


def borrar(db, cuenta: str) -> None:
    db.execute("DELETE FROM est_contrapartes WHERE cuenta=?", (cuenta,))
    actualizar(db)


def por_cuenta(db) -> dict:
    return {cp['cuenta']: cp for cp in listar(db)}


def de_persona(db, nombre: str) -> str | None:
    """Cuenta de la contraparte cuyo nombre o alias es `nombre` (ej. un
    compromiso a nombre de «Judicial» o «Corner»)."""
    n = (nombre or '').strip().lower()
    return next((cp['cuenta'] for cp in listar(db)
                 if n and (cp['nombre'].lower() == n or n in (a.lower() for a in cp['alias']))), None)


def sugerencia(cp: dict, tipo: str, descripcion: str):
    """(categoria, subcategoria, texto) que sugiere la contraparte para un
    movimiento, o None. Primero las reglas por palabra; luego la de su lado."""
    lado = 'abono' if tipo == 'INGRESO' else 'cargo'
    d = (descripcion or '').upper()
    for palabra, l, cat in cp['reglas']:
        if l == lado and palabra in d:
            c, _, s = cat.partition('/')
            return c, s, f"{cp['nombre']} (…{cp['cuenta']}): «{palabra.lower()}» → {cat}"
    cat = cp['cat_abono'] if lado == 'abono' else cp['cat_cargo']
    if cat:
        c, _, s = cat.partition('/')
        return c, s, f"{'De' if lado == 'abono' else 'A'} {cp['nombre']} (…{cp['cuenta']}) → {cat}"
    return None


def aplicar_auto(db) -> int:
    """Movimientos de contrapartes marcadas «auto» (ej. Mamá, Gastos
    compartidos) que siguen con categoría genérica: toman la de su lado."""
    n = 0
    cps = {cp['cuenta']: cp for cp in listar(db) if cp['auto']}
    if not cps:
        return 0
    rows = db.execute(f"""SELECT id, tipo, descripcion, categoria, subcategoria, contraparte FROM est_movimientos
                          WHERE contraparte IN ({','.join('?' * len(cps))}) AND tipo IN ('INGRESO', 'GASTO')""",
                      list(cps)).fetchall()
    for r in rows:
        if ((r['categoria'] or ''), (r['subcategoria'] or '')) not in GENERICAS:
            continue
        s = sugerencia(cps[r['contraparte']], r['tipo'], r['descripcion'])
        if s and (s[0], s[1]) != ((r['categoria'] or ''), (r['subcategoria'] or '')):
            db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?", (s[0], s[1], r['id']))
            n += 1
    return n
