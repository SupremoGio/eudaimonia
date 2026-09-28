"""
Correcciones de «Sin clasificar» (2026-09-28): el usuario bajó OTROS con el
botón CSV del detalle de categoría y le puso un comentario a cada fila.
Cada una se identifica por id + fecha + monto; si el id no coincide (otra
base), por fecha + monto + comercio siempre que siga en OTROS. Comentario ->
categoría:
  «boleto avion» -> VIAJES/Transporte
  «café pan» -> CAFE/PAN/Pan
  «casa articulos hogar» -> VIVIENDA/Artículos del hogar
  «decoracion casa» -> VIVIENDA/Artículos del hogar
  «entretenimiento» -> OCIO/Salidas
  «estacionamiento» -> TRANSPORTE/Estacionamiento
  «expense» -> EXPENSE
  «farmacia» -> SALUD/Farmacia
  «fast food» -> COMIDA_FUERA/Fast Food
  «gasolina» -> TRANSPORTE/Gasolina
  «gym a meses sin intereses» -> DEPORTE/Gym
  «lavanderia» -> VIVIENDA/Lavandería
  «meses sin intereses comedor» -> VIVIENDA/Artículos del hogar
  «pan» -> CAFE/PAN/Pan
  «pizza» -> COMIDA_FUERA/Delivery
  «restaurante» -> COMIDA_FUERA/Restaurante
  «ropa» -> ROPA/Ropa
  «ropa a meses» -> ROPA/Ropa
  «ropa deportiva» -> ROPA/Ropa deportiva
  «salsa» -> SALSA/Social
  «salsa evento» -> SALSA/Social
  «salsa social» -> SALSA/Social
  «seguro carro BBVA a meses» -> TRANSPORTE/Seguro auto
  «super» -> SUPER/Súper
  «tecnologia» -> TECH/DIGITAL/Accesorios
  «viaje hotel» -> VIAJES/Hospedaje
  «educacion» -> APRENDIZAJE/Libros (Larousse) o APRENDIZAJE/Cursos (Superprof)
Las mensualidades a meses (Training, Sodimac, Men's Factory, Privalia, autoseguro)
toman la categoría del comentario: su compra inicial ya está fuera del gasto.
"""

# (id, fecha, monto, comercio, categoria, subcategoria)  # comentario
CORRECCIONES = [
    (4936, '2023-07-23', 1910.15, 'CERVECERIA CHAPULTEPEC', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4120, '2022-08-20', 1785.0, 'DESPEGAR', 'VIAJES', 'Transporte'),  # boleto avion
    (4195, '2023-01-01', 1782.94, 'CE CDMX AEROPUERTO', 'VIAJES', 'Hospedaje'),  # viaje hotel
    (4169, '2022-12-17', 1599.0, '3582 PULL BEAR LA P ZAPOPA', 'ROPA', 'Ropa'),  # ropa
    (4136, '2022-10-12', 1497.0, '6517 P B VIA VALLEJO', 'ROPA', 'Ropa'),  # ropa
    (4796, '2022-11-07', 1348.19, 'SEGBBVA AUTOSEGURO ROP', 'TRANSPORTE', 'Seguro auto'),  # seguro carro BBVA a meses
    (4219, '2023-01-08', 1327.9, 'AME PUMA MEXICO', 'ROPA', 'Ropa deportiva'),  # ropa deportiva
    (4893, '2023-04-29', 1288.0, 'LA MATA TINTA', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4218, '2023-01-08', 1104.51, 'CALVIN KLEIN', 'ROPA', 'Ropa'),  # ropa
    (4335, '2023-06-23', 952.6, 'LAS HIJAS DE LA TOSTAD', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4440, '2022-09-22', 949.0, 'SEGBBVA AUTOSEGURO VO', 'TRANSPORTE', 'Seguro auto'),  # seguro carro BBVA a meses
    (4118, '2022-08-22', 949.0, 'SEGBBVA AUTOSEGURO VO', 'TRANSPORTE', 'Seguro auto'),  # seguro carro BBVA a meses
    (4110, '2022-07-22', 949.0, 'SEGBBVA AUTOSEGURO VO', 'TRANSPORTE', 'Seguro auto'),  # seguro carro BBVA a meses
    (4102, '2022-06-22', 949.0, 'SEGBBVA AUTOSEGURO VO', 'TRANSPORTE', 'Seguro auto'),  # seguro carro BBVA a meses
    (4143, '2022-10-22', 942.31, 'SEGBBVA AUTOSEGURO VO', 'TRANSPORTE', 'Seguro auto'),  # seguro carro BBVA a meses
    (4106, '2022-07-03', 849.0, 'PLAZA PATRIA GUADALAJA', 'ROPA', 'Ropa'),  # ropa
    (4167, '2022-12-15', 819.16, 'ALDO CONTI PZA PTRIA', 'ROPA', 'Ropa'),  # ropa
    (5094, '2024-01-22', 700.0, 'SODIMAC', 'VIVIENDA', 'Artículos del hogar'),  # meses sin intereses comedor
    (5084, '2023-12-22', 700.0, 'SODIMAC', 'VIVIENDA', 'Artículos del hogar'),  # meses sin intereses comedor
    (5147, '2023-11-22', 700.0, 'SODIMAC', 'VIVIENDA', 'Artículos del hogar'),  # meses sin intereses comedor
    (4861, '2023-04-06', 700.0, 'GAS FLORENCIA 1000', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4820, '2023-03-11', 700.0, 'SERV RAYO', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4809, '2023-02-25', 700.0, 'SERV LOPEZ MATEOS', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4228, '2023-01-23', 700.0, 'RED NAC COMB SERV', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4142, '2022-10-17', 700.0, 'SERV LOPEZ MATEOS', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4431, '2022-09-03', 700.0, 'RED NAC COMB SERV', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4117, '2022-08-20', 700.0, 'SERV FERPETRO', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (5117, '2024-04-22', 697.0, 'SODIMAC', 'VIVIENDA', 'Artículos del hogar'),  # meses sin intereses comedor
    (4196, '2023-01-02', 567.0, 'ONE MINUTE PARK', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4605, '2024-06-12', 559.0, 'FARMASAL COUNTRY', 'SALUD', 'Farmacia'),  # farmacia
    (4213, '2022-12-29', 550.0, 'AEROMEX WEB MX', 'VIAJES', 'Transporte'),  # boleto avion
    (4375, '2024-04-30', 544.0, 'CLIPMX PACHANGUITOS', 'EXPENSE', ''),  # expense
    (4850, '2023-03-24', 525.0, 'CLIP MX ITEC', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4135, '2022-10-11', 500.25, 'VICENTA VALLEJO', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4776, '2022-11-06', 500.0, 'MARISCOS EL DORADO', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (5080, '2023-12-08', 495.0, 'CONJUNTO SANTANDER WEB', 'OCIO', 'Salidas'),  # entretenimiento
    (5011, '2023-08-25', 472.0, 'H LIVE PATRIA', 'SALSA', 'Social'),  # salsa evento
    (4897, '2023-04-30', 470.0, 'ZTL JOELGONZALEZROCHA', 'SALSA', 'Social'),  # salsa evento
    (4876, '2023-04-22', 462.0, 'MEN S FACTORY P PAT I', 'ROPA', 'Ropa'),  # ropa a meses
    (4833, '2023-03-22', 462.0, 'MEN S FACTORY P PAT I', 'ROPA', 'Ropa'),  # ropa a meses
    (4271, '2023-02-22', 462.0, 'MEN S FACTORY P PAT I', 'ROPA', 'Ropa'),  # ropa a meses
    (4211, '2023-01-22', 462.0, 'MEN S FACTORY P PAT I', 'ROPA', 'Ropa'),  # ropa a meses
    (4175, '2022-12-22', 462.0, 'MEN S FACTORY P PAT I', 'ROPA', 'Ropa'),  # ropa a meses
    (4925, '2023-05-22', 458.01, 'MEN S FACTORY P PAT I', 'ROPA', 'Ropa'),  # ropa a meses
    (5043, '2023-09-11', 400.0, 'KINZA GAS', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4350, '2023-07-09', 400.0, 'KINZA GAS', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4340, '2023-07-01', 400.0, 'KINZA GAS', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4302, '2023-06-03', 400.0, 'KINZA GAS', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (5104, '2024-04-20', 399.0, '5092 PULL BEAR GAL GDL', 'ROPA', 'Ropa'),  # ropa
    (4590, '2024-05-31', 384.0, 'DOMIN SENDERO DELIVERY', 'COMIDA_FUERA', 'Delivery'),  # pizza
    (4132, '2022-10-11', 370.0, 'CLIP MX SITIO', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4280, '2023-02-22', 361.0, 'PRIVALIA 55 36877115', 'ROPA', 'Ropa'),  # ropa a meses
    (4225, '2023-01-22', 361.0, 'PRIVALIA 55 36877115', 'ROPA', 'Ropa'),  # ropa a meses
    (4843, '2023-03-22', 359.67, 'PRIVALIA 55 36877115', 'ROPA', 'Ropa'),  # ropa a meses
    (5138, '2023-11-22', 359.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (5067, '2023-09-22', 359.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4994, '2023-08-22', 359.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4361, '2023-07-22', 359.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4328, '2023-06-22', 359.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4926, '2023-05-22', 359.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4877, '2023-04-22', 359.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4226, '2023-02-22', 358.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4179, '2023-01-22', 358.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4207, '2023-01-15', 358.0, 'CLIP MX COMIDA CORRIDA', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4151, '2022-12-22', 358.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4766, '2022-11-22', 358.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4122, '2022-10-22', 358.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4430, '2022-09-22', 358.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4113, '2022-08-22', 358.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4105, '2022-07-22', 358.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4101, '2022-06-22', 358.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4804, '2023-03-22', 352.0, 'TRAINING INNOVATION', 'DEPORTE', 'Gym'),  # gym a meses sin intereses
    (4156, '2022-12-03', 348.0, 'EDICIONES LAROUSSE I', 'APRENDIZAJE', 'Libros'),  # educacion
    (4109, '2022-07-17', 330.0, 'DECATHLON GDL ACUEDUCT', 'ROPA', 'Ropa deportiva'),  # ropa deportiva
    (4337, '2023-06-24', 329.0, 'SUBBIA VILLAMOSA PATIO', 'ROPA', 'Ropa'),  # ropa
    (4308, '2023-06-09', 325.6, 'MERPAGO ROMA', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (5041, '2023-09-10', 320.0, 'ITAMAE SUSHI', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4432, '2022-09-04', 320.0, 'BAR ROCK IT', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4130, '2022-10-11', 313.0, 'IHOP VIA VALLEJO', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4599, '2024-06-05', 310.0, 'MERPAGO FUNDAMENTAL', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4810, '2023-02-25', 302.5, 'MACARENA BRUNCH', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4140, '2022-10-15', 302.0, 'MERPAGO ELVERA', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4573, '2024-05-25', 300.0, 'FEDERALISMO CENTRO', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4376, '2024-05-01', 300.0, 'SERV NUEVO MEXICO', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (5062, '2023-09-17', 300.0, 'KINZA GAS', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (5025, '2023-09-01', 300.0, 'EST SERV GALERIAS', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (5014, '2023-08-26', 300.0, 'KINZA GAS', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4964, '2023-08-06', 300.0, 'KINZA GAS', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4959, '2023-08-04', 300.0, 'GAS MEX FEDERALISMO', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4958, '2023-07-31', 300.0, 'GASOJAL III', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4139, '2022-10-14', 300.0, 'POINTMP TRANSPORTACI', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4857, '2023-04-01', 299.0, 'C A ZAPOPAN', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4168, '2022-12-17', 297.0, 'CLIP MX EL REY DE LAS', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4502, '2025-12-23', 295.0, 'BPK MISC ALTA PROTGAMA', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4906, '2023-05-13', 289.3, 'MEMBRILLO', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4825, '2023-03-13', 278.0, 'CLIP MX BLACK MOON COF', 'SALSA', 'Social'),  # salsa social
    (4355, '2023-07-15', 267.3, 'BP LA MADRIGUERA2', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4385, '2024-05-05', 261.0, 'YORK PUB CHAPULTEPEC', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4184, '2022-12-27', 253.0, 'CMX ZAPOPAN', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4816, '2023-03-05', 250.0, 'ZTL JUANCARLOSBERRUTTI', 'SALSA', 'Social'),  # salsa social
    (4588, '2024-05-30', 249.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4336, '2023-06-23', 245.0, 'QUESOS Y MAS', 'SUPER', 'Súper'),  # super
    (4965, '2023-08-07', 231.0, 'THE BONE HOUSE', 'SALSA', 'Social'),  # salsa social
    (4114, '2022-07-24', 229.0, 'MOBO PLAZA PATRIA 2', 'TECH/DIGITAL', 'Accesorios'),  # tecnologia
    (4319, '2023-06-17', 225.0, 'MICHELADAS LOS CUATES', 'COMIDA_FUERA', 'Fast Food'),  # fast food
    (4141, '2022-10-17', 224.0, 'QIN PLAZA PATRIA', 'COMIDA_FUERA', 'Fast Food'),  # fast food
    (4980, '2023-08-09', 218.0, 'OLA KREPE', 'COMIDA_FUERA', 'Fast Food'),  # fast food
    (4630, '2022-08-15', 218.0, 'QIN ANDARES', 'COMIDA_FUERA', 'Fast Food'),  # fast food
    (4318, '2023-06-16', 216.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4868, '2023-04-14', 205.0, 'MERPAGO MARIOALEJANDR', 'SALSA', 'Social'),  # salsa social
    (5151, '2026-04-25', 200.0, 'RECORCHOLIS LPG', 'OCIO', 'Salidas'),  # entretenimiento
    (4384, '2024-05-05', 200.0, 'YORK PUB CHAPULTEPEC', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (5034, '2023-09-06', 200.0, 'GAS COLON', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4971, '2023-08-12', 200.0, 'GASOJAL III', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4968, '2023-08-10', 200.0, 'SERV ZAPOPAN', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4293, '2023-05-28', 200.0, 'SERV PATRYBACH', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4907, '2023-05-13', 200.0, 'RED NAC COMB SERV', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4888, '2023-04-26', 200.0, 'ESTACION DE SERV COL', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4795, '2022-11-07', 200.0, 'SEGBBVA AUTOSEGURO ROP', 'TRANSPORTE', 'Seguro auto'),  # seguro carro BBVA a meses
    (4312, '2023-06-11', 199.0, 'T14 GALS GDL', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4835, '2023-02-23', 199.0, 'SUPERPROF PASSELEVE', 'APRENDIZAJE', 'Cursos'),  # educacion
    (4274, '2023-01-24', 199.0, 'SUPERPROF PASS ELEVE', 'APRENDIZAJE', 'Cursos'),  # educacion
    (4129, '2022-10-10', 192.0, 'MERCADO LA FLOR DE COR', 'VIVIENDA', 'Artículos del hogar'),  # decoracion casa
    (4983, '2023-08-17', 190.0, 'CLIP MX POLACOS HOT DO', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4749, '2022-11-17', 190.0, 'AQUI ES PEJAMO', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4437, '2022-09-15', 174.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4790, '2022-11-18', 172.87, 'SAMS CLUB PATRIA', 'COMIDA_FUERA', 'Fast Food'),  # fast food
    (4242, '2023-01-29', 166.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4887, '2023-04-24', 160.0, 'BAR ROCK IT', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4078, '2022-08-01', 153.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4324, '2023-06-20', 138.0, 'DONA TOTA FORUM COATZA', 'CAFE/PAN', 'Pan'),  # pan
    (4701, '2022-10-13', 134.0, 'H&M MX0006 VALLEJO', 'ROPA', 'Ropa'),  # ropa
    (5044, '2023-09-11', 129.0, 'CARNICERIA FLORENCIA B', 'SUPER', 'Súper'),  # super
    (4848, '2023-03-23', 128.0, 'ZTL JOSEFRANCISCOCASTI', 'SALSA', 'Social'),  # salsa
    (4970, '2023-08-12', 126.5, 'LOS VOLTEADOS ZAPOPAN', 'COMIDA_FUERA', 'Fast Food'),  # fast food
    (4170, '2022-12-17', 126.0, 'ZTL JUANCARLOSBERRUTTI', 'SALSA', 'Social'),  # salsa
    (5033, '2023-09-06', 121.0, 'EL CHIRINGUITO DE GDL', 'EXPENSE', ''),  # expense
    (4895, '2023-04-29', 120.0, 'KIDZANIA GDL', 'OCIO', 'Salidas'),  # entretenimiento
    (4188, '2022-12-29', 120.0, 'CERRAJERIA GUTIERREZ', 'VIVIENDA', 'Artículos del hogar'),  # casa articulos hogar
    (5027, '2023-09-02', 118.0, 'ZTL LUISALBERTOMEZARAM', 'SALSA', 'Social'),  # salsa
    (4867, '2023-04-14', 118.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (5037, '2023-09-08', 110.0, 'MC DONALDS VALLARTA', 'COMIDA_FUERA', 'Fast Food'),  # fast food
    (4349, '2023-07-09', 110.0, 'DISTRITO WOK', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4775, '2022-11-05', 110.0, 'FURTER DOGOS', 'COMIDA_FUERA', 'Fast Food'),  # fast food
    (4824, '2023-03-12', 105.0, 'CERVECERIA CHAPULTEPEC', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4051, '2022-07-11', 105.0, 'MERPAGO*CAMACHOS', 'COMIDA_FUERA', 'Restaurante'),  # restaurante
    (4206, '2023-01-14', 103.05, 'CARNICERIAS PTO BELLO', 'SUPER', 'Súper'),  # super
    (4373, '2024-04-29', 101.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (5150, '2026-04-25', 100.0, 'RECORCHOLIS LPG', 'OCIO', 'Salidas'),  # entretenimiento
    (4358, '2023-07-20', 100.0, 'RED NAC COMB SERV', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4251, '2023-02-07', 100.0, 'ESTACION DE SERV COL', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4786, '2022-11-12', 100.0, 'ESTACION DE SERV COL', 'TRANSPORTE', 'Gasolina'),  # gasolina
    (4321, '2023-06-18', 99.0, 'MADALENA CITY CENTER', 'SALSA', 'Social'),  # salsa
    (4675, '2022-09-21', 96.0, 'EL GLOBO AEROPUERTO 4', 'CAFE/PAN', 'Pan'),  # pan
    (4828, '2023-03-17', 90.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4872, '2023-04-20', 84.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4166, '2022-12-14', 84.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4587, '2024-05-30', 83.0, 'AQUAMATIC PABLO NERUDA', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4978, '2023-08-13', 82.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4811, '2023-02-26', 82.0, 'LAVANDERIA AQUAMATIC P', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4152, '2022-11-26', 80.0, 'QUEEN LATIN CLUB', 'SALSA', 'Social'),  # salsa social
    (4955, '2023-07-30', 73.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4873, '2023-04-20', 71.0, 'LAVANDERIA AQUAMATIC P', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (5057, '2023-09-16', 70.0, 'AQUAMATIC PABLO NERUDA (2)', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (5056, '2023-09-16', 70.0, 'AQUAMATIC PABLO NERUDA', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (5031, '2023-09-03', 70.0, 'AQUAMATIC PABLO NERUDA (2)', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (5030, '2023-09-03', 70.0, 'AQUAMATIC PABLO NERUDA', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4966, '2023-08-09', 70.0, 'AQUAMATIC PABLO NERUDA', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4962, '2023-08-05', 70.0, 'AQUAMATIC PABLO NERUDA (2)', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4961, '2023-08-05', 70.0, 'AQUAMATIC PABLO NERUDA', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4307, '2023-06-04', 70.0, 'AQUAMATIC PABLO NERUDA', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4862, '2023-04-06', 70.0, 'LAVANDERIA AQUAMATIC P', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4826, '2023-03-15', 70.0, 'LAVANDERIA AQUAMATIC P', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4259, '2023-02-11', 70.0, 'LAVANDERIA AQUAMATIC P', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4231, '2023-01-25', 70.0, 'LAVANDERIA AQUAMATIC P', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4205, '2023-01-14', 70.0, 'LAVANDERIA AQUAMATIC P', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4187, '2022-12-29', 66.0, 'LAVANDERIA AQUAMATIC P', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4171, '2022-12-18', 66.0, 'LAVANDERIA AQUAMATIC P', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4342, '2023-07-02', 64.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4186, '2022-12-29', 64.0, 'LAVANDERIA AQUAMATIC P', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (5032, '2023-09-03', 60.0, 'QUEEN LATIN CLUB', 'SALSA', 'Social'),  # salsa social
    (4817, '2023-03-05', 60.0, 'QUEEN LATIN CLUB', 'SALSA', 'Social'),  # salsa social
    (4711, '2022-10-19', 60.0, 'QUEEN LATIN CLUB', 'SALSA', 'Social'),  # salsa social
    (5015, '2023-08-27', 48.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4944, '2023-07-24', 48.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4294, '2023-05-28', 48.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4347, '2023-07-08', 42.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4589, '2024-05-30', 41.0, 'AQUAMATIC PABLO NERUDA', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (5063, '2023-09-17', 40.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4986, '2023-08-19', 40.0, 'TRE BLE', 'CAFE/PAN', 'Pan'),  # café pan
    (4903, '2023-05-07', 40.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4898, '2023-04-30', 40.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4815, '2023-03-04', 40.0, 'QUEEN LATIN CLUB', 'SALSA', 'Social'),  # salsa social
    (4709, '2022-10-17', 40.0, 'LAVANDERIA AQUAMATIC P', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4258, '2023-02-11', 35.0, 'LAVANDERIA AQUAMATIC P', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (4204, '2023-01-14', 35.0, 'LAVANDERIA AQUAMATIC P', 'VIVIENDA', 'Lavandería'),  # lavanderia
    (5012, '2023-08-26', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4988, '2023-08-19', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4979, '2023-08-13', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4973, '2023-08-12', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4967, '2023-08-09', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4960, '2023-08-05', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4940, '2023-07-23', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4357, '2023-07-18', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4356, '2023-07-15', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4345, '2023-07-08', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4341, '2023-07-01', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4303, '2023-06-03', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4292, '2023-05-27', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4920, '2023-05-20', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4908, '2023-05-14', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4900, '2023-05-06', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4899, '2023-05-01', 15.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
    (4953, '2023-07-30', 10.0, 'ESTACIONAM AMER MIL500', 'TRANSPORTE', 'Estacionamiento'),  # estacionamiento
]


def aplicar(db) -> tuple[int, int]:
    """(actualizadas, no encontradas). Idempotente."""
    ok = faltan = 0
    for mid, fecha, monto, comercio, cat, sub in CORRECCIONES:
        row = db.execute("""SELECT id, categoria, subcategoria FROM est_movimientos
                            WHERE id=? AND substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01""",
                         (mid, fecha, monto)).fetchone()
        if not row:
            row = db.execute("""SELECT id, categoria, subcategoria FROM est_movimientos
                                WHERE substr(fecha,1,10)=? AND ABS(ABS(monto) - ?) < 0.01
                                  AND UPPER(descripcion) LIKE ? AND categoria='OTROS'
                                ORDER BY id LIMIT 1""",
                             (fecha, monto, f"%{comercio.split(' (')[0][:18].upper()}%")).fetchone()
        if not row:
            faltan += 1
            continue
        if (row['categoria'], row['subcategoria'] or '') != (cat, sub):
            db.execute("UPDATE est_movimientos SET categoria=?, subcategoria=? WHERE id=?", (cat, sub, row['id']))
            ok += 1
    return ok, faltan
