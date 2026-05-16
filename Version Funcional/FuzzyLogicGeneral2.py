# ============================================================
# fuzzyLogicGeneral.py
# Librería General de Lógica Difusa
# Compatible con MicroPython (Raspberry Pi Pico W) y Python 3
#
# Autor: Adaptado para uso educativo en Control Inteligente
# Descripción: Librería genérica para construir controladores
#              difusos de tipo Mamdani con defuzzificación
#              por centroide. Aplicable a cualquier sistema.
# ============================================================

# MicroPython no tiene functools, se define reduce manualmente 
try:
    from functools import reduce
except ImportError:
    def reduce(f, lst):
        result = lst[0]
        for item in lst[1:]:
            result = f(result, item)
        return result

# Resolución de la discretización para el cálculo del centroide
# Mayor precisión = cálculo más lento pero más exacto
# Recomendado: 20 para Pico W, 100 para PC
PRECISION = 20


# ============================================================
# FUNCIÓN AUXILIAR: Ecuación de línea entre dos puntos
# Retorna [pendiente m, intercepto b] de y = mx + b
# ============================================================
def lineEquation(p1, p2):
    """
    Calcula la ecuación de la recta entre dos puntos.
    p1, p2: [x, y]
    Retorna: [m, b] donde y = m*x + b
    """
    m = (p2[1] - p1[1]) / (p2[0] - p1[0])
    b = p1[1] - m * p1[0]
    return [m, b]


# ============================================================
# CLASE BASE: Funciones de Membresía
# ============================================================
class MembershipFunctions:
    """
    Clase base que implementa las funciones de membresía
    más comunes en lógica difusa:
      - trimf  : triangular
      - tramfL : trapezoidal izquierda (abierta a la izquierda)
      - tramfR : trapezoidal derecha  (abierta a la derecha)
    
    Cada función tiene versión de ENTRADA (_i) y SALIDA (_o).
    Las entradas reciben un valor x y retornan su grado [0,1].
    Las salidas generan la curva discreta para el centroide.
    """

    # ----------------------------------------------------------
    # FUNCIONES DE ENTRADA (fuzzificación)
    # ----------------------------------------------------------

    def trimf_i(self, points, eqVals, x):
        """
        Función triangular de entrada.
        points: [a, b, c]  → a=inicio, b=pico, c=fin
        eqVals: [[m0,b0],[m1,b1]] ecuaciones de los lados
        x: valor a evaluar
        Retorna: grado de membresía en [0, 1]
        """
        a, b, c = points
        if x >= a and x < b:
            return eqVals[0][1] + x * eqVals[0][0]
        elif x >= b and x <= c:
            return eqVals[1][1] + x * eqVals[1][0]
        else:
            return 0

    def tramfL_i(self, points, eqVal, x):
        """
        Trapezoidal abierta a la IZQUIERDA (para conjuntos 'MUY NEGATIVO').
        points: [a, b, c]  → a=donde empieza la bajada, b=donde llega a 0, c=límite derecho
        Retorna: 1 si x <= a, rampa descendente entre a y b, 0 si x > b
        """
        a, b, c = points
        if x >= a and x <= b:
            return eqVal[1] + x * eqVal[0]
        elif x >= points[0] - (b - a) and x < a:  # zona plana izquierda
            return 1
        else:
            return 0

    def tramfR_i(self, points, eqVal, x):
        """
        Trapezoidal abierta a la DERECHA (para conjuntos 'MUY POSITIVO').
        points: [a, b, c]  → a=inicio, b=donde sube a 1, c=límite derecho
        Retorna: rampa ascendente entre a y b, 1 si x >= b
        """
        a, b, c = points
        if x >= a and x <= b:
            return eqVal[1] + x * eqVal[0]
        elif x > b and x <= c:
            return 1
        else:
            return 0

    # ----------------------------------------------------------
    # FUNCIONES DE SALIDA (para defuzzificación)
    # Generan lista discreta de la curva truncada
    # ----------------------------------------------------------

    def trimf_o(self, points, eqVals, x_start, x_end):
        """
        Genera la curva triangular discreta para la salida.
        x_start, x_end: rango del universo de salida
        Retorna: lista con los valores de membresía discretizados
        """
        step = (x_end - x_start) / PRECISION
        a, b, c = points
        graph = []
        x = x_start
        while x <= x_end:
            if x >= a and x < b:
                graph.append(eqVals[0][1] + x * eqVals[0][0])
            elif x >= b and x <= c:
                graph.append(eqVals[1][1] + x * eqVals[1][0])
            else:
                graph.append(0)
            x += step
        return graph

    def tramfL_o(self, points, eqVal, x_start, x_end):
        """
        Genera la curva trapezoidal izquierda discreta para la salida.
        """
        step = (x_end - x_start) / PRECISION
        a, b, _ = points
        graph = []
        x = x_start
        while x <= x_end:
            if x >= a and x <= b:
                graph.append(eqVal[1] + x * eqVal[0])
            elif x < a:
                graph.append(1)
            else:
                graph.append(0)
            x += step
        return graph

    def tramfR_o(self, points, eqVal, x_start, x_end):
        """
        Genera la curva trapezoidal derecha discreta para la salida.
        """
        step = (x_end - x_start) / PRECISION
        a, b, _ = points
        graph = []
        x = x_start
        while x <= x_end:
            if x >= a and x <= b:
                graph.append(eqVal[1] + x * eqVal[0])
            elif x > b:
                graph.append(1)
            else:
                graph.append(0)
            x += step
        return graph


# ============================================================
# CLASE: Conjunto Difuso
# Encapsula un conjunto (ej: "temperatura ALTA")
# ============================================================
class FuzzySet:
    """
    Representa un conjunto difuso individual.
    
    Parámetros:
      name   : nombre del conjunto (ej: "ALTA", "MEDIA")
      shape  : tipo de función → 'tri', 'trapL', 'trapR'
      points : [a, b, c] puntos clave de la función
    
    Ejemplo:
      temp_alta = FuzzySet("ALTA", "trapR", [25, 35, 50])
    """

    SHAPES = ['tri', 'trapL', 'trapR']

    def __init__(self, name, shape, points):
        assert shape in self.SHAPES, f"Forma '{shape}' no válida. Usa: {self.SHAPES}"
        assert len(points) == 3, "Se requieren exactamente 3 puntos [a, b, c]"
        self.name = name
        self.shape = shape
        self.points = points
        self.mf = MembershipFunctions()

        # Pre-calcular ecuaciones de recta
        a, b, c = points
        if shape == 'tri':
            self.eqVals = [
                lineEquation([a, 0], [b, 1]),
                lineEquation([b, 1], [c, 0])
            ]
        elif shape == 'trapL':
            self.eqVals = lineEquation([a, 1], [b, 0])
        elif shape == 'trapR':
            self.eqVals = lineEquation([a, 0], [b, 1])

    def evaluate(self, x):
        """Evalúa el grado de membresía para el valor x."""
        if self.shape == 'tri':
            return self.mf.trimf_i(self.points, self.eqVals, x)
        elif self.shape == 'trapL':
            return self.mf.tramfL_i(self.points, self.eqVals, x)
        elif self.shape == 'trapR':
            return self.mf.tramfR_i(self.points, self.eqVals, x)

    def output_curve(self, x_start, x_end):
        """Genera la curva discreta para defuzzificación."""
        if self.shape == 'tri':
            return self.mf.trimf_o(self.points, self.eqVals, x_start, x_end)
        elif self.shape == 'trapL':
            return self.mf.tramfL_o(self.points, self.eqVals, x_start, x_end)
        elif self.shape == 'trapR':
            return self.mf.tramfR_o(self.points, self.eqVals, x_start, x_end)


# ============================================================
# CLASE: Variable Difusa
# Agrupa varios conjuntos difusos para una variable
# ============================================================
class FuzzyVariable:
    """
    Representa una variable lingüística (ej: temperatura, velocidad).
    Contiene múltiples conjuntos difusos.
    
    Ejemplo:
      temperatura = FuzzyVariable("Temperatura", 0, 100)
      temperatura.add_set(FuzzySet("FRIA",  "trapL", [0,  10, 20]))
      temperatura.add_set(FuzzySet("MEDIA", "tri",   [15, 25, 35]))
      temperatura.add_set(FuzzySet("ALTA",  "trapR", [30, 40, 50]))
    """

    def __init__(self, name, min_val, max_val):
        self.name = name
        self.min_val = min_val
        self.max_val = max_val
        self.sets = {}   # dict: nombre → FuzzySet

    def add_set(self, fuzzy_set):
        """Agrega un conjunto difuso a la variable."""
        self.sets[fuzzy_set.name] = fuzzy_set

    def fuzzify(self, x):
        """
        Fuzzifica el valor x.
        Retorna: dict {nombre_conjunto: grado_membresía}
        """
        return {name: fs.evaluate(x) for name, fs in self.sets.items()}

    def output_curves(self):
        """
        Genera todas las curvas discretas de salida.
        Retorna: dict {nombre_conjunto: lista_curva}
        """
        return {
            name: fs.output_curve(self.min_val, self.max_val)
            for name, fs in self.sets.items()
        }


# ============================================================
# FUNCIÓN: Defuzzificación por Centroide
# ============================================================
def centroid(rules_outputs, x_start, x_end):
    """
    Calcula el centroide (centro de gravedad) del área resultante.
    
    rules_outputs : lista de listas (curva discreta por cada regla activada)
    x_start       : inicio del universo de salida
    x_end         : fin del universo de salida
    
    Retorna: valor numérico defuzzificado
    """
    n = len(rules_outputs[0])
    step = (x_end - x_start) / PRECISION

    # Agregar por máximo (operador OR entre reglas)
    total = [
        reduce(lambda a, b: max(a, b), [rules_outputs[i][j] for i in range(len(rules_outputs))])
        for j in range(n)
    ]

    num = sum(total[k] * (x_start + step * k) for k in range(n))
    den = sum(total)

    if den == 0:
        return (x_start + x_end) / 2  # valor neutro si no hay activación
    return num / den


# ============================================================
# CLASE: Controlador Difuso General (Mamdani)
# ============================================================
class FuzzyController:
    """
    Controlador difuso genérico tipo Mamdani.
    
    Uso básico:
      1. Crear variables de entrada y salida con FuzzyVariable
      2. Agregar conjuntos difusos con add_set()
      3. Crear el controlador y agregar variables
      4. Definir reglas como lista de tuplas
      5. Llamar a compute() con los valores de entrada
    
    Ejemplo mínimo (temperatura → velocidad_ventilador):
    
      temp = FuzzyVariable("Temperatura", 0, 50)
      temp.add_set(FuzzySet("BAJA",  "trapL", [0,  15, 25]))
      temp.add_set(FuzzySet("MEDIA", "tri",   [20, 30, 40]))
      temp.add_set(FuzzySet("ALTA",  "trapR", [35, 45, 50]))
    
      fan = FuzzyVariable("Ventilador", 0, 100)
      fan.add_set(FuzzySet("LENTO",  "trapL", [0,  20, 40]))
      fan.add_set(FuzzySet("MEDIO",  "tri",   [30, 50, 70]))
      fan.add_set(FuzzySet("RAPIDO", "trapR", [60, 80, 100]))
    
      ctrl = FuzzyController()
      ctrl.add_input("temp", temp)
      ctrl.add_output("fan", fan)
    
      reglas = [
          ({"temp": "BAJA"},  {"fan": "LENTO"}),
          ({"temp": "MEDIA"}, {"fan": "MEDIO"}),
          ({"temp": "ALTA"},  {"fan": "RAPIDO"}),
      ]
      ctrl.add_rules(reglas)
    
      resultado = ctrl.compute({"temp": 38})
      print(resultado["fan"])  # ej: 82.3
    """

    def __init__(self):
        self.inputs = {}   # nombre → FuzzyVariable
        self.outputs = {}  # nombre → FuzzyVariable
        self.rules = []    # lista de (antecedente_dict, consecuente_dict)

    def add_input(self, name, variable):
        """Agrega una variable de entrada."""
        self.inputs[name] = variable

    def add_output(self, name, variable):
        """Agrega una variable de salida."""
        self.outputs[name] = variable

    def add_rules(self, rules):
        """
        Agrega reglas difusas.
        rules: lista de tuplas (antecedente, consecuente)
          antecedente : dict {nombre_var_entrada: nombre_conjunto}
          consecuente : dict {nombre_var_salida: nombre_conjunto}
        
        Para reglas con AND entre varias entradas, se usa el mínimo.
        """
        self.rules = rules

    def compute(self, input_values, operator='min'):
        """
        Ejecuta el controlador difuso.
        
        input_values : dict {nombre_variable: valor_numérico}
        operator     : 'min' (AND) o 'prod' para el antecedente
        
        Retorna: dict {nombre_variable_salida: valor_defuzzificado}
        """
        # 1. Fuzzificar todas las entradas
        memberships = {}
        for var_name, value in input_values.items():
            memberships[var_name] = self.inputs[var_name].fuzzify(value)

        # 2. Pre-generar curvas de salida
        output_curves = {}
        for out_name, out_var in self.outputs.items():
            output_curves[out_name] = out_var.output_curves()

        # 3. Evaluar reglas y acumular consecuentes
        activated = {out_name: [] for out_name in self.outputs}

        for antecedent, consequent in self.rules:
            # Calcular fuerza del antecedente (AND = mínimo)
            strengths = []
            for var_name, set_name in antecedent.items():
                strengths.append(memberships[var_name].get(set_name, 0))

            if operator == 'min':
                firing = min(strengths) if strengths else 0
            else:  # producto
                firing = 1
                for s in strengths:
                    firing *= s

            if firing == 0:
                continue

            # Truncar curvas de salida con la fuerza de activación
            for out_name, set_name in consequent.items():
                curve = output_curves[out_name].get(set_name, [])
                truncated = [min(firing, v) for v in curve]
                activated[out_name].append(truncated)

        # 4. Defuzzificar por centroide
        result = {}
        for out_name, curves in activated.items():
            out_var = self.outputs[out_name]
            if not curves:
                result[out_name] = (out_var.min_val + out_var.max_val) / 2
            else:
                result[out_name] = centroid(curves, out_var.min_val, out_var.max_val)

        return result


# ============================================================
# EJEMPLOS LISTOS PARA USAR
# ============================================================

def ejemplo_temperatura_humedad():
    """
    Control difuso para temperatura y humedad.
    Entradas : temperatura (°C), humedad (%)
    Salida   : potencia del sistema de climatización (0-100%)
    """
    # --- Variable: Temperatura ---
    temp = FuzzyVariable("Temperatura", 0, 50)
    temp.add_set(FuzzySet("FRIA",    "trapL", [0,  10, 20]))
    temp.add_set(FuzzySet("FRESCA",  "tri",   [15, 20, 27]))
    temp.add_set(FuzzySet("COMODA",  "tri",   [22, 26, 30]))
    temp.add_set(FuzzySet("CALIDA",  "tri",   [27, 32, 38]))
    temp.add_set(FuzzySet("CALIENTE","trapR", [35, 42, 50]))

    # --- Variable: Humedad ---
    hum = FuzzyVariable("Humedad", 0, 100)
    hum.add_set(FuzzySet("SECA",    "trapL", [0,  20, 35]))
    hum.add_set(FuzzySet("NORMAL",  "tri",   [30, 50, 70]))
    hum.add_set(FuzzySet("HUMEDA",  "trapR", [65, 80, 100]))

    # --- Variable de Salida: Potencia del climatizador ---
    clima = FuzzyVariable("Climatizador", 0, 100)
    clima.add_set(FuzzySet("APAGADO",   "trapL", [0,  5,  15]))
    clima.add_set(FuzzySet("BAJO",      "tri",   [10, 25, 40]))
    clima.add_set(FuzzySet("MEDIO",     "tri",   [35, 50, 65]))
    clima.add_set(FuzzySet("ALTO",      "tri",   [60, 75, 90]))
    clima.add_set(FuzzySet("MAX",       "trapR", [85, 95, 100]))

    # --- Controlador ---
    ctrl = FuzzyController()
    ctrl.add_input("temp", temp)
    ctrl.add_input("hum", hum)
    ctrl.add_output("clima", clima)

    # --- Reglas ---
    reglas = [
        # Temperatura fría
        ({"temp": "FRIA",     "hum": "SECA"},    {"clima": "APAGADO"}),
        ({"temp": "FRIA",     "hum": "NORMAL"},  {"clima": "APAGADO"}),
        ({"temp": "FRIA",     "hum": "HUMEDA"},  {"clima": "BAJO"}),
        # Temperatura fresca
        ({"temp": "FRESCA",   "hum": "SECA"},    {"clima": "APAGADO"}),
        ({"temp": "FRESCA",   "hum": "NORMAL"},  {"clima": "BAJO"}),
        ({"temp": "FRESCA",   "hum": "HUMEDA"},  {"clima": "MEDIO"}),
        # Temperatura cómoda
        ({"temp": "COMODA",   "hum": "SECA"},    {"clima": "BAJO"}),
        ({"temp": "COMODA",   "hum": "NORMAL"},  {"clima": "MEDIO"}),
        ({"temp": "COMODA",   "hum": "HUMEDA"},  {"clima": "MEDIO"}),
        # Temperatura cálida
        ({"temp": "CALIDA",   "hum": "SECA"},    {"clima": "MEDIO"}),
        ({"temp": "CALIDA",   "hum": "NORMAL"},  {"clima": "ALTO"}),
        ({"temp": "CALIDA",   "hum": "HUMEDA"},  {"clima": "ALTO"}),
        # Temperatura caliente
        ({"temp": "CALIENTE", "hum": "SECA"},    {"clima": "ALTO"}),
        ({"temp": "CALIENTE", "hum": "NORMAL"},  {"clima": "MAX"}),
        ({"temp": "CALIENTE", "hum": "HUMEDA"},  {"clima": "MAX"}),
    ]
    ctrl.add_rules(reglas)
    return ctrl

def proyecto_minigranja_porcina():
    """
    Control difuso para el control de temperatura dentro de las cunas
    de una minigranja porcina.
    Entrada 1: Temperatura DS18X20
    Entrada 2: Edad
    
    Salida 1: Potencia Foco
    
    """
    
    # --- Variable: Edad ---
    edad = FuzzyVariable("Edad", 0, 27)
    edad.add_set(FuzzySet("CERO",    "trapL", [0,  7, 13]))
    edad.add_set(FuzzySet("SIET",  "tri",   [7, 13, 21]))
    edad.add_set(FuzzySet("VU",    "trapR",   [20, 21, 27]))


    # --- Variable: TemperaturaCuna ---
    tempcuna = FuzzyVariable("TemperaturaCuna", 0, 60)
    tempcuna.add_set(FuzzySet("MB",    "trapL", [0,  22, 23]))
    tempcuna.add_set(FuzzySet("ENGR",    "tri", [23,  26, 28]))
    tempcuna.add_set(FuzzySet("SIETE",  "tri",   [25, 27, 30]))
    tempcuna.add_set(FuzzySet("LRN",  "tri", [30, 31, 33]))
    tempcuna.add_set(FuzzySet("MA",    "trapR", [33,  34, 60]))
    
    # --- Variable: TemperaturaAmbiente ---
    tempamb = FuzzyVariable("TemperaturaAmbiente", -10, 60)#-- ojo con el negativo!!!
    tempamb.add_set(FuzzySet("MBTA", "trapL", [-10, 14, 15]))
    tempamb.add_set(FuzzySet("TAD", "tri", [14, 17, 20]))
    tempamb.add_set(FuzzySet("MATA", "trapR", [20, 21, 60]))
    

    # --- Variable de Salida: Intensidad Foco ---
    foco = FuzzyVariable("Intensidad Foco", 0, 100)
    foco.add_set(FuzzySet("APAGADOF",   "trapL", [0,  5,  15]))
    foco.add_set(FuzzySet("BAJOF",      "tri",   [10, 25, 40]))
    foco.add_set(FuzzySet("MEDIOF",     "tri",   [35, 50, 65]))
    foco.add_set(FuzzySet("ALTOF",      "tri",   [60, 75, 90]))
    foco.add_set(FuzzySet("MAXF",       "trapR", [85, 95, 100]))
    
    # --- Variable de Salida: Ventilador ---
    vent = FuzzyVariable("Ventilador", 0, 100)
    vent.add_set(FuzzySet("APAGADOV",   "trapL", [0,  5,  15]))
    vent.add_set(FuzzySet("BAJOV",      "tri",   [10, 25, 40]))
    vent.add_set(FuzzySet("MEDIOV",     "tri",   [35, 50, 65]))
    vent.add_set(FuzzySet("ALTOV",      "tri",   [60, 75, 90]))
    vent.add_set(FuzzySet("MAXV",       "trapR", [85, 95, 100]))

    # --- Controlador ---
    ctrl = FuzzyController()
    ctrl.add_input("edad", edad)
    ctrl.add_input("tempcuna", tempcuna)
    ctrl.add_input("tempamb", tempamb)
    ctrl.add_output("foco", foco)
    ctrl.add_output("vent", vent)

    # --- Reglas ---
    reglas = [
        # Edad: CERO ------------------------------------------------------------------------------------------------
        
        
        ({"edad": "CERO",     "tempcuna": "MB",     "tempamb": "MBTA" },    {"foco": "MAXF"   ,"vent": "APAGADOV"}),
        ({"edad": "CERO",     "tempcuna": "MB",     "tempamb": "TAD" },    {"foco": "MAXF"   ,"vent": "APAGADOV"}),
        ({"edad": "CERO",     "tempcuna": "MB",     "tempamb": "MATA" },    {"foco": "MAXF"   ,"vent": "MAXV"}),
        
        
        ({"edad": "CERO",     "tempcuna": "ENGR",     "tempamb": "MBTA" },    {"foco": "MAXF"   ,"vent": "APAGADOV"}),
        ({"edad": "CERO",     "tempcuna": "ENGR",     "tempamb": "TAD" },    {"foco": "MAXF"   ,"vent": "APAGADOV"}),
        ({"edad": "CERO",     "tempcuna": "ENGR",     "tempamb": "MATA" },    {"foco": "MAXF"   ,"vent": "MAXV"}),
        
        
        ({"edad": "CERO",     "tempcuna": "SIETE",     "tempamb": "MBTA" },    {"foco": "MAXF"   ,"vent": "APAGADOV"}),
        ({"edad": "CERO",     "tempcuna": "SIETE",     "tempamb": "TAD" },    {"foco": "MAXF"   ,"vent": "APAGADOV"}),
        ({"edad": "CERO",     "tempcuna": "SIETE",     "tempamb": "MATA" },    {"foco": "MAXF"   ,"vent": "MAXV"}),
        
        
        ({"edad": "CERO",     "tempcuna": "LRN",     "tempamb": "MBTA" },    {"foco": "BAJOF"   ,"vent": "APAGADOV"}),
        ({"edad": "CERO",     "tempcuna": "LRN",     "tempamb": "TAD" },    {"foco": "BAJOF"   ,"vent": "APAGADOV"}),
        ({"edad": "CERO",     "tempcuna": "LRN",     "tempamb": "MATA" },    {"foco": "BAJOF"   ,"vent": "MAXV"}),
        
        
        ({"edad": "CERO",     "tempcuna": "MA",     "tempamb": "MBTA" },    {"foco": "APAGADOF"   ,"vent": "APAGADOV"}),
        ({"edad": "CERO",     "tempcuna": "MA",     "tempamb": "TAD" },    {"foco": "APAGADOF"   ,"vent": "APAGADOV"}),
        ({"edad": "CERO",     "tempcuna": "MA",     "tempamb": "MATA" },    {"foco": "APAGADOF"   ,"vent": "MAXV"}),
        
        
        # Edad: SIET -----------------------------------------------------------------------------------------------
        
        
        ({"edad": "SIET",     "tempcuna": "MB",     "tempamb": "MBTA" },    {"foco": "MAXF"   ,"vent": "APAGADOV"}),
        ({"edad": "SIET",     "tempcuna": "MB",     "tempamb": "TAD" },    {"foco": "MAXF"   ,"vent": "APAGADOV"}),
        ({"edad": "SIET",     "tempcuna": "MB",     "tempamb": "MATA" },    {"foco": "MAXF"   ,"vent": "MAXV"}),
        
        
        ({"edad": "SIET",     "tempcuna": "ENGR",     "tempamb": "MBTA" },    {"foco": "ALTOF"   ,"vent": "APAGADOV"}),
        ({"edad": "SIET",     "tempcuna": "ENGR",     "tempamb": "TAD" },    {"foco": "ALTOF"   ,"vent": "APAGADOV"}),
        ({"edad": "SIET",     "tempcuna": "ENGR",     "tempamb": "MATA" },    {"foco": "ALTOF"   ,"vent": "MAXV"}),
        
        
        ({"edad": "SIET",     "tempcuna": "SIETE",     "tempamb": "MBTA" },    {"foco": "BAJOF"   ,"vent": "APAGADOV"}),
        ({"edad": "SIET",     "tempcuna": "SIETE",     "tempamb": "TAD" },    {"foco": "BAJOF"   ,"vent": "APAGADOV"}),
        ({"edad": "SIET",     "tempcuna": "SIETE",     "tempamb": "MATA" },    {"foco": "BAJOF"   ,"vent": "MAXV"}),
        
        
        ({"edad": "SIET",     "tempcuna": "LRN",     "tempamb": "MBTA" },    {"foco": "APAGADOF"   ,"vent": "APAGADOV"}),
        ({"edad": "SIET",     "tempcuna": "LRN",     "tempamb": "TAD" },    {"foco": "APAGADOF"   ,"vent": "APAGADOV"}),
        ({"edad": "SIET",     "tempcuna": "LRN",     "tempamb": "MATA" },    {"foco": "APAGADOF"   ,"vent": "MAXV"}),
        
        
        ({"edad": "SIET",     "tempcuna": "MA",     "tempamb": "MBTA" },    {"foco": "APAGADOF"   ,"vent": "APAGADOV"}),
        ({"edad": "SIET",     "tempcuna": "MA",     "tempamb": "TAD" },    {"foco": "APAGADOF"   ,"vent": "APAGADOV"}),
        ({"edad": "SIET",     "tempcuna": "MA",     "tempamb": "MATA" },    {"foco": "APAGADOF"   ,"vent": "MAXV"}),
        
        
        #Edad: VU ---------------------------------------------------------------------------------------------------
        
        ({"edad": "VU",     "tempcuna": "MB",     "tempamb": "MBTA" },    {"foco": "MAXF"   ,"vent": "APAGADOV"}),
        ({"edad": "VU",     "tempcuna": "MB",     "tempamb": "TAD" },    {"foco": "MAXF"   ,"vent": "APAGADOV"}),
        ({"edad": "VU",     "tempcuna": "MB",     "tempamb": "MATA" },    {"foco": "MAXF"   ,"vent": "MAXV"}),
        
        
        ({"edad": "VU",     "tempcuna": "ENGR",     "tempamb": "MBTA" },    {"foco": "BAJOF"   ,"vent": "APAGADOV"}),
        ({"edad": "VU",     "tempcuna": "ENGR",     "tempamb": "TAD" },    {"foco": "BAJOF"   ,"vent": "APAGADOV"}),
        ({"edad": "VU",     "tempcuna": "ENGR",     "tempamb": "MATA" },    {"foco": "BAJOF"   ,"vent": "MAXV"}),
        
        
        ({"edad": "VU",     "tempcuna": "SIETE",     "tempamb": "MBTA" },    {"foco": "BAJOF"   ,"vent": "BAJOV"}),
        ({"edad": "VU",     "tempcuna": "SIETE",     "tempamb": "TAD" },    {"foco": "BAJOF"   ,"vent": "BAJOV"}),
        ({"edad": "VU",     "tempcuna": "SIETE",     "tempamb": "MATA" },    {"foco": "BAJOF"   ,"vent": "MAXV"}),
        
        
        ({"edad": "VU",     "tempcuna": "LRN",     "tempamb": "MBTA" },    {"foco": "APAGADOF"   ,"vent": "APAGADOV"}),
        ({"edad": "VU",     "tempcuna": "LRN",     "tempamb": "TAD" },    {"foco": "APAGADOF"   ,"vent": "APAGADOV"}),
        ({"edad": "VU",     "tempcuna": "LRN",     "tempamb": "MATA" },    {"foco": "APAGADOF"   ,"vent": "MAXV"}),
        
        
        ({"edad": "VU",     "tempcuna": "MA",     "tempamb": "MBTA" },    {"foco": "APAGADOF"   ,"vent": "MAXV"}),
        ({"edad": "VU",     "tempcuna": "MA",     "tempamb": "TAD" },    {"foco": "APAGADOF"   ,"vent": "MAXV"}),
        ({"edad": "VU",     "tempcuna": "MA",     "tempamb": "MATA" },    {"foco": "APAGADOF"   ,"vent": "MAXV"}),
        
        
        
        
        
        #({"edad": "CERO",     "tempcuna": "SIET"},  {"foco": "MEDIO"}),
        #({"edad": "CERO",     "tempcuna": "ENGR"},  {"foco": "ALTO"}),
        # Temperatura fresca
        #({"edad": "SIETE",   "tempcuna": "LRN"},    {"foco": "APAGADO"}),
        #({"edad": "SIETE",   "tempcuna": "SIET"},  {"foco": "BAJO"}),
        #({"edad": "SIETE",   "tempcuna": "ENGR"},  {"foco": "MEDIO"}),

    ]
    ctrl.add_rules(reglas)
    return ctrl

def ejemplo_balanceo_grua():
    """
    Control difuso para balanceo de carga en grúas.
    Entrada : error de ángulo de balanceo (grados), -30 a +30
    Salida  : corrección de velocidad del cable (-100 a +100 cm/s)
    """
    # --- Variable: Error de ángulo ---
    angulo = FuzzyVariable("Angulo", -30, 30)
    angulo.add_set(FuzzySet("GN",  "trapL", [-30, -20, -10]))  # Grande Negativo
    angulo.add_set(FuzzySet("MN",  "tri",   [-15, -8,  -3]))   # Medio Negativo
    angulo.add_set(FuzzySet("PN",  "tri",   [-5,  -2,   0]))   # Pequeño Negativo
    angulo.add_set(FuzzySet("CE",  "tri",   [-3,   0,   3]))   # Cero
    angulo.add_set(FuzzySet("PP",  "tri",   [0,    2,   5]))   # Pequeño Positivo
    angulo.add_set(FuzzySet("MP",  "tri",   [3,    8,  15]))   # Medio Positivo
    angulo.add_set(FuzzySet("GP",  "trapR", [10,  20,  30]))   # Grande Positivo

    # --- Variable: Corrección de velocidad ---
    velocidad = FuzzyVariable("Velocidad", -100, 100)
    velocidad.add_set(FuzzySet("GN",  "trapL", [-100, -70, -40]))
    velocidad.add_set(FuzzySet("MN",  "tri",   [-60,  -35, -15]))
    velocidad.add_set(FuzzySet("PN",  "tri",   [-25,  -10,  -2]))
    velocidad.add_set(FuzzySet("CE",  "tri",   [-5,    0,    5]))
    velocidad.add_set(FuzzySet("PP",  "tri",   [2,    10,   25]))
    velocidad.add_set(FuzzySet("MP",  "tri",   [15,   35,   60]))
    velocidad.add_set(FuzzySet("GP",  "trapR", [40,   70,  100]))

    # --- Controlador ---
    ctrl = FuzzyController()
    ctrl.add_input("angulo", angulo)
    ctrl.add_output("velocidad", velocidad)

    # --- Reglas (invertidas: ángulo grande negativo → corrección grande positiva) ---
    reglas = [
        ({"angulo": "GN"}, {"velocidad": "GP"}),
        ({"angulo": "MN"}, {"velocidad": "MP"}),
        ({"angulo": "PN"}, {"velocidad": "PP"}),
        ({"angulo": "CE"}, {"velocidad": "CE"}),
        ({"angulo": "PP"}, {"velocidad": "PN"}),
        ({"angulo": "MP"}, {"velocidad": "MN"}),
        ({"angulo": "GP"}, {"velocidad": "GN"}),
    ]
    ctrl.add_rules(reglas)
    return ctrl


def ejemplo_control_avion():
    """
    Control difuso para alabeo (roll) de aeronave.
    Entradas : error_roll (grados), velocidad_angular (grados/s)
    Salida   : deflexión de alerón (-1.0 a +1.0, normalizado)
    """
    # --- Variable: Error de ángulo de alabeo ---
    error_roll = FuzzyVariable("Error_Roll", -45, 45)
    error_roll.add_set(FuzzySet("GN",  "trapL", [-45, -30, -15]))
    error_roll.add_set(FuzzySet("MN",  "tri",   [-20, -10,  -3]))
    error_roll.add_set(FuzzySet("CE",  "tri",   [-5,    0,   5]))
    error_roll.add_set(FuzzySet("MP",  "tri",   [3,    10,  20]))
    error_roll.add_set(FuzzySet("GP",  "trapR", [15,   30,  45]))

    # --- Variable: Velocidad angular ---
    vel_ang = FuzzyVariable("Vel_Angular", -60, 60)
    vel_ang.add_set(FuzzySet("GN", "trapL", [-60, -40, -20]))
    vel_ang.add_set(FuzzySet("MN", "tri",   [-30, -15,  -5]))
    vel_ang.add_set(FuzzySet("CE", "tri",   [-8,    0,   8]))
    vel_ang.add_set(FuzzySet("MP", "tri",   [5,    15,  30]))
    vel_ang.add_set(FuzzySet("GP", "trapR", [20,   40,  60]))

    # --- Variable de Salida: Deflexión de alerón ---
    alerón = FuzzyVariable("Alerón", -1.0, 1.0)
    alerón.add_set(FuzzySet("GN",  "trapL", [-1.0, -0.7, -0.4]))
    alerón.add_set(FuzzySet("MN",  "tri",   [-0.6, -0.3, -0.1]))
    alerón.add_set(FuzzySet("CE",  "tri",   [-0.15, 0.0,  0.15]))
    alerón.add_set(FuzzySet("MP",  "tri",   [0.1,   0.3,  0.6]))
    alerón.add_set(FuzzySet("GP",  "trapR", [0.4,   0.7,  1.0]))

    # --- Controlador ---
    ctrl = FuzzyController()
    ctrl.add_input("error_roll", error_roll)
    ctrl.add_input("vel_ang", vel_ang)
    ctrl.add_output("alerón", alerón)

    # --- Base de reglas (matriz 5x5 simplificada) ---
    reglas = [
        # Error Grande Negativo
        ({"error_roll": "GN", "vel_ang": "GN"}, {"alerón": "GN"}),
        ({"error_roll": "GN", "vel_ang": "MN"}, {"alerón": "GN"}),
        ({"error_roll": "GN", "vel_ang": "CE"}, {"alerón": "GN"}),
        ({"error_roll": "GN", "vel_ang": "MP"}, {"alerón": "MN"}),
        ({"error_roll": "GN", "vel_ang": "GP"}, {"alerón": "CE"}),
        # Error Medio Negativo
        ({"error_roll": "MN", "vel_ang": "GN"}, {"alerón": "GN"}),
        ({"error_roll": "MN", "vel_ang": "MN"}, {"alerón": "MN"}),
        ({"error_roll": "MN", "vel_ang": "CE"}, {"alerón": "MN"}),
        ({"error_roll": "MN", "vel_ang": "MP"}, {"alerón": "CE"}),
        ({"error_roll": "MN", "vel_ang": "GP"}, {"alerón": "MP"}),
        # Error Cero
        ({"error_roll": "CE", "vel_ang": "GN"}, {"alerón": "MN"}),
        ({"error_roll": "CE", "vel_ang": "MN"}, {"alerón": "MN"}),
        ({"error_roll": "CE", "vel_ang": "CE"}, {"alerón": "CE"}),
        ({"error_roll": "CE", "vel_ang": "MP"}, {"alerón": "MP"}),
        ({"error_roll": "CE", "vel_ang": "GP"}, {"alerón": "MP"}),
        # Error Medio Positivo
        ({"error_roll": "MP", "vel_ang": "GN"}, {"alerón": "MN"}),
        ({"error_roll": "MP", "vel_ang": "MN"}, {"alerón": "CE"}),
        ({"error_roll": "MP", "vel_ang": "CE"}, {"alerón": "MP"}),
        ({"error_roll": "MP", "vel_ang": "MP"}, {"alerón": "MP"}),
        ({"error_roll": "MP", "vel_ang": "GP"}, {"alerón": "GP"}),
        # Error Grande Positivo
        ({"error_roll": "GP", "vel_ang": "GN"}, {"alerón": "CE"}),
        ({"error_roll": "GP", "vel_ang": "MN"}, {"alerón": "MP"}),
        ({"error_roll": "GP", "vel_ang": "CE"}, {"alerón": "GP"}),
        ({"error_roll": "GP", "vel_ang": "MP"}, {"alerón": "GP"}),
        ({"error_roll": "GP", "vel_ang": "GP"}, {"alerón": "GP"}),
    ]
    ctrl.add_rules(reglas)
    return ctrl


# ============================================================
# PROGRAMA PRINCIPAL - Demostración
# ============================================================
if __name__ == "__main__":
    print("=" * 55)
    print("  DEMOSTRACIÓN: Librería General de Lógica Difusa")
    print("=" * 55)

    # --- Ejemplo 1: Temperatura y Humedad ---
    print("\n[1] Control de Temperatura y Humedad")
    ctrl_clima = ejemplo_temperatura_humedad()
    casos = [
        {"temp": 15, "hum": 40},   # fresco y normal
        {"temp": 26, "hum": 50},   # cómodo y normal
        {"temp": 38, "hum": 75},   # caliente y húmedo
        {"temp": 10, "hum": 20},   # frío y seco
    ]
    for caso in casos:
        res = ctrl_clima.compute(caso)
        print(f"  Temp={caso['temp']}°C, Hum={caso['hum']}%"
              f"  →  Climatizador: {res['clima']:.1f}%")

    # --- Ejemplo 2: Balanceo de grúa ---
    print("\n[2] Control de Balanceo en Grúa")
    ctrl_grua = ejemplo_balanceo_grua()
    angulos = [-25, -8, -2, 0, 3, 10, 22]
    for ang in angulos:
        res = ctrl_grua.compute({"angulo": ang})
        print(f"  Ángulo={ang:+.0f}°  →  Velocidad cable: {res['velocidad']:+.1f} cm/s")

    # --- Ejemplo 3: Control de avión ---
    print("\n[3] Control de Alabeo de Aeronave")
    ctrl_avion = ejemplo_control_avion()
    casos_avion = [
        {"error_roll": -30, "vel_ang": 0},
        {"error_roll": -10, "vel_ang": 5},
        {"error_roll":   0, "vel_ang": 0},
        {"error_roll":  15, "vel_ang": -8},
        {"error_roll":  35, "vel_ang": 10},
    ]
    for caso in casos_avion:
        res = ctrl_avion.compute(caso)
        print(f"  Error Roll={caso['error_roll']:+.0f}°, VelAng={caso['vel_ang']:+.0f}°/s"
              f"  →  Alerón: {res['alerón']:+.3f}")

    print("\n" + "=" * 55)
    print("  Fin de la demostración")
    print("=" * 55)


