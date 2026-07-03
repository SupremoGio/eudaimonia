import json, random
from flask import Blueprint, render_template, request, jsonify
from database import get_db
from datetime import date, timedelta
from utils import today_str, today_date

nutricion_bp = Blueprint('nutricion', __name__, template_folder='../../templates')

# ── Helpers de tiempo/semana ──────────────────────────────────────────────────

DAY_KEYS = {0: 'L', 1: 'M', 2: 'X', 3: 'J', 4: 'V', 5: 'S', 6: 'D'}

def get_week_start():
    td = today_date()
    return td - timedelta(days=td.weekday())

def get_today_key():
    return DAY_KEYS[today_date().weekday()]

# ── Plantilla base de 5 comidas FODMAP ───────────────────────────────────────

PLAN_TEMPLATE = [
    {
        'slot': 'Desayuno', 'time': '07:00', 'xp': 12, 'tag': 'safe',
        'name': 'Huevos + tortilla de maíz + papaya',
        'kcal': 420, 'protein': 28,
        'note': 'Base proteica limpia. Sin lácteos, sin harina refinada.',
        'items': [
            {'t': '2 huevos revueltos en aceite de oliva', 'tag': 'safe'},
            {'t': '2 tortillas de maíz (nixtamal)', 'tag': 'safe'},
            {'t': '1 taza de papaya', 'tag': 'safe'},
            {'t': 'Té verde suave (no café)', 'tag': 'caution', 'why': 'Cafeína moderada — evita el exceso'},
        ],
        'swap': 'Cambia papaya por kiwi o fresas si prefieres.',
    },
    {
        'slot': 'Colación AM', 'time': '10:30', 'xp': 8, 'tag': 'safe',
        'name': 'Nueces + plátano firme',
        'kcal': 230, 'protein': 6,
        'note': 'Grasa buena + energía estable pre-tarde.',
        'items': [
            {'t': '10 mitades de nuez', 'tag': 'safe'},
            {'t': '1 plátano poco maduro', 'tag': 'caution', 'why': 'Maduro = más fructanos. Elígelo firme.'},
        ],
        'swap': 'Cambia nueces por cacahuate natural (sin azúcar).',
    },
    {
        'slot': 'Comida', 'time': '14:00', 'xp': 14, 'tag': 'safe',
        'name': 'Pollo a la plancha + arroz + calabacita',
        'kcal': 560, 'protein': 42,
        'note': 'Comida ancla del día. Arroz = carbo seguro y digerible.',
        'items': [
            {'t': '180 g pechuga de pollo a la plancha', 'tag': 'safe'},
            {'t': '1 taza de arroz blanco', 'tag': 'safe'},
            {'t': 'Calabacita + zanahoria salteadas', 'tag': 'safe'},
            {'t': 'Aceite de oliva + limón', 'tag': 'safe'},
        ],
        'swap': 'Sin ajo ni cebolla — usa aceite infusionado o cebollín (parte verde).',
    },
    {
        'slot': 'Colación PM', 'time': '17:30', 'xp': 8, 'tag': 'safe',
        'name': 'Batido de proteína + cacahuate',
        'kcal': 280, 'protein': 30,
        'note': 'Aislado sin lactosa. Rendimiento sin inflamar.',
        'items': [
            {'t': '1 scoop aislado de proteína SIN lactosa', 'tag': 'safe'},
            {'t': '1 cda mantequilla de cacahuate', 'tag': 'safe'},
            {'t': 'Agua o leche de almendra sin endulzar', 'tag': 'safe'},
        ],
        'swap': 'Nada de suero con lactosa ni leche de vaca.',
    },
    {
        'slot': 'Cena', 'time': '20:30', 'xp': 12, 'tag': 'safe',
        'name': 'Salmón + papa + espinaca',
        'kcal': 480, 'protein': 36,
        'note': 'Omega-3 antiinflamatorio. Cena temprana para dormir mejor.',
        'items': [
            {'t': '150 g salmón al horno', 'tag': 'safe'},
            {'t': '1 papa mediana cocida', 'tag': 'safe'},
            {'t': 'Espinaca salteada en oliva', 'tag': 'safe'},
        ],
        'swap': 'Cambia salmón por pescado blanco si lo prefieres ligero.',
    },
]

TEMPTATIONS_MAP = {
    'cafe':    {'label': 'Café de más',       'glyph': '☕', 'pen': 5},
    'pan':     {'label': 'Pan / harina',      'glyph': '🥖', 'pen': 12},
    'galleta': {'label': 'Galleta / dulce',   'glyph': '🍪', 'pen': 12},
    'lacteo':  {'label': 'Lácteo',            'glyph': '🥛', 'pen': 10},
    'frijol':  {'label': 'Frijol / legumbre', 'glyph': '🫘', 'pen': 8},
    'alcohol': {'label': 'Alcohol',           'glyph': '🍷', 'pen': 12},
    'otro':    {'label': 'Otro disparador',   'glyph': '⚑',  'pen': 8},
}

STOIC_SLIP = [
    'No te castigues; corrige. Mañana es otro asalto.',
    'El desliz registrado ya es virtud: has vuelto a mirar.',
    'No es la caída, sino la prontitud en levantarte.',
    'Ningún hombre es libre si no es dueño de sí mismo.',
    'Recomienza. Cada acto es una vida entera.',
]

# ── DB helpers ────────────────────────────────────────────────────────────────

def seed_week(db, week_str):
    for day_key in ['L', 'M', 'X', 'J', 'V']:
        for m in PLAN_TEMPLATE:
            db.execute(
                """INSERT INTO nutricion_semana
                   (week_start,day_key,slot,time_str,name,kcal,protein,tag,note,items_json,swap,xp)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                [week_str, day_key, m['slot'], m['time'], m['name'],
                 m['kcal'], m['protein'], m['tag'], m.get('note', ''),
                 json.dumps(m.get('items', [])), m.get('swap', ''), m['xp']]
            )
    db.commit()


def get_or_seed_week(db, week_str):
    rows = db.execute(
        'SELECT * FROM nutricion_semana WHERE week_start=? ORDER BY id', [week_str]
    ).fetchall()
    if not rows:
        seed_week(db, week_str)
        rows = db.execute(
            'SELECT * FROM nutricion_semana WHERE week_start=? ORDER BY id', [week_str]
        ).fetchall()
    return rows


def rows_to_week(rows):
    week = {k: [] for k in ['L', 'M', 'X', 'J', 'V', 'S', 'D']}
    for r in rows:
        week[r['day_key']].append({
            'id': r['id'],
            'slot': r['slot'],
            'time': r['time_str'],
            'xp': r['xp'],
            'tag': r['tag'],
            'name': r['name'],
            'kcal': r['kcal'],
            'protein': r['protein'],
            'note': r['note'] or '',
            'items': json.loads(r['items_json'] or '[]'),
            'swap': r['swap'] or '',
            'custom': bool(r['custom']),
            'done': bool(r['done']),
            'symptom': r['symptom'],
            'sym_tags': json.loads(r['sym_tags_json'] or '[]'),
        })
    for k in week:
        week[k].sort(key=lambda m: m['time'])
    return week


def get_streak(db):
    row = db.execute(
        "SELECT value FROM app_settings WHERE key='nutricion_streak'"
    ).fetchone()
    return int(row['value']) if row else 0


def set_streak(db, val):
    db.execute(
        "INSERT OR REPLACE INTO app_settings(key,value) VALUES('nutricion_streak',?)", [str(val)]
    )


def get_xp_today(db):
    today = today_str()
    row = db.execute(
        "SELECT COALESCE(SUM(amount),0) as s FROM xp_ledger WHERE source='nutricion' AND date=?", [today]
    ).fetchone()
    return int(row['s'])


def get_ec_today(db):
    today = today_str()
    row = db.execute(
        "SELECT COALESCE(SUM(amount),0) as s FROM coins_ledger WHERE source='nutricion' AND date=?", [today]
    ).fetchone()
    return int(row['s'])


def award_xp(db, amount, ref_id=None, desc=''):
    db.execute(
        "INSERT INTO xp_ledger(amount,source,reference_id,description,date,created_at) VALUES(?,?,?,?,?,datetime('now'))",
        [amount, 'nutricion', ref_id, desc, today_str()]
    )


def award_ec(db, amount, desc=''):
    db.execute(
        "INSERT INTO coins_ledger(amount,source,description,date,created_at) VALUES(?,?,?,?,datetime('now'))",
        [amount, 'nutricion', desc, today_str()]
    )


# ── Rutas ─────────────────────────────────────────────────────────────────────

@nutricion_bp.route('/')
def index():
    week_start = get_week_start()
    week_str = week_start.isoformat()
    today_key = get_today_key()
    today = today_str()

    with get_db() as db:
        rows = get_or_seed_week(db, week_str)
        week = rows_to_week(rows)

        slips = [dict(r) for r in db.execute(
            'SELECT * FROM nutricion_deslices WHERE date=? ORDER BY id', [today]
        ).fetchall()]

        bristol_row = db.execute(
            'SELECT valor FROM nutricion_bristol WHERE date=? ORDER BY id DESC LIMIT 1', [today]
        ).fetchone()

        xp_today = get_xp_today(db)
        ec_today = get_ec_today(db)
        streak = get_streak(db)

    state = {
        'week': week,
        'today': today_key,
        'week_start': week_str,
        'xp_today': xp_today,
        'ec_today': ec_today,
        'streak': streak,
        'slips': slips,
        'bristol': bristol_row['valor'] if bristol_row else None,
    }

    return render_template('nutricion/index.html', state=state)


@nutricion_bp.route('/api/cumplir', methods=['POST'])
def cumplir():
    data = request.get_json()
    meal_id = data['meal_id']

    with get_db() as db:
        meal = db.execute('SELECT * FROM nutricion_semana WHERE id=?', [meal_id]).fetchone()
        if not meal or meal['done']:
            return jsonify({'error': 'not found or already done'}), 400

        db.execute('UPDATE nutricion_semana SET done=1 WHERE id=?', [meal_id])
        award_xp(db, meal['xp'], ref_id=meal_id, desc=meal['slot'])

        week_str = get_week_start().isoformat()
        today_key = get_today_key()
        today = today_str()

        today_meals = db.execute(
            'SELECT * FROM nutricion_semana WHERE week_start=? AND day_key=?',
            [week_str, today_key]
        ).fetchall()

        all_done = all(m['done'] or m['id'] == meal_id for m in today_meals)
        slip_count = db.execute(
            'SELECT COUNT(*) as c FROM nutricion_deslices WHERE date=?', [today]
        ).fetchone()['c']

        bonus_xp = 0
        bonus_ec = 0
        new_streak = get_streak(db)

        if all_done and slip_count == 0:
            bonus_xp = 30
            bonus_ec = 8
            award_xp(db, 30, desc='día limpio bonus')
            award_ec(db, 8, desc='día cerrado')
            new_streak += 1
            set_streak(db, new_streak)

        db.commit()

        return jsonify({
            'xp_earned': meal['xp'],
            'bonus_xp': bonus_xp,
            'bonus_ec': bonus_ec,
            'total_xp': get_xp_today(db),
            'total_ec': get_ec_today(db),
            'streak': new_streak,
            'all_done': all_done and slip_count == 0,
        })


@nutricion_bp.route('/api/sintoma', methods=['POST'])
def sintoma():
    data = request.get_json()
    meal_id = data['meal_id']
    feeling = data['feeling']
    tags = data.get('tags', [])

    with get_db() as db:
        db.execute(
            'UPDATE nutricion_semana SET symptom=?, sym_tags_json=? WHERE id=?',
            [feeling, json.dumps(tags), meal_id]
        )
        award_xp(db, 5, ref_id=meal_id, desc='registro síntoma')
        db.commit()
        return jsonify({'xp_earned': 5, 'total_xp': get_xp_today(db)})


@nutricion_bp.route('/api/desliz', methods=['POST'])
def desliz():
    data = request.get_json()
    trig_id = data['trig_id']
    over = data.get('over', False)
    note = data.get('note', '')

    trig = TEMPTATIONS_MAP.get(trig_id, TEMPTATIONS_MAP['otro'])
    pen = round(trig['pen'] * (1.5 if over else 1))

    with get_db() as db:
        today = today_str()
        db.execute(
            'INSERT INTO nutricion_deslices(date,trig_id,label,glyph,pen,over,note) VALUES(?,?,?,?,?,?,?)',
            [today, trig_id, trig['label'], trig['glyph'], pen, 1 if over else 0, note]
        )
        award_xp(db, -pen, desc=f'desliz {trig["label"]}')
        set_streak(db, 0)
        db.commit()
        return jsonify({
            'pen': pen,
            'msg': random.choice(STOIC_SLIP),
            'total_xp': get_xp_today(db),
            'streak': 0,
            'slip': {
                'id': db.execute('SELECT last_insert_rowid() as i').fetchone()['i'],
                'label': trig['label'],
                'glyph': trig['glyph'],
                'pen': pen,
                'over': over,
                'note': note,
            }
        })


@nutricion_bp.route('/api/bristol', methods=['POST'])
def bristol():
    data = request.get_json()
    valor = data['valor']
    today = today_str()
    with get_db() as db:
        db.execute('DELETE FROM nutricion_bristol WHERE date=?', [today])
        db.execute('INSERT INTO nutricion_bristol(date,valor) VALUES(?,?)', [today, valor])
        db.commit()
    return jsonify({'ok': True})


@nutricion_bp.route('/api/comida', methods=['POST'])
def add_comida():
    data = request.get_json()
    week_str = get_week_start().isoformat()
    day_key = data.get('day', get_today_key())
    slot = data['slot']
    xp = 8 if 'Colación' in slot else 12

    with get_db() as db:
        db.execute(
            """INSERT INTO nutricion_semana
               (week_start,day_key,slot,time_str,name,kcal,protein,tag,note,items_json,swap,xp,custom)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            [week_str, day_key, slot, data.get('time', '12:00'), data['name'],
             data.get('kcal', 0), data.get('protein', 0), data.get('tag', 'safe'),
             data.get('note', 'Comida personalizada.'),
             json.dumps(data.get('items', [])), data.get('swap', ''), xp]
        )
        db.commit()
        meal_id = db.execute('SELECT last_insert_rowid() as i').fetchone()['i']
        r = db.execute('SELECT * FROM nutricion_semana WHERE id=?', [meal_id]).fetchone()
        return jsonify({'meal': {
            'id': r['id'], 'slot': r['slot'], 'time': r['time_str'], 'xp': r['xp'],
            'tag': r['tag'], 'name': r['name'], 'kcal': r['kcal'], 'protein': r['protein'],
            'note': r['note'], 'items': json.loads(r['items_json'] or '[]'),
            'swap': r['swap'], 'custom': True, 'done': False, 'symptom': None, 'sym_tags': [],
        }})


@nutricion_bp.route('/api/comida/<int:meal_id>', methods=['DELETE'])
def delete_comida(meal_id):
    with get_db() as db:
        r = db.execute('SELECT name FROM nutricion_semana WHERE id=?', [meal_id]).fetchone()
        db.execute('DELETE FROM nutricion_semana WHERE id=?', [meal_id])
        db.commit()
    return jsonify({'ok': True, 'name': r['name'] if r else ''})


@nutricion_bp.route('/api/repetir', methods=['POST'])
def repetir():
    data = request.get_json()
    src_day = data['src_day']
    week_str = get_week_start().isoformat()
    today_key = get_today_key()

    with get_db() as db:
        src = db.execute(
            'SELECT * FROM nutricion_semana WHERE week_start=? AND day_key=?', [week_str, src_day]
        ).fetchall()

        for dk in ['L', 'M', 'X', 'J', 'V']:
            if dk == today_key:
                continue
            db.execute(
                'DELETE FROM nutricion_semana WHERE week_start=? AND day_key=?', [week_str, dk]
            )
            for m in src:
                db.execute(
                    """INSERT INTO nutricion_semana
                       (week_start,day_key,slot,time_str,name,kcal,protein,tag,note,items_json,swap,xp,custom)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [week_str, dk, m['slot'], m['time_str'], m['name'],
                     m['kcal'], m['protein'], m['tag'], m['note'],
                     m['items_json'], m['swap'], m['xp'], m['custom']]
                )
        db.commit()

        rows = db.execute(
            'SELECT * FROM nutricion_semana WHERE week_start=? ORDER BY id', [week_str]
        ).fetchall()
        return jsonify({'week': rows_to_week(rows)})
