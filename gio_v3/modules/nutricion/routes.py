from flask import Blueprint, render_template, request, jsonify
from database import get_db
from data import DAYS_ES, MEAL_TYPES
from datetime import date, datetime, timedelta

nutricion_bp = Blueprint('nutricion', __name__, template_folder='../../templates')


def current_week_start():
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


@nutricion_bp.route('/')
def index():
    ws = current_week_start()
    with get_db() as db:
        meals = db.execute(
            "SELECT * FROM meal_plan WHERE week_start=? ORDER BY id", (ws,)
        ).fetchall()

    # Build calendar structure
    calendar = {}
    for day in DAYS_ES:
        calendar[day] = {mt: None for mt in MEAL_TYPES}
    for m in meals:
        if m["day_name"] in calendar and m["meal_type"] in calendar[m["day_name"]]:
            calendar[m["day_name"]][m["meal_type"]] = dict(m)

    return render_template('nutricion/index.html',
        calendar=calendar, days=DAYS_ES, meal_types=MEAL_TYPES,
        week_start=ws, today=date.today().isoformat(),
    )


@nutricion_bp.route('/api/meal', methods=['POST'])
def add_meal():
    d = request.json
    if not d.get('description'): return jsonify({'error':'description required'}), 400
    ws = current_week_start()
    with get_db() as db:
        # Upsert: delete existing slot first
        db.execute("""DELETE FROM meal_plan
            WHERE week_start=? AND day_name=? AND meal_type=?""",
            (ws, d['day_name'], d['meal_type']))
        db.execute("""INSERT INTO meal_plan
            (week_start, day_name, meal_type, description, video_url, created_at)
            VALUES (?,?,?,?,?,?)""",
            (ws, d['day_name'], d['meal_type'], d['description'],
             d.get('video_url',''), datetime.now().isoformat()))
        db.commit()
    return jsonify({'ok':True})


@nutricion_bp.route('/api/meal/<int:mid>', methods=['DELETE'])
def delete_meal(mid):
    with get_db() as db:
        db.execute("DELETE FROM meal_plan WHERE id=?", (mid,))
        db.commit()
    return jsonify({'ok':True})


@nutricion_bp.route('/api/meal/<int:mid>', methods=['PUT'])
def update_meal(mid):
    d = request.json
    with get_db() as db:
        db.execute("UPDATE meal_plan SET description=?, video_url=? WHERE id=?",
                   (d['description'], d.get('video_url',''), mid))
        db.commit()
    return jsonify({'ok':True})


@nutricion_bp.route('/api/nutrition/articles')
def nutrition_articles():
    """
    Placeholder endpoint — ready for real nutrition API integration.
    Future: connect to Nutritionix, USDA FoodData Central, or Edamam API.
    """
    mock_articles = [
        {"id":1,"title":"The Power of Protein Timing","category":"Muscle","read_time":"4 min","summary":"Consuming protein within 2 hours post-workout maximizes muscle protein synthesis.","source":"Mock"},
        {"id":2,"title":"Omega-3 and Cognitive Performance","category":"Brain","read_time":"3 min","summary":"DHA-rich omega-3 fatty acids support focus, memory, and stress resilience.","source":"Mock"},
        {"id":3,"title":"Intermittent Fasting: 16:8 Protocol","category":"Metabolismo","read_time":"5 min","summary":"Time-restricted eating can improve insulin sensitivity and support fat loss without muscle loss.","source":"Mock"},
        {"id":4,"title":"Magnesium: The Recovery Mineral","category":"Recovery","read_time":"3 min","summary":"Magnesium deficiency is linked to poor sleep, muscle cramps, and elevated cortisol.","source":"Mock"},
        {"id":5,"title":"Hydration and Athletic Performance","category":"Performance","read_time":"2 min","summary":"Even 2% dehydration can reduce physical and cognitive performance significantly.","source":"Mock"},
    ]
    return jsonify({"ok":True,"articles":mock_articles,"note":"Mock data — real API integration ready."})
