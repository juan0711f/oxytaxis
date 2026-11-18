#!/usr/bin/env python3

"""
Monitor grafico para las simulaciones de control optimo.

La idea central:
1. Se lee el archivo info_controlOptimo.txt para encontrar la carpeta real de
   ejecucion, nIter, dt y los valores del funcional J.
2. Se descubren automaticamente los archivos data_iter_<n>.txt.
3. Al seleccionar una iteracion, se lee su archivo data_iter_<n>.txt y se
   actualizan las seis graficas asociadas a esa iteracion.
"""

import argparse                 # Para argumentos por CLI
import re                       # Permite buscar patrones en texto mediante expresiones regulares
from pathlib import Path        # Maneja rutas entre sistemas operativos


FLOAT = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"            # Patron para reconocer numeros reales, con signo opcional y notacion cientifica.

ITER_FILE_RE = re.compile(r"data_iter_(\d+)\.txt$")                 # Almacena la dirección del archivo de iteración a mostrar
SUMMARY_J_RE = re.compile(r"^\s*Iteracion\s+(\d+)\s*:\s*J\s*=\s*(" + FLOAT + r")", re.IGNORECASE)       # Revisa las líneas de resumen
CONTROL_RE = re.compile(r"C\[(\d+)\]\s*=\s*(" + FLOAT + r")\s*[,;]\s*S\[\d+\]\s*=\s*(" + FLOAT + r")", re.IGNORECASE)   # Revisa las líneas de controles
MIN_ITER_RE = re.compile(r"Iteraci[oó]n\s+del\s+funcional\s+m[ií]nimo\s*:\s*(\d+)", re.IGNORECASE)      # Revisa la línea que indica donde se alcanzo el mejor funcional.
STATE_RE = re.compile(              # Revisa las líneas de estados (volumen, min u, min max, etc etc)
    r"Iteraci[oó]n\s*:\s*(\d+).*?"
    r"Volumen\s*[:=]\s*(" + FLOAT + r").*?"
    r"Min\s+u\s*[:=]\s*(" + FLOAT + r").*?"
    r"Max\s+u\s*[:=]\s*(" + FLOAT + r").*?"
    r"Min\s+(?:s|sigma)\s*[:=]\s*(" + FLOAT + r").*?"
    r"Max\s+(?:s|sigma)\s*[:=]\s*(" + FLOAT + r").*?"
    r"Integral\s+u\^2\s*[:=]\s*(" + FLOAT + r").*?"
    r"Integral\s+\(sigma-sigmaQ\)\^2\s*[:=]\s*(" + FLOAT + r")",
    re.IGNORECASE,
)
FUNCTIONAL_RE = re.compile(         # Revisa las líneas del funcional completo dentro de data_iter (J, J1, ..., J6)
    r"Funcional\s+J\s*[:=]\s*(" + FLOAT + r").*?"
    r"J1\s*[:=]\s*(" + FLOAT + r").*?"
    r"J2\s*[:=]\s*(" + FLOAT + r").*?"
    r"J3\s*[:=]\s*(" + FLOAT + r").*?"
    r"J4\s*[:=]\s*(" + FLOAT + r").*?"
    r"J5\s*[:=]\s*(" + FLOAT + r").*?"
    r"J6\s*[:=]\s*(" + FLOAT + r")",
    re.IGNORECASE,
)
INTEGRAL_C_RE = re.compile(r"Integral\s+temporal\s+de\s+C\s*[:=]\s*(" + FLOAT + r")", re.IGNORECASE)        # Revisa la línea de la integral de C
CAPACITY_RE = re.compile(r"Capacidad\s+de\s+carga\s*[:=]\s*(" + FLOAT + r")", re.IGNORECASE)                # Revisa la línea de la capacidad de carga


# ====================================================================================================
# =================================== Definición de clases ===========================================
# ====================================================================================================

""" Informacion tomada del archivo de resumen """
class SummaryInfo:
    def __init__(self, simulation_name, summary_path, run_folder, n_iter=None, dt=None, total_time=None, c_max=None, j_by_iteration=None):
        self.simulation_name = simulation_name                                          # Nombre de la simulacion, usado en el titulo de la ventana.
        self.summary_path = summary_path                                                # Ruta al archivo info_controlOptimo.txt.
        self.run_folder = run_folder                                                    # Carpeta donde estan los archivos de cada iteracion.
        self.n_iter = n_iter                                                            # Numero total de iteraciones reportado por el resumen.
        self.dt = dt                                                                    # Paso temporal de la simulacion.
        self.total_time = total_time                                                    # Tiempo final T.
        self.c_max = c_max                                                              # Cota superior del control C.
        self.j_by_iteration = j_by_iteration if j_by_iteration is not None else {}      # J por iteracion.

""" Evolucion en tiempo que se grafica para una iteracion """
class TimeEvolution:
    def __init__(self):
        self.steps = []
        self.volume = []
        self.min_u = []
        self.max_u = []
        self.min_sigma = []
        self.max_sigma = []
        self.integral_u2 = []
        self.integral_sigma_q2 = []

""" Datos detallados leidos de data_iter_<n>.txt """
class IterationData:
    def __init__(self, iteration, path):
        self.iteration = iteration
        self.path = path
        self.control_steps = []
        self.control_c = []
        self.control_s = []
        self.states = TimeEvolution()
        self.functional = {}
        self.integral_c = None
        self.carrying_capacity = None

""" Controles guardados en Controles_FuncionalMinimo.txt """
class BestControls:
    def __init__(self, steps=None, control_c=None, control_s=None, min_iteration=None):
        self.steps = steps if steps is not None else []
        self.control_c = control_c if control_c is not None else []
        self.control_s = control_s if control_s is not None else []
        self.min_iteration = min_iteration

# ====================================================================================================
# =============================== Funciones de lectura basica ========================================
# ====================================================================================================

""" Lee un archivo de texto evitando caracteres raros """
def read_lines(path):
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.readlines()

""" Encuentra info_controlOptimo.txt a partir de un numero, nombre o ruta """
def resolve_summary_path(argument, results_dir):
    if not argument:        # Si el usuario no paso argumento, se intenta listar las simulaciones disponibles
        sims = []       # Para guardar los nombres de carpetas que sí contienen info_controlOptimo.txt
        if results_dir.exists():
            for folder in sorted(results_dir.iterdir()):
                if folder.is_dir() and (folder / "info_controlOptimo.txt").exists():
                    sims.append(folder.name)
        if sims:
            joined = ", ".join(sims)
            raise SystemExit("Falta la simulacion. Disponibles: " + joined)
        raise SystemExit("Falta la simulacion y no hay resultados de control optimo disponibles.")

    raw = Path(argument)        # Se interpreta el argumento recibido como una ruta.

    # Caso 1: el usuario paso directamente el archivo de resumen.
    if raw.is_file():
        return raw.resolve()
    
    # Caso 2: el usuario paso una carpeta de simulacion.
    if raw.is_dir():
        summary = raw / "info_controlOptimo.txt"
        if summary.exists():
            return summary.resolve()
        raise SystemExit("La carpeta no contiene info_controlOptimo.txt: " + str(raw))
    
    # Caso 3: el usuario paso solo el numero.
    if argument.isdigit():
        sim_name = "Simulacion" + argument
    else:
        sim_name = argument

    summary = results_dir / sim_name / "info_controlOptimo.txt"
    if not summary.exists():
        raise SystemExit("No se encontro el resumen de control optimo: " + str(summary))
    return summary.resolve()


# ====================================================================================================
# ============================== Funciones de lectura del resumen ====================================
# ====================================================================================================

""" Extrae la información principal del archivo resumen """
def process_summary(summary_path, base_dir):
    lines = read_lines(summary_path)
    simulation_name = summary_path.parent.name

    # Si el resumen no trae ruta de ejecucion, se usa la estructura esperada.
    run_folder = summary_path.parent / "optimalControl"

    n_iter = None
    dt = None
    total_time = None
    c_max = None
    j_by_iteration = {}

    for line in lines:
        if "Simulacion" in line and ":" in line:
            left, right = line.split(":", 1)
            if left.strip().lower() == "simulacion":
                simulation_name = right.strip()

        if "- Ejecucion" in line and ":" in line:
            raw_path = line.split(":", 1)[1].strip()
            run_folder = Path(raw_path)
            if not run_folder.is_absolute():
                run_folder = base_dir / run_folder

        match_n_iter = re.search(r"-\s*nIter\s*:\s*(\d+)", line)
        if match_n_iter:
            n_iter = int(match_n_iter.group(1))

        match_dt = re.search(r"-\s*dt\s*:\s*(" + FLOAT + r")", line, re.IGNORECASE)
        if match_dt:
            dt = float(match_dt.group(1))

        match_t = re.search(r"-\s*T\s*:\s*(" + FLOAT + r")", line, re.IGNORECASE)
        if match_t:
            total_time = float(match_t.group(1))

        match_cmax = re.search(r"\bcmax\s*:\s*(" + FLOAT + r")", line, re.IGNORECASE)
        if match_cmax:
            c_max = float(match_cmax.group(1))

        match_j = SUMMARY_J_RE.search(line)
        if match_j:
            j_by_iteration[int(match_j.group(1))] = float(match_j.group(2))

    return SummaryInfo(simulation_name=simulation_name, summary_path=summary_path, run_folder=run_folder, n_iter=n_iter, dt=dt, total_time=total_time, c_max=c_max, j_by_iteration=j_by_iteration)

""" Localiza los archivos individuales data_iter_<n>.txt de cada iteracion de la carpeta de control óptimo """
def discover_iteration_files(run_folder):
    files = {}
    if not run_folder.exists():
        return files
    for path in run_folder.glob("data_iter_*.txt"):
        match = ITER_FILE_RE.match(path.name)
        if match:
            files[int(match.group(1))] = path
    return files

""" Completa los valores de J usando el resumen y, si hace falta, los archivos data_iter. """
def discover_j_values(summary, iteration_files):
    values = dict(summary.j_by_iteration)
    for iteration, path in iteration_files.items():
        if iteration in values:
            continue
        try:
            for line in read_lines(path):
                match = FUNCTIONAL_RE.search(line)
                if match:
                    values[iteration] = float(match.group(1))
                    break
        except OSError:
            pass

    return values


# ====================================================================================================
# =============================== Funciones para procesar los resultados ==================================
# ====================================================================================================

""" Extrae controles C y S desde lineas ya leidas """
def process_controls_from_lines(lines):
    c_by_step = {}
    s_by_step = {}
    for line in lines:
        match = CONTROL_RE.search(line)
        if not match:
            continue
        step = int(match.group(1))
        c_by_step[step] = float(match.group(2))
        s_by_step[step] = float(match.group(3))
    steps = sorted(c_by_step)
    return steps, [c_by_step[i] for i in steps], [s_by_step[i] for i in steps]

""" Lee Controles_FuncionalMinimo.txt si existe. """
def process_best_controls(control_file):
    if not control_file.exists():
        return None
    try:
        lines = read_lines(control_file)
    except OSError:
        return None
    steps, control_c, control_s = process_controls_from_lines(lines)
    min_iteration = None
    for line in lines:
        match = MIN_ITER_RE.search(line)
        if match:
            min_iteration = int(match.group(1))
    if not steps:
        return None
    return BestControls(steps=steps, control_c=control_c, control_s=control_s, min_iteration=min_iteration)

""" Lee un data_iter_<n>.txt completo y lo convierte en IterationData """
def process_iteration_file(path, iteration):
    lines = read_lines(path)
    data = IterationData(iteration=iteration, path=path)

    data.control_steps, data.control_c, data.control_s = process_controls_from_lines(lines)

    for line in lines:
        state_match = STATE_RE.search(line)
        if state_match:
            data.states.steps.append(int(state_match.group(1)))
            data.states.volume.append(float(state_match.group(2)))
            data.states.min_u.append(float(state_match.group(3)))
            data.states.max_u.append(float(state_match.group(4)))
            data.states.min_sigma.append(float(state_match.group(5)))
            data.states.max_sigma.append(float(state_match.group(6)))
            data.states.integral_u2.append(float(state_match.group(7)))
            data.states.integral_sigma_q2.append(float(state_match.group(8)))
            continue

        functional_match = FUNCTIONAL_RE.search(line)
        if functional_match:
            data.functional = {
                "J": float(functional_match.group(1)),
                "J1": float(functional_match.group(2)),
                "J2": float(functional_match.group(3)),
                "J3": float(functional_match.group(4)),
                "J4": float(functional_match.group(5)),
                "J5": float(functional_match.group(6)),
                "J6": float(functional_match.group(7)),
            }
            continue

        integral_match = INTEGRAL_C_RE.search(line)
        if integral_match:
            data.integral_c = float(integral_match.group(1))
            continue

        capacity_match = CAPACITY_RE.search(line)
        if capacity_match:
            data.carrying_capacity = float(capacity_match.group(1))

    return data


# ====================================================================================================
# =============================== Funciones de carga de iteraciones ==================================
# ====================================================================================================

""" Lee los resultados de una iteracion desde su archivo data_iter_<n>.txt """
def load_iteration(iteration, iteration_files):
    path = iteration_files.get(iteration)
    if path is None:
        return None
    try:
        return process_iteration_file(path, iteration)
    except OSError:
        return None


# ====================================================================================================
# =============================== Funciones de texto para la interfaz ================================
# ====================================================================================================
""" Texto resumen que se muestra en la parte superior superior """
def format_functional_text(iteration, data, j_value):
    lines = [f"iter {iteration}"]

    if data and data.functional:
        parts = data.functional
        lines[0] += f" | J={parts['J']:.6g}"
        lines.append(f"J1={parts['J1']:.6g}  J2={parts['J2']:.6g}  J3={parts['J3']:.6g}")
        lines.append(f"J4={parts['J4']:.6g}  J5={parts['J5']:.6g}  J6={parts['J6']:.6g}")
    elif j_value is not None:
        lines[0] += f" | J={j_value:.6g}"
    else:
        lines[0] += " | J sin dato"

    if data and data.integral_c is not None:
        lines.append(f"Integral temporal de C: {data.integral_c:.6g}")

    if data:
        lines.append(f"Estados leidos: {len(data.states.steps)} | Controles leidos: {len(data.control_steps)}")

    return "\n".join(lines)

# ====================================================================================================
# =============================== GUI ================================================================
# ====================================================================================================

""" Crea la ventana gráfica interactiva """
def run_gui(summary_path):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from matplotlib.widgets import Button, Slider, TextBox

    base_dir = Path(__file__).resolve().parent
    summary = process_summary(summary_path, base_dir)
    iteration_files = discover_iteration_files(summary.run_folder)
    j_values = discover_j_values(summary, iteration_files)

    # Datos que pueden cambiar mientras la ventana está abierta.
    state = {
        "summary": summary,                     # Resumen
        "iteration_files": iteration_files,     # Archivos de iteracion
        "j_values": j_values,                   # Valores de J
        "selected": None,                       # Iteración seleccionada
        "playing": False,                       # Si se esta reproduciendo automaticamente
        "timer": None,                          # Timer de reproduccion
        "speed": 1.0,                           # Velocidad de reproducción
    }

    # La figura se organiza asi:
    # fila 0:    panel de los controles (play, restart, velocidad, iteracion)
    # fila 1:    grafica del funcional J
    # filas 2-4: seis graficas que cambian con la iteracion seleccionada
    fig = plt.figure(figsize=(13.5, 10.5))
    manager = getattr(fig.canvas, "manager", None)
    if manager is not None and hasattr(manager, "set_window_title"):
        manager.set_window_title("Monitor control optimo - " + summary.simulation_name)
    outer = fig.add_gridspec(5, 2, height_ratios=[0.42, 1.15, 1.0, 1.0, 1.0], hspace=0.58, wspace=0.28, left=0.06, right=0.98, top=0.95, bottom=0.06)

    ctrl_ax = fig.add_subplot(outer[0, :])
    ax_j = fig.add_subplot(outer[1, :])
    ax_c = fig.add_subplot(outer[2, 0])
    ax_s = fig.add_subplot(outer[2, 1])
    ax_max_u = fig.add_subplot(outer[3, 0])
    ax_volume = fig.add_subplot(outer[3, 1])
    ax_u2 = fig.add_subplot(outer[4, 0])
    ax_sigma_q2 = fig.add_subplot(outer[4, 1])

    # Fondo para el panel de controles (play, restart, velocidad, iteracion).
    ctrl_ax.axis("off")
    ctrl_ax.set_title("Controles", loc="left", fontsize=11, color="#111827", pad=4)
    ctrl_ax.add_patch(Rectangle((0, 0), 1, 1, transform=ctrl_ax.transAxes, facecolor="#f8fafc", edgecolor="#d9e2ec"))

    # Ejes internos del panel superior.
    box = ctrl_ax.get_position()
    control_positions = {
        "play": (0.02, 0.25, 0.075, 0.5),
        "restart": (0.11, 0.25, 0.09, 0.5),
        "speed": (0.25, 0.32, 0.24, 0.36),
        "iter": (0.54, 0.25, 0.10, 0.5),
    }
    control_axes = {}
    for key, (x, y, width, height) in control_positions.items():
        control_axes[key] = fig.add_axes([box.x0 + x * box.width, box.y0 + y * box.height, width * box.width, height * box.height])

    play_ax = control_axes["play"]
    restart_ax = control_axes["restart"]
    speed_ax = control_axes["speed"]
    iter_ax = control_axes["iter"]

    play_button = Button(play_ax, "Play", color="#e8eef8", hovercolor="#d8e2f2")
    restart_button = Button(restart_ax, "Inicio", color="#e7f6ef", hovercolor="#d1f0e5")
    speed_slider = Slider(speed_ax, "vel", 0.5, 3.0, valinit=1.0, valstep=0.1, color="#a5b4fc")
    iter_box = TextBox(iter_ax, "iter", initial="", color="#f8fafc", hovercolor="#eef2f7")

    info_text = ctrl_ax.text(0.72, 0.50, "Selecciona una iteracion en la grafica de J.", transform=ctrl_ax.transAxes, ha="left", va="center", fontsize=8.5, family="monospace", color="#111827")

    # Linea principal del funcional y fondos de colores entre iteraciones.
    line_j, = ax_j.plot([], [], marker="o", color="#1f77b4", linewidth=1.7)
    selected_marker = ax_j.scatter([], [], s=95, color="#ffeb3b", edgecolors="#b91c1c", linewidths=1.3, zorder=5)
    selected_marker.set_visible(False)
    colored_spans = []

    ax_j.set_title("Funcional de costo J")
    ax_j.set_xlabel("Iteracion de control")
    ax_j.set_ylabel("J")
    ax_j.grid(True, alpha=0.35)

    # Se crean las 6 graficas inferiores.
    line_c, = ax_c.plot([], [], color="#2ca02c", marker="o", linewidth=1.5)
    line_s, = ax_s.plot([], [], color="#ff7f0e", marker="o", linewidth=1.5)
    line_max_u, = ax_max_u.plot([], [], color="#d62728", linewidth=1.6)
    line_volume, = ax_volume.plot([], [], color="#1f77b4", linewidth=1.6)
    line_u2, = ax_u2.plot([], [], color="#9467bd", linewidth=1.6)
    line_sigma_q2, = ax_sigma_q2.plot([], [], color="#8c564b", linewidth=1.6)

    capacity_line = ax_max_u.axhline(0, color="gray", linestyle="--", alpha=0.35)
    capacity_line.set_visible(False)

    plot_specs = [
        (ax_c, "Control C", "Paso temporal", "C"),
        (ax_s, "Control S", "Paso temporal", "S"),
        (ax_max_u, "Max u", "Paso temporal", "Max u"),
        (ax_volume, "Volumen", "Paso temporal", "Volumen"),
        (ax_u2, "Integral u^2", "Paso temporal", "Integral u^2"),
        (ax_sigma_q2, "Integral (sigma-sigmaQ)^2", "Paso temporal", "Integral"),
    ]

    for axis, title, xlabel, ylabel in plot_specs:
        axis.set_title(title)
        axis.set_xlabel(xlabel)
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.35)

    """ Actualiza una linea y reescala sus ejes """
    def update_line(line, xs, ys, y_min=None, y_max=None):
        line.set_data(xs, ys)
        axis = line.axes
        axis.relim()
        axis.autoscale_view()
        if y_min is not None or y_max is not None:
            current_low, current_high = axis.get_ylim()
            axis.set_ylim(y_min if y_min is not None else current_low, y_max if y_max is not None else current_high)

    """ Redibuja J y colorea los intervalos segun suba o baje """
    def update_j_plot():
        for span in colored_spans:
            span.remove()
        colored_spans.clear()

        items = sorted(state["j_values"].items())
        if not items:
            line_j.set_data([], [])
            ax_j.relim()
            ax_j.autoscale_view()
            return

        xs = [item[0] for item in items]
        ys = [item[1] for item in items]
        line_j.set_data(xs, ys)

        # La asignación de coloreses :
        # Verde si J baja
        # rojo si sube
        # amarillo si queda igual.
        for idx in range(1, len(xs)):
            previous_j = ys[idx - 1]
            current_j = ys[idx]
            if current_j < previous_j:
                color = "#bbf7d0"
            elif current_j > previous_j:
                color = "#fecaca"
            else:
                color = "#fef08a"
            colored_spans.append(ax_j.axvspan(xs[idx - 1], xs[idx], color=color, alpha=0.45, zorder=0))

        ax_j.relim()
        ax_j.autoscale_view()
        ax_j.margins(x=0.05, y=0.08)

    """ Carga una iteracion y actualiza las 6 graficas """
    def apply_iteration(iteration):
        data = load_iteration(iteration, state["iteration_files"])
        j_value = state["j_values"].get(iteration)

        if data is None:
            for line in (line_c, line_s, line_max_u, line_volume, line_u2, line_sigma_q2):
                update_line(line, [], [])
            capacity_line.set_visible(False)
            info_text.set_text(f"iter {iteration}: no se pudo leer data_iter_{iteration}.txt")
            return False

        current_summary = state["summary"]
        c_axis_max = max(1.0, current_summary.c_max or 1.0)
        update_line(line_c, data.control_steps, data.control_c, 0.0, c_axis_max * 1.05)
        update_line(line_s, data.control_steps, data.control_s, 0.0, 1.05)
        update_line(line_max_u, data.states.steps, data.states.max_u)
        update_line(line_volume, data.states.steps, data.states.volume)
        update_line(line_u2, data.states.steps, data.states.integral_u2)
        update_line(line_sigma_q2, data.states.steps, data.states.integral_sigma_q2)

        if data.carrying_capacity is not None:
            capacity_line.set_ydata([data.carrying_capacity, data.carrying_capacity])
            capacity_line.set_visible(True)
        else:
            capacity_line.set_visible(False)

        for axis in (ax_c, ax_s, ax_max_u, ax_volume, ax_u2, ax_sigma_q2):
            base_title = axis.get_title().split(" | ")[0]
            axis.set_title(f"{base_title} | iter {iteration}")

        info_text.set_text(format_functional_text(iteration, data, j_value))
        return True

    """
    Selecciona una iteracion desde:
        a) click en la gráfica
        b) insertar iteración en el panel de controles
        c) al reproducir la secuencia de iteraciones
    """
    def select_iteration(iteration):
        if iteration not in state["iteration_files"] and iteration not in state["j_values"]:
            info_text.set_text(f"iter {iteration}: no existe en esta simulacion")
            fig.canvas.draw_idle()
            return False

        state["selected"] = iteration
        if iteration in state["j_values"]:
            selected_marker.set_offsets([[iteration, state["j_values"][iteration]]])
            selected_marker.set_visible(True)
        else:
            selected_marker.set_visible(False)
        ok = apply_iteration(iteration)
        fig.canvas.draw_idle()
        return ok

    """ Encuentra el punto de J mas cercano al hacer click en la gráfica o al hacer hover """
    def closest_j_point(event):
        if event.inaxes != ax_j:
            return None

        xdata = list(line_j.get_xdata())
        ydata = list(line_j.get_ydata())
        if not xdata:
            return None

        best_iteration = None
        best_distance = None
        for x_val, y_val in zip(xdata, ydata):
            px, py = ax_j.transData.transform((x_val, y_val))
            distance = (px - event.x) ** 2 + (py - event.y) ** 2
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_iteration = int(x_val)

        if best_distance is not None and best_distance <= 120:
            return best_iteration
        return None

    # Anotación al hacer hover sobre J
    hover_j = ax_j.annotate("", xy=(0, 0), xytext=(10, 10), textcoords="offset points", bbox=dict(boxstyle="round", fc="white", ec="#9ca3af", alpha=0.95), arrowprops=dict(arrowstyle="->"))
    hover_j.set_visible(False)

    hover_entries = []
    for axis, line in ((ax_c, line_c), (ax_s, line_s), (ax_max_u, line_max_u), (ax_volume, line_volume), (ax_u2, line_u2), (ax_sigma_q2, line_sigma_q2)):
        annotation = axis.annotate("", xy=(0, 0), xytext=(10, 10), textcoords="offset points", bbox=dict(boxstyle="round", fc="white", ec="#9ca3af", alpha=0.95), arrowprops=dict(arrowstyle="->"))
        annotation.set_visible(False)
        hover_entries.append((axis, line, annotation))

    """ Punto mas cercano de una linea cualquiera """
    def closest_line_point(axis, line, event):
        if event.inaxes != axis:
            return None

        xdata = list(line.get_xdata())
        ydata = list(line.get_ydata())
        if not xdata:
            return None

        best = None
        best_distance = None
        for x_val, y_val in zip(xdata, ydata):
            px, py = axis.transData.transform((x_val, y_val))
            distance = (px - event.x) ** 2 + (py - event.y) ** 2
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best = (x_val, y_val)

        if best_distance is not None and best_distance <= 120:
            return best
        return None
    
    """ Muestra valores al pasar el mouse por las curvas """
    def on_move(event):
        iteration = closest_j_point(event)
        if iteration is not None:
            j_value = state["j_values"].get(iteration)
            hover_j.xy = (iteration, j_value)
            hover_j.set_text(f"iter {iteration}\nJ={j_value:.6g}")
            hover_j.set_visible(True)
            fig.canvas.draw_idle()
        elif hover_j.get_visible():
            hover_j.set_visible(False)
            fig.canvas.draw_idle()

        for axis, line, annotation in hover_entries:
            point = closest_line_point(axis, line, event)
            if point is None:
                if annotation.get_visible():
                    annotation.set_visible(False)
                    fig.canvas.draw_idle()
                continue
            x_val, y_val = point
            annotation.xy = (x_val, y_val)
            annotation.set_text(f"paso={x_val:g}\nvalor={y_val:.6g}")
            annotation.set_visible(True)
            fig.canvas.draw_idle()

    """ Selecciona iteraciones con click sobre J """
    def on_click(event):
        iteration = closest_j_point(event)
        if iteration is not None:
            select_iteration(iteration)

    fig.canvas.mpl_connect("motion_notify_event", on_move)
    fig.canvas.mpl_connect("button_press_event", on_click)

    """ Convierte el slider de velocidad a milisegundos """
    def playback_interval_ms():
        factor = max(0.5, min(3.0, float(state["speed"])))
        iterations_per_second = 1.0 + (factor - 0.5) * (12.0 - 1.0) / (3.0 - 0.5)
        return int(1000.0 / iterations_per_second)

    """ Detiene el timer de reproduccion si existe """
    def stop_timer():
        timer = state.get("timer")
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
        state["timer"] = None

    """ Avanza una iteracion durante el play """
    def playback_step():
        if not state["playing"]:
            return

        order = sorted(state["j_values"])
        if not order:
            state["playing"] = False
            play_button.label.set_text("Play")
            stop_timer()
            return

        selected = state["selected"]
        if selected in order:
            next_index = (order.index(selected) + 1) % len(order)
        else:
            next_index = 0

        select_iteration(order[next_index])

    """ Boton Play o Pausa, según corresponda """
    def toggle_play(event=None):
        if state["playing"]:
            state["playing"] = False
            play_button.label.set_text("Play")
            stop_timer()
        else:
            state["playing"] = True
            play_button.label.set_text("Pausa")
            if state["timer"] is None:
                timer = fig.canvas.new_timer(interval=playback_interval_ms())
                timer.add_callback(playback_step)
                state["timer"] = timer
            state["timer"].interval = playback_interval_ms()
            state["timer"].start()
            playback_step()
        fig.canvas.draw_idle()

    """ Actualiza la velocidad de reproduccion """
    def change_speed(value):
        state["speed"] = float(value)
        timer = state.get("timer")
        if timer is not None:
            timer.interval = playback_interval_ms()
            if state["playing"]:
                timer.stop()
                timer.start()

    """ Selecciona la iteracion escrita en el panel de controles """
    def submit_iteration(text):
        try:
            iteration = int(text.strip())
        except ValueError:
            info_text.set_text("Escribe un numero de iteracion valido.")
            fig.canvas.draw_idle()
            return
        select_iteration(iteration)

    play_button.on_clicked(toggle_play)
    restart_button.on_clicked(lambda event: select_iteration(sorted(state["j_values"])[0]) if state["j_values"] else None)
    speed_slider.on_changed(change_speed)
    iter_box.on_submit(submit_iteration)

    """ Limpia el timer al cerrar la ventana """
    def on_close(event):
        state["playing"] = False
        stop_timer()

    fig.canvas.mpl_connect("close_event", on_close)

    # ===============================================================
    # Carga inicial de las graficas con una una iteración seleccionada.
    update_j_plot()
    best_controls = process_best_controls(summary.run_folder / "Controles_FuncionalMinimo.txt")
    if best_controls is not None:
        update_line(line_c, best_controls.steps, best_controls.control_c, 0.0, max(1.0, summary.c_max or 1.0) * 1.05)
        update_line(line_s, best_controls.steps, best_controls.control_s, 0.0, 1.05)
        min_text = "funcional minimo"
        if best_controls.min_iteration is not None:
            min_text += f" iter {best_controls.min_iteration}"
        ax_c.set_title("Control C | " + min_text)
        ax_s.set_title("Control S | " + min_text)

    if j_values:
        initial_iteration = best_controls.min_iteration if best_controls and best_controls.min_iteration in j_values else min(j_values)
        select_iteration(initial_iteration)
    else:
        info_text.set_text("No hay valores de J para graficar.")

    plt.show()


# ====================================================================================================
# =============================== Main ================================================================
# ====================================================================================================
def main():
    arg = argparse.ArgumentParser(description="Monitor de resultados para el problema de control optimo.")
    arg.add_argument("simulacion", nargs="?", help="Numero, nombre de carpeta o ruta al info_controlOptimo.txt.")
    args = arg.parse_args()

    base_dir = Path(__file__).resolve().parent
    summary_path = resolve_summary_path(args.simulacion, base_dir / "results")

    run_gui(summary_path)


if __name__ == "__main__":
    main()
