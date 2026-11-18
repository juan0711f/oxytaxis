# Control óptimo de terapias en un modelo de glioblastoma con oxitaxis

[![arXiv](https://img.shields.io/badge/arXiv-2604.21674-b31b1b.svg)](https://arxiv.org/abs/2604.21674)
[![FreeFem++](https://img.shields.io/badge/FreeFem%2B%2B-4.15-3a6ea5.svg)](https://freefem.org/)
[![Python](https://img.shields.io/badge/Python-3-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
![Plataforma](https://img.shields.io/badge/plataforma-macOS%20%7C%20Linux-lightgrey.svg)
[![Licencia: Apache 2.0](https://img.shields.io/badge/licencia-Apache%202.0-blue.svg)](LICENSE)

Código de las simulaciones numéricas del artículo [*Optimal control of therapies related to an oxytaxis glioblastoma model*](https://arxiv.org/abs/2604.21674), de J. J. Forero-Hernández, F. Guillén-González y É. J. Villamizar-Roa. Está escrito en FreeFem++ e incluye un monitor en Python para revisar las corridas.

## Modelo y método

El modelo es un sistema tipo Keller-Segel para la densidad de células tumorales $u$ y la concentración de oxígeno $\sigma$ en un corte axial del cerebro, con condiciones de Neumann homogéneas:

$$
\partial_t u = D_u\Delta u + \rho(\sigma)u(\alpha-u) - \kappa c(t)u\sigma - \chi\nabla\cdot(u\nabla\sigma),
$$

$$
\partial_t\sigma = D_\sigma\Delta\sigma + P_{er}S_v(\beta-\sigma) - \frac{A_{ox}u\sigma}{k_{ox}+\sigma} + (1-s(t))S_c u.
$$

Los controles son la quimioterapia $c$ y la terapia antiangiogénica $s$. En las simulaciones dependen solo del tiempo, toman valores en $[0,1]$ y la dosis total de quimioterapia cumple $\int_0^T c(t)dt \le c_{\max}$. El funcional penaliza $u^2$ y $(\sigma-\beta)^2$ durante el tratamiento y en $t=T$, además de la cantidad de cada terapia.

Las ecuaciones se discretizan con elementos finitos $P_1$ en espacio y un esquema lineal, desacoplado y de primer orden en tiempo. En cada iteración se resuelven el estado hacia adelante y el adjunto hacia atrás, se calcula el gradiente del funcional reducido y se actualizan los controles con Adam. Luego se truncan a sus cotas y $c$ se proyecta sobre la restricción integral, buscando el multiplicador por bisección. El algoritmo para cuando $J$ cambia menos de $3\cdot 10^{-5}$ en cinco iteraciones seguidas, o al llegar a `-maxControlIter`.

## Requisitos

- [FreeFem++](https://freefem.org/) 4.15. Las corridas del artículo se hicieron con `v4.15-175-g822d1d2e9`.
- Python 3 con Matplotlib, solo para `monitor.py`.
- macOS o Linux: el programa llama a `mkdir`, `sed`, `date` y `rm` desde FreeFem++. En Windows hace falta WSL.

## Uso

Los comandos se ejecutan desde esta carpeta, porque las rutas a `src/` y `results/` son relativas.

```bash
# Ayuda
FreeFem++ code.edp -h

# Evolución sin control
FreeFem++ -nw code.edp -nSimulacion 10 -soloCrecimiento

# Control óptimo, prueba corta
FreeFem++ -nw code.edp -nSimulacion 11 -nIter 25 -T 0.2 -maxControlIter 3

# Ver la corrida
python3 monitor.py 11
```

Cada corrida se guarda en `results/Simulacion<n>/`. Si ya hay una corrida del mismo modo con ese número, el programa pregunta antes de borrarla. `-nw` evita que FreeFem++ abra ventanas; quítalo si usas `-mostrarU` o `-mostrarSigma`.

### Opciones

| Opción | Descripción |
| --- | --- |
| `-nSimulacion <n>` | Número de la simulación. Obligatoria. |
| `-soloCrecimiento` | Resuelve solo el estado, con $c=s=0$. Sin esta opción se corre el control óptimo. |
| `-nIter <int>`, `-T <real>` | Pasos de tiempo y tiempo final, con `dt = T/nIter`. Por defecto 250 y 2. |
| `-maxControlIter <int>` | Máximo de iteraciones de Adam. Por defecto 400; con `-1` no hay límite. |
| `-loadControls <archivo>` | Arranca desde un `Controles_FuncionalMinimo.txt` en lugar del control inicial ($c=1$ hasta agotar $c_{\max}$, $s=0.2$). Sirve para continuar una corrida con el mismo `nIter`. |
| `-mesh <archivo>` | Malla. Por defecto `src/sources/axial.mesh`. |
| `-mostrarU`, `-mostrarSigma` | Dibujan $u$ y $\sigma$ en cada paso de tiempo. |
| `-c "<texto>"` | Comentario que queda en el resumen de la corrida. |

Los parámetros del modelo, del funcional y de Adam también se cambian por línea de comandos. Sus valores por defecto, en `src/config/modelParams.idp`, son los del artículo.

| Opción | Parámetro | Por defecto |
| --- | --- | --- |
| `-Du`, `-DSigma` | $D_u$, $D_\sigma$ | 2, 0.02 |
| `-alpha`, `-beta` | $\alpha$, $\beta$ | 4, 1 |
| `-pmax`, `-b` | $\hat\rho$, $b$ | 3.5, 1 |
| `-xhi`, `-psi` | $\chi$, $\kappa$ | 10, 2 |
| `-Aox`, `-kox` | $\alpha A_{ox}$, $k_{ox}$ | 0.6, 0.1 |
| `-Per`, `-Sv`, `-Sc` | $P_{er}$, $S_v$, $S_c$ | 0.1, 1, 0.4 |
| `-CT` | $c_{\max}$ | 0.25 |
| `-cmax` | cota superior de $c$ | 1 |
| `-k1` a `-k4`, `-l1`, `-l2` | $k_1$ a $k_4$, $l_1$, $l_2$ | 1 |
| `-alpha0Adam`, `-beta1Adam`, `-beta2Adam`, `-epsilonAdam` | $\tau_k$, $\beta_1$, $\beta_2$, $\varepsilon$ | 0.1, 0.9, 0.999, 1e-8 |
| `-sigmaGauss` | ancho relativo de las gaussianas iniciales | 0.1 |

Dos nombres pueden confundir: `-CT` es el $c_{\max}$ del artículo, la cota de $\int_0^T c(t)dt$, mientras que `-cmax` es la cota puntual de $c$. Además, el código divide `-Aox` por $\alpha$, así que el 0.6 por defecto corresponde a $A_{ox}=0.15$.

### Salidas

```text
results/Simulacion<n>/
├── info_controlOptimo.txt             comando, parámetros, J por iteración y resumen final
└── optimalControl/
    ├── data_iter_<k>.txt              estado en cada paso de tiempo, gradientes, controles y J1 a J6
    ├── Controles_FuncionalMinimo.txt  controles con el menor J
    └── residuo_proyectado.txt         J, residuo KKT proyectado, integral de c y norma del gradiente
```

`J1` a `J6` son los términos del funcional en este orden: $u^2$, $(\sigma-\beta)^2$, $u(T)^2$, $(\sigma(T)-\beta)^2$, $c$ y $s$. Con `-soloCrecimiento` se escriben `info_soloCrecimiento.txt` y `soloCrecimiento/data.txt`. Las carpetas `images/` y `solutions/` se crean, pero quedan vacías.

### Monitor

```bash
python3 monitor.py 2    # también acepta Simulacion2 o la ruta a info_controlOptimo.txt
```

Muestra la curva de $J$ y, para la iteración elegida, los controles $c$ y $s$ y la evolución en el tiempo de $\max u$, $\int_\Omega u$, $\int_\Omega u^2$ y $\int_\Omega(\sigma-\beta)^2$. La iteración se elige con un clic sobre la curva de $J$ o escribiendo su número, y `Play` las recorre en orden. Sin argumentos, lista las simulaciones disponibles. Solo lee corridas de control óptimo.

## Reproducir los resultados del artículo

```bash
# Experimento 1: evolución sin control
FreeFem++ -nw code.edp -nSimulacion 5 -soloCrecimiento

# Experimento 2: c_max = 0.25, con l_j = 1 y con l_j = 0
FreeFem++ -nw code.edp -nSimulacion 1 -CT 0.25 -psi 2 -l1 1 -l2 1 -maxControlIter 600
FreeFem++ -nw code.edp -nSimulacion 2 -CT 0.25 -psi 2 -l1 0 -l2 0 -maxControlIter 600

# Experimento 3: c_max = 0.75, con l_j = 1 y con l_j = 0
FreeFem++ -nw code.edp -nSimulacion 3 -CT 0.75 -psi 2 -l1 1 -l2 1 -maxControlIter 600
FreeFem++ -nw code.edp -nSimulacion 4 -CT 0.75 -psi 2 -l1 0 -l2 0 -maxControlIter 600

# Estabilidad del funcional alrededor del control óptimo de la simulación 2
FreeFem++ -nw estabilidad_funcional.edp -nSimulacion 2 -CT 0.25 -psi 2 -l1 0 -l2 0
```

| Carpeta en `results/` | Experimento | Iteraciones | Tiempo |
| --- | --- | ---: | ---: |
| `Simulacion5` | 1, sin control | – | 2 min |
| `Simulacion1` | 2, $l_j=1$ | 551 | 31.3 h |
| `Simulacion2` | 2, $l_j=0$ | 161 | 11.0 h |
| `Simulacion3` | 3, $l_j=1$ | 162 | 11.2 h |
| `Simulacion4` | 3, $l_j=0$ | 444 | 24.6 h |
| `EstabilidadFuncional` | 2, estabilidad de $J$ | – | 40 min |

Los tiempos son de un MacBook Air M4 con 16 GB. Las cuatro corridas de control se detuvieron por el criterio de parada, antes de las 600 iteraciones. La salida completa de todas ellas está en `results/`; para comparar sin sobrescribirla, usa otro número de simulación.

`estabilidad_funcional.edp` toma `Controles_FuncionalMinimo.txt` de la simulación indicada, suma una constante a $c$ o a $s$, vuelve a proyectar sobre el conjunto admisible y recalcula $J$. De ahí salen las figuras de $J(c+\delta)$ y $J(s+\delta)$ del Experimento 2. De la línea de comandos solo lee `-nSimulacion`, `-CT`, `-psi`, `-l1` y `-l2`, que deben coincidir con los de la corrida original; el resto de parámetros queda en sus valores por defecto. Acepta además:

- `-out <carpeta>`: carpeta de salida. Por defecto `results/EstabilidadFuncional/`, que se sobrescribe sin preguntar.
- `-noProject`: no reproyecta sobre la restricción integral; solo trunca a las cotas.
- `-soloCpos`: calcula solo las perturbaciones positivas de $c$.

## Estructura

```text
.
├── code.edp                        programa principal
├── estabilidad_funcional.edp       perturbaciones de J alrededor del control óptimo
├── monitor.py                      visor de resultados
├── src/
│   ├── config/
│   │   ├── configParams.idp        rutas y opciones de ejecución
│   │   └── modelParams.idp         parámetros del modelo, del funcional y de Adam
│   ├── core/
│   │   ├── cli.idp                 lectura y validación de opciones
│   │   ├── edp_problem.idp         esquema para u y σ
│   │   ├── functional.idp          J por la regla del trapecio
│   │   ├── initial_conditions.idp  datos iniciales
│   │   ├── logs_utils.idp          archivos de salida
│   │   ├── macros.idp              ρ(σ) y términos de reacción
│   │   ├── mesh_setup.idp          malla y espacio P1
│   │   └── utils.idp               proyección de c, control inicial y utilidades
│   ├── modes/
│   │   ├── optimal_control.idp     estado, adjunto, gradiente y Adam
│   │   └── solo_crecimiento.idp    evolución sin control
│   └── sources/
│       └── axial.mesh              malla del dominio (53 545 triángulos)
└── results/                        corridas del artículo
```

## Cita

Si usas este código, cita el artículo:

```bibtex
@misc{ForeroHernandez2026,
  title         = {Optimal control of therapies related to an oxytaxis glioblastoma model},
  author        = {Forero-Hern{\'a}ndez, Juan J. and Guill{\'e}n-Gonz{\'a}lez, Francisco and Villamizar-Roa, {\'E}lder J.},
  year          = {2026},
  eprint        = {2604.21674},
  archivePrefix = {arXiv},
  primaryClass  = {math.OC},
  doi           = {10.48550/arXiv.2604.21674},
  url           = {https://arxiv.org/abs/2604.21674}
}
```

## Licencia

Copyright 2026 Juan J. Forero-Hernández, Francisco Guillén-González y Élder J. Villamizar-Roa.

El código se distribuye bajo la licencia Apache 2.0. El texto completo está en [LICENSE](LICENSE) y el aviso de copyright, en [NOTICE](NOTICE).
