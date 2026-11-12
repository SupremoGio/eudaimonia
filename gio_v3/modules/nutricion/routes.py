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

# ── Menú semanal FODMAP (Semana de reseteo SII — Dr. González / Elizabeth) ────

PLAN_TEMPLATE = {
    'L': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos revueltos con espinacas y ejotes',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 huevos revueltos con espinacas y ejotes picados', 'tag': 'safe'},
                {'t': '2 cdtas de aceite para cocinar', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '1 kiwi', 'tag': 'safe'},
            ],
            'swap': 'Fruta: papaya ↔ kiwi ↔ mandarina ↔ naranja ↔ piña ↔ plátano firme ↔ fresas/moras/blueberries.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Mandarina + naranja + tostadas de arroz + pepino',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '1 mandarina + 1 naranja', 'tag': 'safe'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': 'Pepino con limón', 'tag': 'safe'},
            ],
            'swap': 'Verdura: pepino ↔ zanahoria ↔ jícama ↔ tomates cherry. Cereal: 2 tostadas ↔ 2.5 tazas palomitas naturales ↔ ¼ taza quinoa cocida.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Tostadas de nopal con pollo deshebrado',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 tostadas de maíz horneadas', 'tag': 'safe'},
                {'t': '150 g de pollo deshebrado', 'tag': 'safe'},
                {'t': 'Nopales guisados con aceite infusionado (ajo/cebolla)', 'tag': 'safe'},
            ],
            'swap': 'Proteína: pollo ↔ pescado blanco ↔ res magra ↔ huevo.',
        },
        {
            'slot': 'Pre-gym', 'time': '18:00', 'xp': 8, 'tag': 'safe',
            'name': 'Plátano firme + tostadas con crema de cacahuate',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '1 plátano firme', 'tag': 'caution', 'why': 'Firme (poco maduro) = menos fructanos.'},
                {'t': '2 tostadas de arroz con 1 cdta de crema de cacahuate sin azúcar', 'tag': 'safe'},
            ],
            'swap': 'Fruta: plátano firme ↔ kiwi ↔ papaya chica.',
        },
        {
            'slot': 'Cena', 'time': '20:30', 'xp': 12, 'tag': 'safe',
            'name': 'Tacos de pollo con nopales asados',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '120 g de pechuga asada', 'tag': 'safe'},
                {'t': '2 nopales asados', 'tag': 'safe'},
                {'t': 'Cilantro fresco', 'tag': 'safe'},
                {'t': 'Limón', 'tag': 'safe'},
                {'t': '1 taza de papaya', 'tag': 'safe'},
            ],
            'swap': 'Fruta: papaya ↔ naranja ↔ kiwi.',
        },
    ],
    'M': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos revueltos con calabacita rallada y cilantro',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 huevos revueltos con calabacita rallada y cilantro fresco', 'tag': 'safe'},
                {'t': '2 cdtas de aceite para cocinar', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '1 mandarina', 'tag': 'safe'},
            ],
            'swap': 'Fruta: papaya ↔ kiwi ↔ mandarina ↔ naranja ↔ piña ↔ plátano firme ↔ fresas/moras/blueberries.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Papaya + tostadas de arroz + zanahoria',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '1 taza de papaya', 'tag': 'safe'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': 'Bastones de zanahoria con limón', 'tag': 'safe'},
            ],
            'swap': 'Verdura: pepino ↔ zanahoria ↔ jícama ↔ tomates cherry.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Arroz integral con calabacitas y pollo deshebrado',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '½ taza de arroz integral cocido', 'tag': 'safe'},
                {'t': 'Calabacitas guisadas con cilantro y aceite infusionado de ajo (sin jitomate, sin cebolla)', 'tag': 'safe'},
                {'t': '150 g de pollo deshebrado', 'tag': 'safe'},
                {'t': '1 tortilla de maíz', 'tag': 'safe'},
                {'t': '2 cdtas de aceite', 'tag': 'safe'},
            ],
            'swap': 'Proteína: pollo ↔ pescado blanco ↔ res magra ↔ huevo.',
        },
        {
            'slot': 'Pre-gym', 'time': '18:00', 'xp': 8, 'tag': 'safe',
            'name': 'Kiwi + tostadas con crema de cacahuate',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '1 kiwi', 'tag': 'safe'},
                {'t': '2 tostadas de arroz con 1 cdta de crema de cacahuate', 'tag': 'safe'},
            ],
            'swap': 'Fruta: kiwi ↔ plátano firme ↔ papaya.',
        },
        {
            'slot': 'Cena', 'time': '20:30', 'xp': 12, 'tag': 'safe',
            'name': 'Entomatadas de pollo en salsa verde',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '120 g de pollo deshebrado', 'tag': 'safe'},
                {'t': '½ taza de calabacita en cubos', 'tag': 'safe'},
                {'t': 'Salsa verde de tomatillo sin chile', 'tag': 'safe'},
                {'t': '¾ taza de piña', 'tag': 'safe'},
            ],
            'swap': 'Fruta: piña ↔ papaya ↔ mandarina.',
        },
    ],
    'X': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos revueltos con espinacas y calabacita rallada',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 huevos revueltos con espinacas y calabacita rallada', 'tag': 'safe'},
                {'t': '2 cdtas de aceite para cocinar', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '1 taza de papaya', 'tag': 'safe'},
            ],
            'swap': 'Fruta: papaya ↔ kiwi ↔ mandarina ↔ naranja ↔ piña ↔ plátano firme ↔ fresas/moras/blueberries.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Mandarinas + tostadas con crema de cacahuate + pepino',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '2 mandarinas', 'tag': 'safe'},
                {'t': '2 tostadas de arroz con 1 cdta de crema de cacahuate', 'tag': 'safe'},
                {'t': 'Pepino con limón', 'tag': 'safe'},
            ],
            'swap': 'Verdura: pepino ↔ zanahoria ↔ jícama ↔ tomates cherry.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Sopa de verduras con picadillo de res',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '1 taza de sopa de verduras (caldo de pollo con hierbas)', 'tag': 'safe'},
                {'t': '150 g de picadillo de res magro con zanahoria, papa picada y hierbas (sin jitomate, sin cebolla)', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '2 cdtas de aceite infusionado de ajo/cebolla', 'tag': 'safe'},
            ],
            'swap': 'Proteína: res magra ↔ pollo deshebrado.',
        },
        {
            'slot': 'Pre-gym', 'time': '18:00', 'xp': 8, 'tag': 'safe',
            'name': 'Plátano firme + tostadas de arroz',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '1 plátano firme', 'tag': 'caution', 'why': 'Firme (poco maduro) = menos fructanos.'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
            ],
            'swap': 'Fruta: plátano firme ↔ kiwi ↔ papaya chica.',
        },
        {
            'slot': 'Cena', 'time': '20:30', 'xp': 12, 'tag': 'safe',
            'name': 'Toast de queso con espinacas, pechuga y blueberries',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 tostadas horneadas con cama de espinacas', 'tag': 'safe'},
                {'t': '90 g de pechuga a las finas hierbas', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': 'Tomates cherry partidos', 'tag': 'safe'},
                {'t': '¾ taza de blueberries', 'tag': 'safe'},
            ],
            'swap': 'Fruta: blueberries ↔ fresas ↔ moras.',
        },
    ],
    'J': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos revueltos con calabacita y cilantro',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 huevos revueltos con calabacita y cilantro fresco', 'tag': 'safe'},
                {'t': '2 cdtas de aceite para cocinar', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '1 kiwi', 'tag': 'safe'},
            ],
            'swap': 'Fruta: papaya ↔ kiwi ↔ mandarina ↔ naranja ↔ piña ↔ plátano firme ↔ fresas/moras/blueberries.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Mandarina + naranja + tostadas + jícama',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '1 mandarina + 1 naranja', 'tag': 'safe'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': 'Jícama con limón', 'tag': 'safe'},
            ],
            'swap': 'Verdura: pepino ↔ zanahoria ↔ jícama ↔ tomates cherry.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Pollo en salsa verde con nopales y puré de papa',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '½ taza de sopa de pasta con verduras', 'tag': 'safe'},
                {'t': '150 g de pechuga en salsa verde con nopales (2 tazas nopales)', 'tag': 'safe'},
                {'t': '½ taza de puré de papa', 'tag': 'safe'},
            ],
            'swap': 'Proteína: pollo ↔ pescado blanco ↔ res magra ↔ huevo.',
        },
        {
            'slot': 'Pre-gym', 'time': '18:00', 'xp': 8, 'tag': 'safe',
            'name': 'Papaya chica + tostadas con crema de cacahuate',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '1 papaya chica', 'tag': 'safe'},
                {'t': '2 tostadas de arroz con 1 cdta de crema de cacahuate', 'tag': 'safe'},
            ],
            'swap': 'Fruta: papaya ↔ kiwi ↔ plátano firme.',
        },
        {
            'slot': 'Cena', 'time': '20:30', 'xp': 12, 'tag': 'safe',
            'name': 'Tacos de pollo con nopales y naranja',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '120 g de pechuga', 'tag': 'safe'},
                {'t': '2 nopales asados', 'tag': 'safe'},
                {'t': 'Cilantro fresco', 'tag': 'safe'},
                {'t': '1 naranja', 'tag': 'safe'},
            ],
            'swap': 'Fruta: naranja ↔ papaya ↔ kiwi.',
        },
    ],
    'V': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos revueltos con espinacas y ejotes',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 huevos revueltos con espinacas y ejotes picados', 'tag': 'safe'},
                {'t': '2 cdtas de aceite para cocinar', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '1 mandarina', 'tag': 'safe'},
            ],
            'swap': 'Fruta: papaya ↔ kiwi ↔ mandarina ↔ naranja ↔ piña ↔ plátano firme ↔ fresas/moras/blueberries.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Mandarinas + tostadas de arroz + zanahoria',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '2 mandarinas', 'tag': 'safe'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': 'Bastones de zanahoria con limón', 'tag': 'safe'},
            ],
            'swap': 'Verdura: pepino ↔ zanahoria ↔ jícama ↔ tomates cherry.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Albóndigas de res magra en caldo con arroz',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '½ taza de arroz con verduras al gusto', 'tag': 'safe'},
                {'t': '150 g de albóndigas de res magra en caldo de hierbas con calabacita y zanahoria (sin jitomate, sin cebolla)', 'tag': 'safe'},
                {'t': '1 tortilla de maíz', 'tag': 'safe'},
                {'t': '2 cdtas de aceite', 'tag': 'safe'},
            ],
            'swap': 'Proteína: res magra ↔ pollo molido.',
        },
        {
            'slot': 'Pre-gym', 'time': '18:00', 'xp': 8, 'tag': 'safe',
            'name': 'Plátano firme + tostadas con crema de cacahuate',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '1 plátano firme', 'tag': 'caution', 'why': 'Firme (poco maduro) = menos fructanos.'},
                {'t': '2 tostadas de arroz con 1 cdta de crema de cacahuate', 'tag': 'safe'},
            ],
            'swap': 'Fruta: plátano firme ↔ kiwi ↔ papaya chica.',
        },
        {
            'slot': 'Cena', 'time': '20:30', 'xp': 12, 'tag': 'safe',
            'name': 'Tostadas de nopal con pollo deshebrado y naranja',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 tostadas de maíz horneadas', 'tag': 'safe'},
                {'t': '120 g de pollo deshebrado', 'tag': 'safe'},
                {'t': 'Nopales guisados', 'tag': 'safe'},
                {'t': '1 naranja', 'tag': 'safe'},
            ],
            'swap': 'Fruta: naranja ↔ papaya ↔ kiwi.',
        },
    ],
    'S': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos en salsa verde',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 huevos revueltos con calabacita rallada', 'tag': 'safe'},
                {'t': '2 cdtas de aceite para cocinar', 'tag': 'safe'},
                {'t': 'Salsa verde de tomatillo sin chile (bañar encima)', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '1 kiwi', 'tag': 'safe'},
            ],
            'swap': 'Fruta: kiwi ↔ papaya ↔ mandarina.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Papaya + mandarina + tostadas con crema de cacahuate + pepino',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '1 taza de papaya + 1 mandarina', 'tag': 'safe'},
                {'t': '2 tostadas de arroz con 1 cdta de crema de cacahuate', 'tag': 'safe'},
                {'t': 'Pepino con limón', 'tag': 'safe'},
            ],
            'swap': 'Verdura: pepino ↔ jícama ↔ zanahoria.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Sopa de verduras con picadillo',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': 'Sopa de verduras (caldo de pollo con hierbas)', 'tag': 'safe'},
                {'t': '150 g de picadillo con zanahoria, papa y hierbas (sin jitomate, sin cebolla)', 'tag': 'safe'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '2 cdtas de aceite infusionado de ajo/cebolla', 'tag': 'safe'},
            ],
            'swap': 'Proteína: res ↔ pollo deshebrado.',
        },
        {
            'slot': 'Colación 2', 'time': '18:00', 'xp': 8, 'tag': 'safe',
            'name': 'Plátano firme + tostadas + zanahoria',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '1 plátano firme', 'tag': 'caution', 'why': 'Firme (poco maduro) = menos fructanos.'},
                {'t': '2 tostadas de arroz', 'tag': 'safe'},
                {'t': 'Bastones de zanahoria', 'tag': 'safe'},
            ],
            'swap': 'Verdura: zanahoria ↔ pepino ↔ jícama.',
        },
        {
            'slot': 'Cena', 'time': '20:30', 'xp': 12, 'tag': 'safe',
            'name': 'Entomatadas de pollo en salsa verde',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '120 g de pollo deshebrado', 'tag': 'safe'},
                {'t': '½ taza de calabacita en cubos', 'tag': 'safe'},
                {'t': 'Salsa verde de tomatillo sin chile', 'tag': 'safe'},
                {'t': '¾ taza de piña', 'tag': 'safe'},
            ],
            'swap': 'Fruta: piña ↔ papaya ↔ mandarina.',
        },
    ],
    'D': [
        {
            'slot': 'Desayuno', 'time': '07:30', 'xp': 12, 'tag': 'safe',
            'name': 'Huevos divorciados',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 huevos (estilo divorciados)', 'tag': 'safe'},
                {'t': 'Salsa verde de tomatillo SIN chile', 'tag': 'safe'},
                {'t': 'Salsa roja SIN chile', 'tag': 'caution', 'why': 'Jitomate en salsa — apunta si te cae mal.'},
                {'t': '3 tortillas de maíz', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': '2 tazas de verduras al gusto', 'tag': 'safe'},
                {'t': '1 taza de papaya', 'tag': 'safe'},
            ],
            'swap': 'Si el jitomate te cayó mal esta semana, usa solo salsa verde.',
        },
        {
            'slot': 'Colación 1', 'time': '10:30', 'xp': 8, 'tag': 'safe',
            'name': 'Kiwis + tostadas con crema de cacahuate + jícama',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '2 kiwis', 'tag': 'safe'},
                {'t': '2 tostadas de arroz con 1 cdta de crema de cacahuate', 'tag': 'safe'},
                {'t': 'Jícama con limón', 'tag': 'safe'},
            ],
            'swap': 'Fruta: kiwi ↔ mandarina ↔ papaya.',
        },
        {
            'slot': 'Comida', 'time': '13:30', 'xp': 14, 'tag': 'safe',
            'name': 'Tostadas de nopal con pollo deshebrado',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 tostadas de maíz horneadas', 'tag': 'safe'},
                {'t': '150 g de pollo deshebrado', 'tag': 'safe'},
                {'t': 'Nopales guisados con aceite infusionado (ajo/cebolla)', 'tag': 'safe'},
                {'t': 'Salsa verde de tomatillo (opcional)', 'tag': 'safe'},
                {'t': '2 cdtas de aceite', 'tag': 'safe'},
                {'t': '1 naranja', 'tag': 'safe'},
            ],
            'swap': 'Proteína: pollo ↔ pescado blanco ↔ res magra ↔ huevo.',
        },
        {
            'slot': 'Colación 2', 'time': '17:00', 'xp': 8, 'tag': 'safe',
            'name': 'Mandarina + tostadas con crema de cacahuate + pepino',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '1 mandarina', 'tag': 'safe'},
                {'t': '2 tostadas de arroz con 1 cdta de crema de cacahuate', 'tag': 'safe'},
                {'t': 'Pepino con limón', 'tag': 'safe'},
            ],
            'swap': 'Fruta: mandarina ↔ kiwi ↔ fresas. Verdura: pepino ↔ zanahoria ↔ jícama.',
        },
        {
            'slot': 'Cena', 'time': '20:00', 'xp': 12, 'tag': 'safe',
            'name': 'Toast de espinaca con pechuga, queso panela y blueberries',
            'kcal': 0, 'protein': 0, 'note': '',
            'items': [
                {'t': '3 tostadas horneadas con cama de espinacas', 'tag': 'safe'},
                {'t': '90 g de pechuga a las finas hierbas', 'tag': 'safe'},
                {'t': '40 g de queso panela', 'tag': 'safe'},
                {'t': 'Tomates cherry partidos', 'tag': 'safe'},
                {'t': '1 cda de olivas verdes', 'tag': 'safe'},
                {'t': '¾ taza de blueberries', 'tag': 'safe'},
                {'t': '1 cdta de aceite', 'tag': 'safe'},
            ],
            'swap': 'Fruta: blueberries ↔ fresas ↔ moras.',
        },
    ],
}

TEMPTATIONS_MAP = {
    'cafe':    {'label': 'Café de más',       'glyph': 'coffee', 'pen': 5},
    'pan':     {'label': 'Pan / harina',      'glyph': 'wheat',  'pen': 12},
    'galleta': {'label': 'Galleta / dulce',   'glyph': 'cookie', 'pen': 12},
    'lacteo':  {'label': 'Lácteo',            'glyph': 'milk',   'pen': 10},
    'frijol':  {'label': 'Frijol / legumbre', 'glyph': 'bean',   'pen': 8},
    'alcohol': {'label': 'Alcohol',           'glyph': 'wine',   'pen': 12},
    'otro':    {'label': 'Otro disparador',   'glyph': 'flag',   'pen': 8},
}

STOIC_SLIP = [
    'No te castigues; corrige. Mañana es otro asalto.',
    'El desliz registrado ya es virtud: has vuelto a mirar.',
    'No es la caída, sino la prontitud en levantarte.',
    'Ningún hombre es libre si no es dueño de sí mismo.',
    'Recomienza. Cada acto es una vida entera.',
]

# ── Banco de recetas del plan (Sprint 4) ─────────────────────────────────────
# Era la pestaña Recetas de Nutrición (un banco aparte en el JS). Se migra una
# vez a la tabla `recetas` (un solo recetario) con su etiqueta FODMAP y momento;
# migrar_banco() se puede correr las veces que sea sin duplicar (nombre normalizado).
BANCO_FODMAP = [
    # (nombre, momento, kcal, proteína, fodmap, minutos, nota)
    ('Omelette de espinaca y papa',          'desayuno', 390, 26, 'seguro',  12, ''),
    ('Avena sin gluten con fresas',          'desayuno', 340, 12, 'porcion',  8, 'Avena en porción ≤ ½ taza'),
    ('Res magra con arroz y zanahoria',      'comida',   600, 45, 'seguro',  25, ''),
    ('Pescado blanco + quinoa + calabaza',   'comida',   520, 38, 'seguro',  20, ''),
    ('Pavo molido con calabacita',           'cena',     440, 40, 'seguro',  18, ''),
    ('Tortilla de maíz con pollo y limón',   'cena',     410, 34, 'seguro',  15, ''),
    ('Kiwi + puñado de almendras',           'colacion', 200,  7, 'seguro',   2, ''),
    ('Arroz inflado + mantequilla de maní',  'colacion', 240,  9, 'seguro',   3, ''),
    ('Yogur SIN lactosa + semillas chía',    'colacion', 210, 14, 'porcion',  2, 'Solo versión sin lactosa'),
]
_CAT_MOMENTO = {'desayuno': 'Desayuno', 'comida': 'Almuerzo', 'cena': 'Cena', 'colacion': 'Snack', 'pregym': 'Post-Entrenamiento'}


def _norm(s):
    import unicodedata
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in s).split())


def migrar_banco(db):
    """Pasa BANCO_FODMAP a `recetas` sin duplicar por nombre normalizado. Devuelve cuántas insertó."""
    from datetime import datetime
    existentes = {_norm(r['nombre']) for r in db.execute("SELECT nombre FROM recetas").fetchall()}
    n = 0
    for nombre, momento, kcal, prot, fodmap, mins, nota in BANCO_FODMAP:
        if _norm(nombre) in existentes:
            continue
        db.execute("""INSERT INTO recetas (nombre, categoria, descripcion, ingredientes, instrucciones,
                      calorias, proteina, tiempo_prep, porciones, tags, fodmap, momento, created_at)
                      VALUES (?,?,?,?,?,?,?,?,1,'fodmap',?,?,?)""",
                   (nombre, _CAT_MOMENTO[momento], nota, '[]', '[]', kcal, prot, mins, fodmap, momento,
                    datetime.now().isoformat()))
        existentes.add(_norm(nombre))
        n += 1
    return n


# Slot del plan → momento del recetario
def momento_de_slot(slot):
    s = _norm(slot)
    if 'desayuno' in s:
        return 'desayuno'
    if 'colacion' in s:
        return 'colacion'
    if 'gym' in s:
        return 'pregym'
    if 'cena' in s:
        return 'cena'
    return 'comida'


_FODMAP_TAG = {'seguro': 'safe', 'porcion': 'caution', 'evitar': 'trigger'}


def banco(db, slot=None):
    """Recetas para «Agregar comida»: del momento del slot (si se da), seguras primero,
    luego de porción y al final sin etiqueta; nunca las de evitar."""
    rows = db.execute("SELECT * FROM recetas WHERE COALESCE(fodmap,'') != 'evitar'").fetchall()
    m = momento_de_slot(slot) if slot else None
    out = []
    for r in rows:
        momentos = [x.strip() for x in (r['momento'] or '').split(',') if x.strip()]
        if m and momentos and m not in momentos:
            continue
        out.append({'id': r['id'], 'nombre': r['nombre'], 'kcal': r['calorias'] or 0, 'protein': round(r['proteina'] or 0),
                    'fodmap': r['fodmap'], 'tag': _FODMAP_TAG.get(r['fodmap'], 'safe'), 'momento': momentos,
                    'nota': r['descripcion'] or '', 'match': bool(m and m in momentos)})
    orden = {'seguro': 0, 'porcion': 1}
    out.sort(key=lambda x: (not x['match'], orden.get(x['fodmap'], 2), x['nombre'].lower()))
    return out


# ── DB helpers ────────────────────────────────────────────────────────────────

def seed_week(db, week_str):
    for day_key, meals in PLAN_TEMPLATE.items():
        for m in meals:
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


# ── XP por el motor (Sprint 1) ────────────────────────────────────────────────
#
# Cada acción es una fila en activity_logs con su clave y pasa por
# engine.process_activity (cat 'Nutrición'):
#   comida  nutri_comida_<meal_id>     meal.xp
#   síntoma nutri_sintoma_<meal_id>    +5 XP (una vez por comida)
#   día     nutri_dia_<fecha>          +30 XP · +8 EC (una vez por día)
#   desliz  nutri_desliz_<id>          −pen XP
# El motor no acepta montos negativos (process_activity aplica max(1, …)), así
# que la penalización del desliz se escribe con engine._award_xp(−pen,
# 'activity', …, log_id): misma fuente y referencia que el resto, de modo que
# engine.remove_activity(log_id) la revierte igual. El histórico previo en
# xp_ledger con source='nutricion' no se toca (ya está sumado); la marca
# app_settings.nutri_engine_since separa lo viejo de lo nuevo.

_CAT = 'Nutrición'
SINTOMA_XP = 5
DIA_XP, DIA_EC = 30, 8
META_KCAL, META_PROT = 1850, 130


def _log(key, xp, ec=0, ref=None):
    """Inserta la fila en activity_logs y otorga XP/EC vía engine. Devuelve el gam
    (con log_id). Abre su propia conexión: el llamador debe haber hecho commit."""
    import modules.gamification.engine as engine
    today = today_str()
    with get_db() as db:
        log_id = db.execute("INSERT INTO activity_logs (activity_key, date, pts) VALUES (?,?,?)",
                            (key, today, xp)).lastrowid
        db.commit()
    if xp < 0:
        engine._award_xp(xp, 'activity', f'Desliz: {key}', log_id)
        return {'xp': xp, 'ec': 0, 'log_id': log_id}
    gam = engine.process_activity(key, xp, _CAT, log_id, ec=ec)
    gam['log_id'] = log_id
    return gam


def _logged(db, key):
    return db.execute("SELECT id FROM activity_logs WHERE activity_key=?", (key,)).fetchone() is not None


def _unlog(key):
    """Quita la acción (filas de activity_logs + su XP/EC en el ledger)."""
    import modules.gamification.engine as engine
    with get_db() as db:
        ids = [r['id'] for r in db.execute("SELECT id FROM activity_logs WHERE activity_key=?", (key,)).fetchall()]
        db.execute("DELETE FROM activity_logs WHERE activity_key=?", (key,))
        db.commit()
    for i in ids:
        engine.remove_activity(i)
    return bool(ids)


def _since(db):
    row = db.execute("SELECT value FROM app_settings WHERE key='nutri_engine_since'").fetchone()
    return row['value'] if row else None


def get_streak(db):
    """Días consecutivos con nutri_dia_<fecha> y sin desliz, contando desde hoy
    (si ya cerró) o desde ayer. Si la cadena llega hasta antes de
    nutri_engine_since, suma la racha guardada en app_settings.nutricion_streak
    (fallback de lectura durante una versión; ya no se escribe)."""
    hoy = today_date()
    since = _since(db)
    cerrados = {r['activity_key'][len('nutri_dia_'):] for r in db.execute(
        "SELECT activity_key FROM activity_logs WHERE substr(activity_key,1,10)='nutri_dia_'").fetchall()}
    deslices = {r['date'] for r in db.execute("SELECT DISTINCT date FROM nutricion_deslices").fetchall()}
    if hoy.isoformat() in deslices:
        return 0
    d = hoy if hoy.isoformat() in cerrados else hoy - timedelta(days=1)
    n = 0
    while True:
        ds = d.isoformat()
        if since and ds < since:
            row = db.execute("SELECT value FROM app_settings WHERE key='nutricion_streak'").fetchone()
            try:
                n += int(row['value']) if row else 0
            except (TypeError, ValueError):
                pass
            break
        if ds not in cerrados or ds in deslices:
            break
        n += 1
        d -= timedelta(days=1)
    return n


def set_streak(db, val):
    """Obsoleta: la racha se calcula (get_streak). Se conserva por compatibilidad."""
    return None


def _ledger_hoy(db, tabla):
    today = today_str()
    row = db.execute(f"""
        SELECT COALESCE(SUM(amount),0) s FROM {tabla}
        WHERE (source='activity' AND reference_id IN (
                 SELECT id FROM activity_logs WHERE date=? AND substr(activity_key,1,6)='nutri_'))
           OR (source='nutricion' AND date=?)""", (today, today)).fetchone()
    return int(row['s'])


def get_xp_today(db):
    return _ledger_hoy(db, 'xp_ledger')


def get_ec_today(db):
    return _ledger_hoy(db, 'coins_ledger')


def disparadores_30d(db):
    desde = (today_date() - timedelta(days=29)).isoformat()
    return [dict(r) for r in db.execute(
        """SELECT trig_id, MAX(label) AS label, COUNT(*) AS n FROM nutricion_deslices
           WHERE date>=? GROUP BY trig_id ORDER BY n DESC, label""", (desde,)).fetchall()]


def _metas(db):
    def _v(k, d):
        r = db.execute("SELECT value FROM app_settings WHERE key=?", (k,)).fetchone()
        try:
            return int(float(r['value'])) if r else d
        except (TypeError, ValueError):
            return d
    return {'kcal': _v('nutri_meta_kcal', META_KCAL), 'prot': _v('nutri_meta_prot', META_PROT)}


def _semana_tira(db, week_start, week):
    """Estado L–D: cerrado (día limpio), hoy, abierto (pasado sin cerrar), futuro."""
    hoy = today_date()
    since = _since(db)
    out = []
    for i, k in enumerate(['L', 'M', 'X', 'J', 'V', 'S', 'D']):
        d = week_start + timedelta(days=i)
        ds = d.isoformat()
        meals = week.get(k, [])
        cerrado = _logged(db, f'nutri_dia_{ds}') or (
            bool(since and ds < since and meals and all(m['done'] for m in meals)))
        estado = 'cerrado' if cerrado else 'hoy' if d == hoy else 'futuro' if d > hoy else 'abierto'
        out.append({'k': k, 'fecha': ds, 'estado': estado, 'hoy': d == hoy})
    return out


def _cerrar_dia_si_toca(today_key=None):
    """Bono de día limpio (+30 XP, +8 EC) una sola vez: todas las comidas de hoy
    cumplidas y sin desliz. Devuelve el gam o None."""
    today = today_str()
    with get_db() as db:
        meals = db.execute('SELECT done FROM nutricion_semana WHERE week_start=? AND day_key=?',
                           [get_week_start().isoformat(), today_key or get_today_key()]).fetchall()
        slips = db.execute('SELECT COUNT(*) c FROM nutricion_deslices WHERE date=?', [today]).fetchone()['c']
        ya = _logged(db, f'nutri_dia_{today}')
    if meals and all(m['done'] for m in meals) and not slips and not ya:
        return _log(f'nutri_dia_{today}', DIA_XP, ec=DIA_EC)
    return None


# ── Rutas ─────────────────────────────────────────────────────────────────────

def estado(db):
    """Todo lo que pinta /nutricion/: la semana, hoy, el lateral y la tira L–D."""
    week_start = get_week_start()
    week = rows_to_week(get_or_seed_week(db, week_start.isoformat()))
    today = today_str()
    today_key = get_today_key()
    hoy = week.get(today_key, [])
    bristol_row = db.execute(
        'SELECT valor FROM nutricion_bristol WHERE date=? ORDER BY id DESC LIMIT 1', [today]
    ).fetchone()
    hechas = [m for m in hoy if m['done']]
    return {
        'week': week,
        'today': today_key,
        'fecha': today,
        'week_start': week_start.isoformat(),
        'xp_today': get_xp_today(db),
        'ec_today': get_ec_today(db),
        'streak': get_streak(db),
        'slips': [dict(r) for r in db.execute(
            'SELECT * FROM nutricion_deslices WHERE date=? ORDER BY id', [today]).fetchall()],
        'bristol': bristol_row['valor'] if bristol_row else None,
        'dia_cerrado': _logged(db, f'nutri_dia_{today}'),
        'tira': _semana_tira(db, week_start, week),
        'macros': {'kcal': sum(m['kcal'] or 0 for m in hechas), 'prot': sum(m['protein'] or 0 for m in hechas)},
        'metas': _metas(db),
        'disparadores': disparadores_30d(db),
        'recetario': recetario_resumen(db),
        'pendientes': [m for m in hoy if m['done'] and not m['symptom']],
    }


def recetario_resumen(db):
    r = db.execute("SELECT COUNT(*) n, COALESCE(SUM(CASE WHEN fodmap='seguro' THEN 1 ELSE 0 END),0) aptas FROM recetas").fetchone()
    return {'total': r['n'], 'aptas': r['aptas']}


@nutricion_bp.route('/')
def index():
    vista = request.args.get('vista', '')
    with get_db() as db:
        state = estado(db)
        historial = []
        if vista == 'sintomas':
            historial = [dict(r) for r in db.execute(
                """SELECT id, week_start, day_key, slot, time_str, name, done, symptom, sym_tags_json
                   FROM nutricion_semana WHERE done=1 ORDER BY week_start DESC, instr('LMXJVSD', day_key) DESC, time_str DESC LIMIT 120""").fetchall()]
            orden = ['L', 'M', 'X', 'J', 'V', 'S', 'D']
            for h in historial:
                h['sym_tags'] = json.loads(h.pop('sym_tags_json') or '[]')
                h['fecha'] = (date.fromisoformat(h['week_start']) + timedelta(days=orden.index(h['day_key']))).isoformat()
            state['deslices_30d'] = [dict(r) for r in db.execute(
                "SELECT * FROM nutricion_deslices WHERE date>=? ORDER BY date DESC, id DESC",
                [(today_date() - timedelta(days=29)).isoformat()]).fetchall()]
    state['vista'] = vista if vista in ('semana', 'sintomas') else ''
    state['historial'] = historial
    return render_template('nutricion/index.html', state=state, vista=state['vista'])


@nutricion_bp.route('/api/estado')
def api_estado():
    with get_db() as db:
        return jsonify(estado(db))


@nutricion_bp.route('/api/cumplir', methods=['POST'])
def cumplir():
    data = request.get_json()
    meal_id = data['meal_id']

    with get_db() as db:
        meal = db.execute('SELECT * FROM nutricion_semana WHERE id=?', [meal_id]).fetchone()
        if not meal or meal['done']:
            return jsonify({'error': 'not found or already done'}), 400
        db.execute('UPDATE nutricion_semana SET done=1 WHERE id=?', [meal_id])
        db.commit()

    gam = _log(f'nutri_comida_{meal_id}', meal['xp'], ref=meal_id)
    dia = _cerrar_dia_si_toca()

    with get_db() as db:
        st = estado(db)
    return jsonify({
        'xp_earned': gam['xp'],
        'bonus_xp': dia['xp'] if dia else 0,
        'bonus_ec': dia['ec'] if dia else 0,
        'total_xp': st['xp_today'],
        'total_ec': st['ec_today'],
        'streak': st['streak'],
        'all_done': bool(dia) or st['dia_cerrado'],
        'gam': dia or gam,
        'estado': st,
    })


@nutricion_bp.route('/api/descumplir', methods=['POST'])
def descumplir():
    """Deshacer «Cumplí»: quita la comida del motor y, si el día ya estaba
    cerrado, también revierte el bono de día limpio."""
    meal_id = (request.get_json() or {}).get('meal_id')
    with get_db() as db:
        meal = db.execute('SELECT * FROM nutricion_semana WHERE id=?', [meal_id]).fetchone()
        if not meal or not meal['done']:
            return jsonify({'error': 'not found or not done'}), 400
        db.execute('UPDATE nutricion_semana SET done=0 WHERE id=?', [meal_id])
        db.commit()
    _unlog(f'nutri_comida_{meal_id}')
    bono = _unlog(f'nutri_dia_{today_str()}')
    with get_db() as db:
        st = estado(db)
    return jsonify({'ok': True, 'bono_revertido': bono, 'total_xp': st['xp_today'],
                    'total_ec': st['ec_today'], 'streak': st['streak'], 'estado': st})


# «¿Cómo cayó?» de la fila → mismos ids que el diario de síntomas
_FEEL_IDS = {'bien': 'bien', 'pesado': 'regular', 'regular': 'regular', 'molestia': 'mal', 'mal': 'mal'}


@nutricion_bp.route('/api/sintoma', methods=['POST'])
def sintoma():
    data = request.get_json()
    meal_id = data['meal_id']
    feeling = _FEEL_IDS.get(str(data['feeling']).lower(), data['feeling'])
    tags = data.get('tags', [])

    with get_db() as db:
        db.execute(
            'UPDATE nutricion_semana SET symptom=?, sym_tags_json=? WHERE id=?',
            [feeling, json.dumps(tags), meal_id]
        )
        ya = _logged(db, f'nutri_sintoma_{meal_id}')
        db.commit()
    gam = None if ya else _log(f'nutri_sintoma_{meal_id}', SINTOMA_XP, ref=meal_id)
    with get_db() as db:
        return jsonify({'xp_earned': gam['xp'] if gam else 0, 'total_xp': get_xp_today(db),
                        'feeling': feeling, 'gam': gam})


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
        slip_id = db.execute(
            'INSERT INTO nutricion_deslices(date,trig_id,label,glyph,pen,over,note) VALUES(?,?,?,?,?,?,?)',
            [today, trig_id, trig['label'], trig['glyph'], pen, 1 if over else 0, note]
        ).lastrowid
        db.commit()
    _log(f'nutri_desliz_{slip_id}', -pen, ref=slip_id)
    with get_db() as db:
        st = estado(db)
    return jsonify({
        'pen': pen,
        'msg': random.choice(STOIC_SLIP),
        'total_xp': st['xp_today'],
        'streak': st['streak'],
        'estado': st,
        'slip': {
            'id': slip_id,
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


@nutricion_bp.route('/api/banco')
def api_banco():
    with get_db() as db:
        return jsonify(banco(db, request.args.get('slot')))


_SLOT_TIME = {'Desayuno': '07:00', 'Colación AM': '10:30', 'Comida': '14:00', 'Colación PM': '17:30', 'Pre-gym': '18:00', 'Cena': '20:30'}


@nutricion_bp.route('/api/comida', methods=['POST'])
def add_comida():
    data = request.get_json()
    week_str = get_week_start().isoformat()
    day_key = data.get('day') or get_today_key()
    slot = data['slot']
    xp = 8 if 'Colación' in slot else 12

    with get_db() as db:
        if data.get('receta_id'):
            # Del recetario único: nombre, macros, etiqueta e ingredientes salen de `recetas`
            r = db.execute("SELECT * FROM recetas WHERE id=?", (data['receta_id'],)).fetchone()
            if not r:
                return jsonify({'error': 'receta no encontrada'}), 404
            try:
                ings = json.loads(r['ingredientes'] or '[]')
            except ValueError:
                ings = []
            tag = _FODMAP_TAG.get(r['fodmap'], 'safe')
            items = [{'t': (i.get('item') if isinstance(i, dict) else str(i)), 'tag': tag} for i in ings] or [{'t': r['nombre'], 'tag': tag}]
            data = dict(data, name=r['nombre'], kcal=r['calorias'] or 0, protein=round(r['proteina'] or 0), tag=tag,
                        note=r['descripcion'] or 'Del recetario.', items=items,
                        time=data.get('time') or _SLOT_TIME.get(slot, '12:00'))
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
