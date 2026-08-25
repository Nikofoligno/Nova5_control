"""Configurazione centralizzata del Nova5 virtuale.

Le pose sono intenzionalmente raccolte qui: quando il braccio verra' montato sul
B2, questa e' l'unica sorgente da calibrare con i limiti meccanici reali, il
TCP della pinza e la zona di ingombro del cane robot.
"""

from __future__ import annotations

JOINTS = ("joint1", "joint2", "joint3", "joint4", "joint5", "joint6")
BASE_FRAME = "base_link"
TCP_LINK = "Link6"
PLANNING_GROUP = "nova5_group"

# Limiti estratti dal modello URDF Nova5 incluso nel pacchetto DOBOT.
JOINT_LIMITS = {
    "joint1": (-6.28, 6.28),
    "joint2": (-3.14, 3.14),
    "joint3": (-2.79, 2.79),
    "joint4": (-6.28, 6.28),
    "joint5": (-6.28, 6.28),
    "joint6": (-6.28, 6.28),
}

# Pose iniziali per il simulatore. Non sono ancora pose certificate per il B2.
# `carry` dovra' diventare la posa compatta che non ostacola la camminata.
POSES = {
    "home": (0.0, 0.5378, -1.1869, 0.0, 1.7785, 0.0),
    "ready": (0.0, 0.15, -1.10, 0.0, 1.45, 0.0),
    "pick": (0.0, 0.72, -1.42, 0.0, 1.65, 0.0),
    "carry": (0.0, 0.30, -0.95, 0.0, 1.60, 0.0),
    # Posa raccolta per fermare il braccio durante le prove simulate. Coincide
    # con carry finche' non saranno disponibili i limiti del montaggio sul B2.
    "safe": (0.0, 0.30, -0.95, 0.0, 1.60, 0.0),
    "place": (0.75, 0.48, -1.15, 0.0, 1.60, 0.0),
}

# Limiti dell'interfaccia operatore. Il driver applica sempre i limiti URDF,
# questi rendono invece l'uso touch meno brusco e piu' prevedibile.
MAX_JOINT_STEP_RAD = 0.10
MAX_TRANSLATION_STEP_M = 0.025
MAX_ROTATION_STEP_RAD = 0.20

# Guardrail per il jog cartesiano. Il percorso viene campionato ogni 2 mm e
# MoveIt rifiuta salti di cinematica; questi limiti sono un'ulteriore difesa
# contro rami IK lontani o configurazioni prossime alla singolarita'.
CARTESIAN_PATH_RESOLUTION_M = 0.002
MAX_CARTESIAN_JOINT_STEP_RAD = 0.12
MAX_CARTESIAN_TOTAL_JOINT_DELTA_RAD = 0.20
MAX_JOINT_SPEED_RAD_S = 0.10
MAX_CARTESIAN_SPEED_M_S = 0.02
MOVEIT_VELOCITY_SCALING = 0.10
MOVEIT_ACCELERATION_SCALING = 0.10
