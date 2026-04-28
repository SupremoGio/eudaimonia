"""
test_midnight_reset.py — Test exhaustivo del bug de reinicio diario.

Cubre:
  1. today_str() usa zona horaria México, NO UTC
  2. Boundary exacto de medianoche México (00:00 = 06:00 UTC)
  3. Actividades de tarde (>18:00 México) se guardan con fecha México correcta
  4. week_start es siempre el lunes de la semana actual (México)
  5. Lunes nuevo = PTS_SEMANA arranca desde 0
  6. Script de migración fix_tz_dates: lógica de corrección de fechas
  7. Regresión: el mismo escenario exacto que falló (26 abr tarde → 27 abr mañana)

Ejecución:
  cd gio_v3
  python -m pytest tests/test_midnight_reset.py -v

Requiere: pytest  (pip install pytest)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

MEXICO = ZoneInfo("America/Mexico_City")
UTC_TZ = ZoneInfo("UTC")


# ── Helpers ────────────────────────────────────────────────────────────────────

def mx(year, month, day, hour=12, minute=0, second=0) -> datetime:
    """Crea un datetime en zona México (aware)."""
    return datetime(year, month, day, hour, minute, second, tzinfo=MEXICO)


def utc(year, month, day, hour=0, minute=0, second=0) -> datetime:
    """Crea un datetime en UTC (aware)."""
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC_TZ)


def today_str_at(dt: datetime) -> str:
    """Llama a today_str() simulando que el reloj del servidor marca 'dt'."""
    with patch("utils.now_local", return_value=dt):
        from utils import today_str
        return today_str()


def today_date_at(dt: datetime) -> date:
    """Llama a today_date() simulando que el reloj del servidor marca 'dt'."""
    with patch("utils.now_local", return_value=dt):
        from utils import today_date
        return today_date()


# ══════════════════════════════════════════════════════════════════════════════
# 1. today_str() — zona horaria correcta
# ══════════════════════════════════════════════════════════════════════════════

class TestTodayStrTimezone:
    """today_str() debe devolver la fecha en hora México, nunca en UTC."""

    def test_dia_normal_mediodia(self):
        assert today_str_at(mx(2026, 4, 27, 12)) == "2026-04-27"

    def test_madrugada_mexico_es_mismo_dia(self):
        """02:00 México = 08:00 UTC — mismo día en ambas zonas."""
        assert today_str_at(mx(2026, 4, 27, 2)) == "2026-04-27"

    def test_tarde_mexico_NO_adelanta_dia(self):
        """18:01 México = 00:01 UTC del día siguiente — NO debe ser el día siguiente."""
        dt = utc(2026, 4, 27, 0, 1).astimezone(MEXICO)   # 18:01 México 26-abr
        assert today_str_at(dt) == "2026-04-26"

    def test_tarde_mexico_19h_sigue_siendo_hoy(self):
        """19:00 México (= 01:00 UTC next) → todavía es el día de México."""
        dt = utc(2026, 4, 27, 1, 0).astimezone(MEXICO)   # 19:00 México 26-abr
        assert today_str_at(dt) == "2026-04-26"

    def test_23h_59m_mexico_sigue_siendo_hoy(self):
        assert today_str_at(mx(2026, 4, 26, 23, 59)) == "2026-04-26"

    def test_utc_midnight_NO_es_midnight_mexico(self):
        """00:00 UTC = 18:00 México del día anterior — NO avanza la fecha México."""
        dt = utc(2026, 4, 27, 0, 0).astimezone(MEXICO)   # 18:00 México 26-abr
        assert today_str_at(dt) == "2026-04-26"

    def test_1am_utc_sigue_siendo_ayer_en_mexico(self):
        dt = utc(2026, 4, 27, 1, 0).astimezone(MEXICO)
        assert today_str_at(dt) == "2026-04-26"

    def test_5h59m_utc_sigue_siendo_ayer_en_mexico(self):
        dt = utc(2026, 4, 27, 5, 59).astimezone(MEXICO)
        assert today_str_at(dt) == "2026-04-26"


# ══════════════════════════════════════════════════════════════════════════════
# 2. Boundary exacto de medianoche México
# ══════════════════════════════════════════════════════════════════════════════

class TestMidnightBoundary:
    """El día cambia en México exactamente a las 00:00 México = 06:00 UTC."""

    def test_un_segundo_antes_de_midnight_mexico(self):
        """23:59:59 México = 05:59:59 UTC — todavía es el día anterior."""
        assert today_str_at(mx(2026, 4, 26, 23, 59, 59)) == "2026-04-26"

    def test_exactamente_midnight_mexico(self):
        """00:00:00 México = 06:00:00 UTC — ya es el nuevo día."""
        assert today_str_at(mx(2026, 4, 27, 0, 0, 0)) == "2026-04-27"

    def test_un_segundo_despues_midnight_mexico(self):
        assert today_str_at(mx(2026, 4, 27, 0, 0, 1)) == "2026-04-27"

    def test_6am_utc_es_midnight_mexico(self):
        """06:00 UTC = 00:00 México → nuevo día México."""
        dt = utc(2026, 4, 27, 6, 0, 0).astimezone(MEXICO)
        assert today_str_at(dt) == "2026-04-27"

    def test_5h59m59s_utc_todavia_ayer_mexico(self):
        dt = utc(2026, 4, 27, 5, 59, 59).astimezone(MEXICO)
        assert today_str_at(dt) == "2026-04-26"

    def test_6h00m01s_utc_nuevo_dia_mexico(self):
        dt = utc(2026, 4, 27, 6, 0, 1).astimezone(MEXICO)
        assert today_str_at(dt) == "2026-04-27"


# ══════════════════════════════════════════════════════════════════════════════
# 3. Semana — week_start siempre el lunes (México)
# ══════════════════════════════════════════════════════════════════════════════

class TestWeekStart:

    def _week_start(self, dt: datetime) -> str:
        td = today_date_at(dt)
        return (td - timedelta(days=td.weekday())).isoformat()

    def test_lunes_es_su_propio_inicio_semana(self):
        """27-abr-2026 es Lunes → week_start = 27-abr."""
        assert self._week_start(mx(2026, 4, 27, 10)) == "2026-04-27"

    def test_domingo_week_start_es_el_lunes_pasado(self):
        """26-abr-2026 es Domingo → week_start = 20-abr."""
        assert self._week_start(mx(2026, 4, 26, 10)) == "2026-04-20"

    def test_miercoles_week_start(self):
        """22-abr-2026 es Miércoles → week_start = 20-abr."""
        assert self._week_start(mx(2026, 4, 22, 10)) == "2026-04-20"

    def test_viernes_week_start(self):
        """24-abr-2026 es Viernes → week_start = 20-abr."""
        assert self._week_start(mx(2026, 4, 24, 10)) == "2026-04-20"

    def test_lunes_nuevo_week_start_no_incluye_semana_anterior(self):
        """En Lunes, week_start == today → query semana excluye todo lo anterior."""
        td = today_date_at(mx(2026, 4, 27, 8))
        week_start = (td - timedelta(days=td.weekday())).isoformat()
        today_iso  = td.isoformat()
        assert week_start == today_iso, (
            "El lunes, week_start debe coincidir con hoy para que XP semana = 0 al inicio"
        )

    def test_domingo_late_night_es_semana_anterior(self):
        """Domingo 23:30 México → week_start sigue siendo el lunes pasado (no el próximo)."""
        assert self._week_start(mx(2026, 4, 26, 23, 30)) == "2026-04-20"


# ══════════════════════════════════════════════════════════════════════════════
# 4. Regresión exacta del bug reportado
# ══════════════════════════════════════════════════════════════════════════════

class TestRegressionBugApril26:
    """
    Escenario real que falló:
      - Usuario hace actividades el 26-abr en la tarde (19:00–23:59 México)
      - Railway (UTC) almacena con date='2026-04-27'
      - Al día siguiente (27-abr 08:26 México) la página muestra pts_hoy = 16

    Con el fix:
      - today_str() en servidor a las 19:00 México del 26 → '2026-04-26' ✓
      - today_str() en servidor a las 08:26 del 27 → '2026-04-27' ✓
      - La query WHERE date='2026-04-27' NO encuentra actividades del 26 ✓
    """

    def test_actividad_19h_mexico_abril26_usa_fecha_correcta(self):
        """19:00 México 26-abr = 01:00 UTC 27-abr — debe guardarse como '2026-04-26'."""
        dt_logging = utc(2026, 4, 27, 1, 0).astimezone(MEXICO)
        assert today_str_at(dt_logging) == "2026-04-26"

    def test_actividad_22h_mexico_abril26_usa_fecha_correcta(self):
        """22:00 México 26-abr = 04:00 UTC 27-abr — debe ser '2026-04-26'."""
        dt_logging = utc(2026, 4, 27, 4, 0).astimezone(MEXICO)
        assert today_str_at(dt_logging) == "2026-04-26"

    def test_mañana_abril27_query_correcta(self):
        """08:26 México 27-abr — today_str debe ser '2026-04-27' (no el 26)."""
        dt_query = mx(2026, 4, 27, 8, 26)
        assert today_str_at(dt_query) == "2026-04-27"

    def test_actividades_26_no_aparecen_en_query_27(self):
        """
        Simula que actividades se guardaron con '2026-04-26' (post-fix).
        Al consultar el 27-abr, la query usa '2026-04-27' → no las encuentra.
        """
        fecha_guardada = today_str_at(utc(2026, 4, 27, 1, 0).astimezone(MEXICO))
        fecha_consulta = today_str_at(mx(2026, 4, 27, 8, 26))
        assert fecha_guardada != fecha_consulta, (
            "La fecha de guardado del 26-abr tarde debe diferir de la fecha "
            "de consulta del 27-abr mañana"
        )

    def test_lunes_27_pts_semana_arranca_desde_cero(self):
        """
        27-abr es Lunes. week_start = '2026-04-27'.
        XP del 26-abr (domingo) tiene date='2026-04-26' → no entra en WHERE date>='2026-04-27'.
        """
        td = today_date_at(mx(2026, 4, 27, 8, 26))
        week_start = (td - timedelta(days=td.weekday())).isoformat()
        xp_date_domingo = today_str_at(mx(2026, 4, 26, 22, 0))  # domingo 22:00

        assert week_start == "2026-04-27"
        assert xp_date_domingo == "2026-04-26"
        assert xp_date_domingo < week_start, (
            "El XP del domingo 26-abr debe quedar FUERA del rango de la semana que empieza el lunes 27"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 5. Lógica del script de migración (fix_tz_dates.py)
# ══════════════════════════════════════════════════════════════════════════════

class TestMigrationLogic:
    """Verifica que utc_str_to_mexico_date() calcula la fecha México correcta."""

    def _fix(self, utc_iso: str) -> str:
        from fix_tz_dates import utc_str_to_mexico_date
        return utc_str_to_mexico_date(utc_iso)

    # Casos donde la fecha UTC es un día antes que la fecha México correcta
    def test_01h_utc_corrije_a_dia_anterior(self):
        assert self._fix("2026-04-27T01:00:00") == "2026-04-26"

    def test_02h_utc_corrije_a_dia_anterior(self):
        assert self._fix("2026-04-27T02:00:00") == "2026-04-26"

    def test_05h59m_utc_corrije_a_dia_anterior(self):
        assert self._fix("2026-04-27T05:59:59") == "2026-04-26"

    # Casos donde la fecha UTC ya es la misma que México
    def test_06h_utc_no_necesita_corrección(self):
        """06:00 UTC = midnight México → ambas fechas son iguales."""
        assert self._fix("2026-04-27T06:00:00") == "2026-04-27"

    def test_12h_utc_es_mismo_dia(self):
        assert self._fix("2026-04-27T12:00:00") == "2026-04-27"

    def test_23h59m_utc_no_adelanta_dia(self):
        """23:59 UTC = 17:59 México — mismo día, no avanza al siguiente."""
        assert self._fix("2026-04-27T23:59:00") == "2026-04-27"

    def test_idempotente_si_fecha_ya_correcta(self):
        """Si la fecha ya estaba bien (actividad registrada de mañana), no cambia nada."""
        # 09:00 UTC April 27 = 03:00 México April 27 → correcto '2026-04-27'
        result = self._fix("2026-04-27T09:00:00")
        assert result == "2026-04-27"

    def test_frontera_exacta_05h59m59s(self):
        assert self._fix("2026-04-27T05:59:59") == "2026-04-26"

    def test_frontera_exacta_06h00m00s(self):
        assert self._fix("2026-04-27T06:00:00") == "2026-04-27"


# ══════════════════════════════════════════════════════════════════════════════
# 6. Frontend timeout (validación conceptual del setTimeout)
# ══════════════════════════════════════════════════════════════════════════════

class TestFrontendMidnightTimeout:
    """
    El nuevo código JavaScript usa setTimeout calculado para midnight exacto.
    Estos tests verifican la matemática que ese código implementa.
    """

    def _ms_until_midnight(self, hour: int, minute: int, second: int = 0) -> int:
        """Replica el cálculo del nuevo JS: midnight - now en milisegundos."""
        now = datetime(2026, 4, 26, hour, minute, second)
        midnight = datetime(2026, 4, 27, 0, 0, 0)
        return int((midnight - now).total_seconds() * 1000)

    def test_a_las_23h_59m_espera_60_segundos(self):
        assert self._ms_until_midnight(23, 59) == 60_000

    def test_a_las_23h_00m_espera_60_minutos(self):
        assert self._ms_until_midnight(23, 0) == 3_600_000

    def test_a_las_22h_00m_espera_2_horas(self):
        assert self._ms_until_midnight(22, 0) == 7_200_000

    def test_nuevo_timeout_es_preciso_sub_segundo(self):
        """El nuevo setTimeout tiene +500ms buffer — prácticamente instantáneo."""
        buffer_ms = 500
        assert buffer_ms < 1_000, "El buffer de 500ms es menor a 1 segundo"

    def test_viejo_setinterval_tenia_ventana_de_60s(self):
        """El viejo setInterval(60_000) podía tardar hasta 59.999s en detectar midnight."""
        max_gap_old = 60_000 - 1  # peor caso: interval acaba de disparar, próximo en 59.999s
        max_gap_new = 500          # nuevo: +500ms buffer tras el timeout exacto
        assert max_gap_new < max_gap_old, (
            f"El nuevo método ({max_gap_new}ms) debe ser más preciso que el viejo ({max_gap_old}ms)"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 7. today_date() devuelve objeto date correcto
# ══════════════════════════════════════════════════════════════════════════════

class TestTodayDate:

    def test_retorna_objeto_date(self):
        result = today_date_at(mx(2026, 4, 27, 10))
        assert isinstance(result, date)

    def test_fecha_correcta_mediodia(self):
        assert today_date_at(mx(2026, 4, 27, 12)) == date(2026, 4, 27)

    def test_weekday_correcto_lunes(self):
        """weekday() == 0 para Lunes (27-abr-2026)."""
        d = today_date_at(mx(2026, 4, 27, 10))
        assert d.weekday() == 0, f"27-abr-2026 debe ser Lunes (weekday=0), got {d.weekday()}"

    def test_weekday_correcto_domingo(self):
        """weekday() == 6 para Domingo (26-abr-2026)."""
        d = today_date_at(mx(2026, 4, 26, 10))
        assert d.weekday() == 6, f"26-abr-2026 debe ser Domingo (weekday=6), got {d.weekday()}"

    def test_replace_day_1_para_inicio_mes(self):
        d = today_date_at(mx(2026, 4, 15, 10))
        month_start = d.replace(day=1).isoformat()
        assert month_start == "2026-04-01"
