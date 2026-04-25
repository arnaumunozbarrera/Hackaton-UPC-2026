# Component Prediction Models

Este documento explica como se predice el estado de cada componente, por que se
usa esa logica y como se convierte la simulacion historica en una prediccion de
fallo.

## Idea General

Hay dos capas distintas de prediccion:

1. **Prediccion fisica de estado**, en `model_mathematic`.
   Cada componente recibe su estado anterior, los drivers actuales y la
   configuracion. Devuelve el siguiente `health`, `status`, `damage`, `metrics`
   y `alerts`.
2. **Prediccion temporal de fallo**, en `backend/app/prediction/predictor.py`.
   Usa el historial guardado por la simulacion para extrapolar cuando un
   componente llegara a zona de fallo si la tendencia actual continua.

La Phase 1 no usa machine learning. Es un modelo fisico-reglado,
determinista y explicable. Esto tiene sentido porque el brief no proporciona
telemetria real: no hay datos suficientes para entrenar un modelo fiable. En
cambio, se usan formulas calibradas con `target_cycles_until_failure`,
umbrales de salud y sensibilidades por driver.

## Drivers

Los modelos trabajan con estos drivers:

```text
L = operational_load
C = contamination
U = humidity
T = temperature_stress
M = maintenance_level
```

Interpretacion:

- `operational_load`: uso/ciclos/capas procesadas en el paso actual.
- `contamination`: suciedad, polvo degradado, residuos o particulas no
  deseadas.
- `humidity`: humedad ambiental o humedad efectiva sobre polvo/componentes.
- `temperature_stress`: desviacion termica normalizada entre 0 y 1.
- `maintenance_level`: calidad de mantenimiento preventivo, entre 0 y 1.

La simulacion de Phase 2 puede variar estos drivers en el tiempo. Phase 1 solo
predice el siguiente estado a partir de los drivers que recibe.

## Salida Comun

Cada componente devuelve:

```text
health: valor normalizado entre 0.0 y 1.0
status: FUNCTIONAL, DEGRADED, CRITICAL o FAILED
damage: desglose del dano producido
metrics: variables fisicas propias del componente
alerts: avisos derivados de metricas o estado
```

El estado se decide por umbrales:

```text
if health <= failed_threshold:   FAILED
elif health <= critical_threshold: CRITICAL
elif health <= degraded_threshold: DEGRADED
else: FUNCTIONAL
```

## Prediccion Temporal De Fallo

La prediccion temporal del backend se calcula despues de ejecutar una
simulacion. El predictor lee la serie historica de un componente y estima la
pendiente media de perdida de salud:

```text
delta_usage = last_usage - first_usage
delta_health = first_health - last_health
slope = delta_health / delta_usage
```

Si no hay al menos dos puntos, si no avanza el uso o si la salud no cae, el
predictor responde que no hay datos suficientes.

Si hay tendencia valida:

```text
usages_until_failure = (current_health - 0.15) / slope
predicted_failure_usage = current_usage + usages_until_failure
predicted_failure_timestamp = last_timestamp + usages_until_failure minutes
```

El umbral `0.15` es conservador: avisa antes del umbral duro de `FAILED`
configurado normalmente en `0.10`. Por eso esta prediccion debe entenderse como
una prediccion preventiva de fallo/riesgo, no como el instante exacto en el que
el status interno cambiara a `FAILED`.

La confianza se calcula de forma transparente:

```text
confidence = 0.45
             + min(delta_usage / 96, 0.30)
             + min(delta_health * 0.8, 0.17)
```

Despues se limita entre `0.20` y `0.92`.

Justificacion:

- Es simple y facil de defender.
- Esta basado solo en la telemetria generada por el propio digital twin.
- Evita inventar conocimiento externo.
- Es suficiente para una demo de mantenimiento predictivo.

Limitacion:

- Es una extrapolacion lineal de tendencia historica. Si un componente tiene
  degradacion acelerada, como el motor con Weibull, una mejora futura seria
  usar la pendiente de los ultimos puntos o proyectar el propio modelo fisico.

## Formula Base 1: Dano Lineal Acumulativo

Usada en componentes donde el dano por ciclo es aproximadamente proporcional al
uso:

```text
base_damage = (H_initial - H_fail) / target_cycles_until_failure

D = base_damage
    * L^alpha
    * product(1 + sensitivity_i * driver_i)
    * (1 - maintenance_protection * M)

H_next = clamp(H_previous - D)
```

Se usa para cuchilla, guia lineal, limpieza, sensores e insulation panels.

## Formula Base 2: Decaimiento Exponencial

Usada en componentes electricos/termicos:

```text
lambda = -ln(H_fail / H_initial) / target_cycles_until_failure

effective_load = L^alpha
                 * product(1 + sensitivity_i * driver_i)
                 * cascade_factors
                 * (1 - maintenance_protection * M)

D = H_previous * (1 - exp(-lambda * effective_load))
H_next = H_previous * exp(-lambda * effective_load)
```

Se usa para heating elements y thermal firing resistors.

## Formula Base 3: Weibull

Usada en el motor del recoater:

```text
effective_age_next =
    effective_age_previous
    + L^alpha
    * guide_drag_factor
    * contamination_factor
    * humidity_factor
    * temperature_factor
    * maintenance_factor

eta = target_cycles_until_failure / (-ln(H_fail / H_initial))^(1 / beta)

H_next = H_initial * exp(-(effective_age_next / eta)^beta)
```

Con `beta = 2.2`, el riesgo de fallo aumenta con la edad acumulada. Esto es
coherente con fatiga mecanica, rodamientos, vibracion y desgaste progresivo.

## Prediccion Por Componente

### 1. Recoater Blade

Archivo: `model_mathematic/recoater_blade.py`

Subsistema: `recoating_system`

Modelo: dano lineal acumulativo por desgaste abrasivo.

Formula:

```text
D = base_damage
    * L^load_exponent
    * (1 + s_contamination * C)
    * (1 + s_humidity * U)
    * (1 - maintenance_protection * M)
```

Por que se predice asi:

- La cuchilla reparte polvo metalico capa tras capa.
- El contacto repetido produce desgaste abrasivo.
- La contaminacion aumenta particulas duras o irregulares.
- La humedad apelmaza el polvo y empeora el contacto.
- El mantenimiento reduce dano futuro por limpieza, ajuste o sustitucion
  parcial de elementos de contacto.

Metricas predichas:

```text
thickness_mm = max(min_thickness, initial_thickness * health)
roughness_index = (1 - health) * max_roughness
wear_rate = damage / operational_load
```

Que significa:

- Menos `thickness_mm` implica cuchilla mas gastada.
- Mas `roughness_index` implica peor uniformidad de capa.
- Si se degrada mucho, acelera la contaminacion efectiva de la `nozzle_plate`.

### 2. Linear Guide

Archivo: `model_mathematic/linear_guide.py`

Subsistema: `recoating_system`

Modelo: dano lineal acumulativo por friccion, contaminacion y humedad.

Formula:

```text
D = base_damage
    * L^load_exponent
    * (1 + s_contamination * C)
    * (1 + s_humidity * U)
    * (1 - maintenance_protection * M)
```

Por que se predice asi:

- La guia soporta movimiento repetido del recoater.
- La suciedad aumenta friccion y rayado.
- La humedad puede provocar corrosion o peor lubricacion.
- La degradacion aparece como perdida de alineacion y aumento de arrastre.

Metricas predichas:

```text
friction_coefficient = nominal_friction + max_friction_increase * degradation
straightness_error_mm = max_straightness_error * degradation
carriage_drag_factor = 1 + max_drag_increase * degradation
alignment_score = 1 - degradation
```

Relacion con otros componentes:

- `linear_guide -> recoater_drive_motor`
- Una guia degradada aumenta `guide_drag_factor` y hace que el motor envejezca
  mas rapido.

### 3. Recoater Drive Motor

Archivo: `model_mathematic/recoater_drive_motor.py`

Subsistema: `recoating_system`

Modelo: Weibull para fatiga mecanica con edad efectiva acumulada.

Formula:

```text
guide_drag_factor = 1 + s_guide * (1 - H_linear_guide)

effective_age_delta =
    L^load_exponent
    * guide_drag_factor
    * (1 + s_contamination * C)
    * (1 + s_humidity * U)
    * (1 + s_temperature * T)
    * (1 - maintenance_protection * M)

effective_age_next = effective_age_previous + effective_age_delta

H_next = H_initial * exp(-(effective_age_next / eta)^beta)
```

Por que se predice asi:

- Un motor no suele fallar de forma lineal perfecta.
- En motores, rodamientos y bobinados, el riesgo de fallo aumenta con la edad y
  la fatiga acumulada.
- Weibull con `beta > 1` representa exactamente ese comportamiento: poco dano al
  principio y dano acelerado despues.
- El arrastre de una guia degradada no quita salud directamente; aumenta la
  edad efectiva del motor.

Metricas predichas:

```text
torque_margin baja con degradation y guide_degradation
current_draw_factor sube con degradation y guide_degradation
vibration_index sube con degradation y guide_degradation
winding_temperature_rise_c sube con degradation y temperature_stress
effective_age_cycles acumula edad equivalente
weibull_cumulative_hazard mide riesgo acumulado
```

Que aporta Weibull:

- Hace el modelo mas realista para fatiga mecanica.
- Permite justificar un modelo estandar adicional del brief.
- Genera una curva donde el motor parece estable al inicio y se vuelve mas
  vulnerable conforme envejece.

### 4. Nozzle Plate

Archivo: `model_mathematic/nozzle_plate.py`

Subsistema: `printhead_array`

Modelo: dano mixto por `clogging` y `thermal_fatigue`.

Formula:

```text
effective_contamination =
    C
    + recoater_cascade * (1 - H_recoater_blade)
    + cleaning_cascade * (1 - H_cleaning_interface)

effective_temperature_stress =
    T
    + heating_cascade * (1 - H_heating_elements)
    + firing_resistor_cascade * (1 - H_thermal_firing_resistors)

clogging_damage =
    base_damage
    * weight_clogging
    * (1 + s_contamination * effective_contamination)
    * (1 + s_humidity * U)

thermal_fatigue_damage =
    base_damage
    * weight_thermal
    * (1 + s_temperature * effective_temperature_stress)

D = (clogging_damage + thermal_fatigue_damage)
    * (1 - maintenance_protection * M)
```

Por que se predice asi:

- La placa de boquillas puede fallar por obturacion o por fatiga termica.
- En binder jetting, el clogging es critico porque afecta directamente a la
  eyeccion del binder.
- La temperatura afecta a viscosidad, disparo y fatiga de la zona del
  printhead.
- La limpieza, el recoater y los elementos termicos influyen en la boquilla, por
  eso recibe cascadas de otros componentes.

Metricas predichas:

```text
clogging_ratio += clogging_damage
thermal_fatigue_index += thermal_fatigue_damage
blocked_nozzles_pct = max_blocked_nozzles_pct * clogging_ratio
jetting_efficiency = health * (1 - clogging_penalty * clogging_ratio)
```

Relaciones:

- `recoater_blade -> nozzle_plate`
- `cleaning_interface -> nozzle_plate`
- `heating_elements -> nozzle_plate`
- `thermal_firing_resistors -> nozzle_plate`

### 5. Thermal Firing Resistors

Archivo: `model_mathematic/thermal_firing_resistors.py`

Subsistema: `printhead_array`

Modelo: decaimiento exponencial por fatiga electrica y termica.

Formula:

```text
effective_temperature_stress =
    T + heating_cascade * (1 - H_heating_elements)

effective_load =
    L^load_exponent
    * (1 + s_temperature * effective_temperature_stress)
    * (1 + s_humidity * U)
    * (1 + s_contamination * C)
    * (1 - maintenance_protection * M)

D = H_previous * (1 - exp(-lambda * effective_load))
```

Por que se predice asi:

- Los resistores de disparo sufren pulsos termicos repetidos.
- El calor y la contaminacion alteran resistencia y uniformidad de pulso.
- Si `heating_elements` esta degradado, el entorno termico del printhead es
  menos estable.

Metricas predichas:

```text
resistance_ohm sube con degradation
firing_energy_factor sube con degradation
pulse_uniformity baja con degradation
misfire_risk sube con degradation y thermal stress
```

Relacion:

- `heating_elements -> thermal_firing_resistors`
- `thermal_firing_resistors -> nozzle_plate`

### 6. Cleaning Interface

Archivo: `model_mathematic/cleaning_interface.py`

Subsistema: `printhead_array`

Modelo: dano lineal acumulativo por desgaste del limpiador y acumulacion de
residuo.

Formula:

```text
D = base_damage
    * L^load_exponent
    * (1 + s_contamination * C)
    * (1 + s_humidity * U)
    * (1 - maintenance_protection * M)
```

Por que se predice asi:

- El wiper o interfaz de limpieza se degrada por contacto repetido.
- La contaminacion aumenta residuos.
- La humedad puede cambiar adherencia o acumulacion de material.
- Una limpieza peor deja mas residuo en boquillas.

Metricas predichas:

```text
cleaning_efficiency baja con degradation
residue_buildup sube con degradation y contamination
wiper_wear_ratio sube con degradation
wipe_pressure_factor baja con degradation
```

Relacion:

- `cleaning_interface -> nozzle_plate`

### 7. Heating Elements

Archivo: `model_mathematic/heating_elements.py`

Subsistema: `thermal_control`

Modelo: decaimiento exponencial por degradacion electrica.

Formula:

```text
effective_temperature_stress =
    T + temperature_sensor_cascade * (1 - H_temperature_sensors)

insulation_heat_loss_factor =
    1 + insulation_cascade * (1 - H_insulation_panels)

effective_load =
    L^load_exponent
    * (1 + s_temperature * effective_temperature_stress)
    * (1 + s_humidity * U)
    * (1 - maintenance_protection * M)
    * insulation_heat_loss_factor

D = H_previous * (1 - exp(-lambda * effective_load))
```

Por que se predice asi:

- Los elementos calefactores son componentes resistivos.
- A medida que envejecen, aumentan resistencia y energia necesaria.
- Si los sensores miden peor, el control termico es menos preciso.
- Si el aislamiento pierde eficiencia, los calefactores deben trabajar mas.

Metricas predichas:

```text
resistance_ohm sube con degradation
energy_factor sube con degradation
thermal_stability baja con health y temperature_stress
temperature_control_error_c sube con degradation y temperature_stress
```

Relaciones:

- `temperature_sensors -> heating_elements`
- `insulation_panels -> heating_elements`
- `heating_elements -> thermal_firing_resistors`
- `heating_elements -> nozzle_plate`

### 8. Temperature Sensors

Archivo: `model_mathematic/temperature_sensors.py`

Subsistema: `thermal_control`

Modelo: dano lineal acumulativo por drift, humedad y ciclos termicos.

Formula:

```text
D = base_damage
    * L^load_exponent
    * (1 + s_temperature * T)
    * (1 + s_humidity * U)
    * (1 - maintenance_protection * M)
```

Por que se predice asi:

- Los sensores pueden perder calibracion con ciclos termicos.
- La humedad puede aumentar ruido o deteriorar contactos.
- La degradacion aparece como drift, respuesta lenta y menor confianza de
  calibracion.

Metricas predichas:

```text
drift_c sube con degradation y temperature_stress
response_time_ms sube con degradation
signal_noise_index sube con degradation y humidity
calibration_confidence baja con degradation
```

Relacion:

- `temperature_sensors -> heating_elements`

### 9. Insulation Panels

Archivo: `model_mathematic/insulation_panels.py`

Subsistema: `thermal_control`

Modelo: dano lineal acumulativo por ciclos termicos, humedad y contaminacion.

Formula:

```text
D = base_damage
    * L^load_exponent
    * (1 + s_temperature * T)
    * (1 + s_humidity * U)
    * (1 + s_contamination * C)
    * (1 - maintenance_protection * M)
```

Por que se predice asi:

- El aislamiento pierde eficiencia con ciclos termicos.
- La humedad puede degradar materiales aislantes.
- La contaminacion puede ensuciar superficies y alterar transferencia termica.
- Si el aislamiento falla, se pierde mas calor y los calefactores trabajan mas.

Metricas predichas:

```text
insulation_efficiency baja con degradation
heat_loss_factor sube con degradation
panel_integrity baja con degradation
thermal_gradient_c sube con degradation y temperature_stress
```

Relacion:

- `insulation_panels -> heating_elements`

## Como Explicarlo En La Demo

Frase corta:

> La prediccion no intenta adivinar magicamente el futuro. En cada paso toma el
> estado anterior, aplica drivers ambientales y operacionales, calcula dano con
> formulas fisicas explicables y guarda el resultado. Despues, el predictor
> estima el tiempo hasta fallo extrapolando la tendencia de salud registrada.

Puntos fuertes:

- Todos los componentes usan drivers reales del brief.
- Cada formula tiene una razon fisica.
- Las cascadas conectan subsistemas.
- El motor incluye Weibull para fatiga mecanica con riesgo creciente.
- La prediccion de fallo incluye evidencia: ultimo timestamp, usage, health y
  status usados para extrapolar.

## Limitaciones Declarables

- No se usan datos reales de HP; la calibracion es sintetica.
- El predictor temporal usa tendencia lineal historica para ser simple y
  explicable.
- Phase 1 es determinista; la variabilidad entra en Phase 2 modificando drivers
  con una semilla reproducible.
- El mantenimiento reduce dano futuro, pero no recupera salud perdida salvo que
  se modele una accion de mantenimiento adicional en Phase 2.

