"""Driver ROS 2 del Nova5 simulato.

La classe espone comandi indipendenti dalla UI. L'app mobile comunica soltanto
con questa API tramite il gateway WebSocket; in futuro un driver DOBOT reale
potra' mantenere la stessa interfaccia pubblica.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Any

from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import PoseStamped, Quaternion
from moveit_msgs.msg import Constraints, JointConstraint, MoveItErrorCodes
from moveit_msgs.srv import GetCartesianPath, GetMotionPlan
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import JointState
from tf2_ros import Buffer, TransformListener
from trajectory_msgs.msg import JointTrajectoryPoint

from robot_config import (
    BASE_FRAME,
    CARTESIAN_PATH_RESOLUTION_M,
    JOINT_LIMITS,
    JOINTS,
    MAX_CARTESIAN_JOINT_STEP_RAD,
    MAX_CARTESIAN_SPEED_M_S,
    MAX_CARTESIAN_TOTAL_JOINT_DELTA_RAD,
    MAX_JOINT_STEP_RAD,
    MAX_JOINT_SPEED_RAD_S,
    MAX_ROTATION_STEP_RAD,
    MAX_TRANSLATION_STEP_M,
    MOVEIT_ACCELERATION_SCALING,
    MOVEIT_VELOCITY_SCALING,
    PLANNING_GROUP,
    POSES,
    TCP_LINK,
)


def _quaternion_product(left: Quaternion, right: Quaternion) -> Quaternion:
    """Restituisce la composizione `left * right` di due quaternioni."""
    return Quaternion(
        x=left.w * right.x + left.x * right.w + left.y * right.z - left.z * right.y,
        y=left.w * right.y - left.x * right.z + left.y * right.w + left.z * right.x,
        z=left.w * right.z + left.x * right.y - left.y * right.x + left.z * right.w,
        w=left.w * right.w - left.x * right.x - left.y * right.y - left.z * right.z,
    )


def _axis_angle(axis: str, radians: float) -> Quaternion:
    """Crea il piccolo incremento rotazionale richiesto dal jog TCP."""
    half_angle = radians / 2.0
    sine = math.sin(half_angle)
    values = {"rx": (sine, 0.0, 0.0), "ry": (0.0, sine, 0.0), "rz": (0.0, 0.0, sine)}
    x, y, z = values[axis]
    return Quaternion(x=x, y=y, z=z, w=math.cos(half_angle))


class SimulationArmDriver(Node):
    """Controlla FakeSystem e calcola i piccoli jog cartesiani tramite MoveIt IK."""

    def __init__(self) -> None:
        super().__init__("nova5_sim_gateway")
        self._lock = threading.RLock()
        self._motion_lock = threading.Lock()
        self._positions = {joint: 0.0 for joint in JOINTS}
        self._received_joint_state = False
        # Il target comandato evita che due tocchi ravvicinati perdano un incremento
        # prima che il topic /joint_states abbia aggiornato la posizione effettiva.
        self._commanded_positions = self._positions.copy()
        self._gripper_closed = False
        self._arm_enabled = False
        self._platform_stable = True
        self._last_command = "idle"
        self._last_error: str | None = None
        self._goal_handle: Any | None = None
        self._hold_stop_event: threading.Event | None = None
        self._hold_thread: threading.Thread | None = None

        self._trajectory_client = ActionClient(self, FollowJointTrajectory, "/nova5_group_controller/follow_joint_trajectory")
        self._cartesian_client = self.create_client(GetCartesianPath, "/compute_cartesian_path")
        self._plan_client = self.create_client(GetMotionPlan, "/plan_kinematic_path")
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self, spin_thread=False)
        self._joint_subscription = self.create_subscription(JointState, "/joint_states", self._on_joint_state, 10)

    def _on_joint_state(self, message: JointState) -> None:
        with self._lock:
            updated = False
            for name, position in zip(message.name, message.position):
                if name in self._positions:
                    self._positions[name] = round(float(position), 4)
                    updated = True
            # Se il gateway parte mentre il simulatore e' gia' in una posa,
            # il primo movimento deve iniziare dalla posa reale, non dagli zeri.
            if updated and not self._received_joint_state:
                self._commanded_positions = self._positions.copy()
                self._received_joint_state = True

    @staticmethod
    def _wait_for_future(future: Any, timeout: float, failure_message: str) -> Any:
        """Attende senza rieseguire lo spin: l'executor e' gia' in un thread dedicato."""
        completed = threading.Event()
        future.add_done_callback(lambda _: completed.set())
        if not completed.wait(timeout=timeout):
            raise RuntimeError(failure_message)
        return future.result()

    def _on_goal_complete(self, future: Any, goal_handle: Any) -> None:
        """Rende disponibile il prossimo comando solo a traiettoria conclusa."""
        try:
            future.result()
        except Exception as error:
            self.record_error(f"Errore durante l'esecuzione della traiettoria: {error}")
        finally:
            with self._lock:
                if self._goal_handle is goal_handle:
                    self._goal_handle = None

    def _motion_is_allowed(self) -> None:
        with self._lock:
            if not self._arm_enabled:
                raise RuntimeError("Abilita prima il braccio con il consenso ARM.")
            if not self._platform_stable:
                raise RuntimeError("Interlock attivo: il B2 non e' stabile, movimento bloccato.")
            if self._goal_handle is not None:
                raise RuntimeError("Movimento gia' in corso: attendi la fine oppure premi STOP.")

    def _validate_target(self, target: tuple[float, ...]) -> None:
        if len(target) != len(JOINTS):
            raise ValueError("La traiettoria deve contenere sei posizioni articolari.")
        for joint, position in zip(JOINTS, target):
            lower, upper = JOINT_LIMITS[joint]
            if not lower <= position <= upper:
                raise ValueError(f"{joint} fuori limite: {position:.2f} rad.")

    def state(self) -> dict[str, Any]:
        with self._lock:
            hold_active = self._hold_thread is not None and self._hold_thread.is_alive()
            return {
                "mode": "simulation", "connected": self._trajectory_client.server_is_ready(),
                "arm_enabled": self._arm_enabled, "platform_stable": self._platform_stable,
                "joints": self._positions.copy(), "commanded_joints": self._commanded_positions.copy(),
                "gripper_closed": self._gripper_closed, "last_command": self._last_command,
                "motion_active": self._goal_handle is not None, "hold_active": hold_active,
                "last_error": self._last_error,
                "poses": list(POSES), "timestamp": round(time.time() * 1000),
            }

    def record_error(self, message: str) -> None:
        """Espone alla UI gli errori di protocollo e di movimento piu' recenti."""
        with self._lock:
            self._last_error = message

    def set_arm_enabled(self, enabled: bool) -> None:
        if enabled and not self._platform_stable:
            raise RuntimeError("Stabilizza il B2 prima di abilitare il braccio.")
        with self._lock:
            self._arm_enabled = enabled
            self._last_command = "arm:enabled" if enabled else "arm:disabled"
            self._last_error = None

    def set_platform_stable(self, stable: bool) -> None:
        """Interlock che in produzione sara' alimentato dalla telemetria Unitree."""
        with self._lock:
            self._platform_stable = stable
            self._last_command = "platform:stable" if stable else "platform:moving"
        if not stable:
            # Quando il cane inizia a muoversi non restano comandi pendenti sul braccio.
            self.stop(disarm=True)

    @staticmethod
    def _nearest_equivalent(position: float, reference: float, joint: str) -> float:
        """Sceglie l'equivalente ±2π piu' vicino al giunto osservato."""
        lower, upper = JOINT_LIMITS[joint]
        candidates = [position + 2.0 * math.pi * turns for turns in range(-2, 3)]
        valid = [candidate for candidate in candidates if lower <= candidate <= upper]
        if not valid:
            return position
        return min(valid, key=lambda candidate: abs(candidate - reference))

    def _path_targets(self, trajectory: Any, reference: tuple[float, ...], cartesian: bool) -> list[tuple[float, ...]]:
        """Valida tutti i punti del percorso MoveIt prima di inviarli al controller."""
        names = list(trajectory.joint_names)
        if not trajectory.points or any(joint not in names for joint in JOINTS):
            raise RuntimeError("MoveIt non ha prodotto una traiettoria articolare completa.")
        previous = reference
        targets: list[tuple[float, ...]] = []
        for point in trajectory.points:
            solution = dict(zip(names, point.positions))
            raw = tuple(float(solution[joint]) for joint in JOINTS)
            target = tuple(
                self._nearest_equivalent(position, previous[index], joint)
                for index, (joint, position) in enumerate(zip(JOINTS, raw))
            )
            self._validate_target(target)
            if cartesian:
                if max(abs(new - old) for new, old in zip(target, previous)) > MAX_CARTESIAN_JOINT_STEP_RAD:
                    raise RuntimeError("Jog TCP bloccato: MoveIt ha rilevato un salto articolare.")
            targets.append(target)
            previous = target
        if cartesian and max(abs(new - old) for new, old in zip(targets[-1], reference)) > MAX_CARTESIAN_TOTAL_JOINT_DELTA_RAD:
            raise RuntimeError("Jog TCP bloccato: scegli un passo piu' piccolo o allontanati da una singolarita'.")
        return targets

    def _execute_targets(self, targets: list[tuple[float, ...]], label: str) -> None:
        """Esegue una traiettoria gia' pianificata, con velocita' conservativa."""
        if not targets:
            raise ValueError("La traiettoria pianificata e' vuota.")
        if not self._trajectory_client.wait_for_server(timeout_sec=3.0):
            raise RuntimeError("Il simulatore ROS non e' avviato o il controller non e' pronto.")
        with self._lock:
            previous_target = self._commanded_positions.copy()
            current = tuple(previous_target[joint] for joint in JOINTS)
            self._commanded_positions = dict(zip(JOINTS, targets[-1]))
            self._last_error = None
            self._last_command = label

        elapsed = 0.0
        points: list[JointTrajectoryPoint] = []
        for target in targets:
            max_delta = max(abs(new - old) for new, old in zip(target, current))
            elapsed += max(0.05, max_delta / MAX_JOINT_SPEED_RAD_S)
            point = JointTrajectoryPoint()
            point.positions = list(target)
            point.time_from_start.sec = int(elapsed)
            point.time_from_start.nanosec = int((elapsed % 1) * 1_000_000_000)
            points.append(point)
            current = target

        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = list(JOINTS)
        goal.trajectory.points = points
        goal_handle = self._wait_for_future(
            self._trajectory_client.send_goal_async(goal),
            4.0,
            "Timeout durante l'invio della traiettoria simulata.",
        )
        if goal_handle is None or not goal_handle.accepted:
            with self._lock:
                self._commanded_positions = previous_target
            raise RuntimeError("Il controller simulato ha rifiutato la traiettoria.")
        with self._lock:
            self._goal_handle = goal_handle
        goal_handle.get_result_async().add_done_callback(
            lambda future: self._on_goal_complete(future, goal_handle)
        )

    def _plan_joint_target(self, target: tuple[float, ...], label: str) -> None:
        """Pianifica pose e jog articolari per controllare le collisioni del percorso."""
        self._motion_is_allowed()
        self._validate_target(target)
        if not self._plan_client.wait_for_service(timeout_sec=2.0):
            raise RuntimeError("MoveIt non e' pronto per pianificare il movimento.")
        with self._lock:
            reference = tuple(self._positions[joint] for joint in JOINTS)

        request = GetMotionPlan.Request()
        plan = request.motion_plan_request
        plan.group_name = PLANNING_GROUP
        plan.allowed_planning_time = 2.0
        plan.max_velocity_scaling_factor = MOVEIT_VELOCITY_SCALING
        plan.max_acceleration_scaling_factor = MOVEIT_ACCELERATION_SCALING
        plan.start_state.joint_state.name = list(JOINTS)
        plan.start_state.joint_state.position = list(reference)
        goal = Constraints()
        for joint, position in zip(JOINTS, target):
            constraint = JointConstraint()
            constraint.joint_name = joint
            constraint.position = position
            constraint.tolerance_above = 0.001
            constraint.tolerance_below = 0.001
            constraint.weight = 1.0
            goal.joint_constraints.append(constraint)
        plan.goal_constraints = [goal]

        response = self._wait_for_future(
            self._plan_client.call_async(request),
            4.0,
            "MoveIt non ha risposto alla pianificazione in tempo.",
        )
        if response.motion_plan_response.error_code.val != MoveItErrorCodes.SUCCESS:
            raise RuntimeError("MoveIt non trova un percorso sicuro per il comando richiesto.")
        targets = self._path_targets(response.motion_plan_response.trajectory.joint_trajectory, reference, cartesian=False)
        self._execute_targets(targets, label)

    def move(self, target: tuple[float, ...], label: str) -> None:
        with self._motion_lock:
            self._plan_joint_target(target, label)

    def move_pose(self, pose_name: str) -> None:
        try:
            target = POSES[pose_name]
        except KeyError as error:
            raise ValueError("Pose non riconosciuta.") from error
        self.move(target, f"pose:{pose_name}")

    def jog_joint(self, joint: str, direction: int, step: float) -> None:
        if joint not in JOINTS:
            raise ValueError("Giunto non riconosciuto.")
        if direction not in (-1, 1):
            raise ValueError("Direzione non valida.")
        if not 0.01 <= step <= MAX_JOINT_STEP_RAD:
            raise ValueError("Passo articolare fuori intervallo.")
        with self._lock:
            target = [self._positions[name] for name in JOINTS]
        target[JOINTS.index(joint)] += direction * step
        self.move(tuple(target), f"joint:{joint}")

    def jog_axis(self, axis: str, direction: int, step: float) -> None:
        """Pianifica un breve percorso cartesiano, controllando collisioni e salti IK."""
        if axis not in ("x", "y", "z", "rx", "ry", "rz"):
            raise ValueError("Asse TCP non riconosciuto.")
        if direction not in (-1, 1):
            raise ValueError("Direzione non valida.")
        maximum = MAX_TRANSLATION_STEP_M if axis in ("x", "y", "z") else MAX_ROTATION_STEP_RAD
        if not 0.001 <= step <= maximum:
            raise ValueError("Passo TCP fuori intervallo.")
        with self._motion_lock:
            self._motion_is_allowed()
            if not self._cartesian_client.wait_for_service(timeout_sec=2.0):
                raise RuntimeError("MoveIt cartesiano non e' pronto nel simulatore.")
            try:
                transform = self._tf_buffer.lookup_transform(BASE_FRAME, TCP_LINK, Time())
            except Exception as error:
                raise RuntimeError("TCP non ancora disponibile: attendi un istante e riprova.") from error
            with self._lock:
                reference = tuple(self._positions[joint] for joint in JOINTS)

            pose = PoseStamped()
            pose.header.frame_id = BASE_FRAME
            pose.pose.position.x = transform.transform.translation.x
            pose.pose.position.y = transform.transform.translation.y
            pose.pose.position.z = transform.transform.translation.z
            pose.pose.orientation = transform.transform.rotation
            delta = direction * step
            if axis in ("x", "y", "z"):
                setattr(pose.pose.position, axis, getattr(pose.pose.position, axis) + delta)
            else:
                pose.pose.orientation = _quaternion_product(_axis_angle(axis, delta), pose.pose.orientation)

            request = GetCartesianPath.Request()
            request.header.frame_id = BASE_FRAME
            request.start_state.joint_state.name = list(JOINTS)
            request.start_state.joint_state.position = list(reference)
            request.group_name = PLANNING_GROUP
            request.link_name = TCP_LINK
            request.waypoints = [pose.pose]
            request.max_step = CARTESIAN_PATH_RESOLUTION_M
            request.jump_threshold = 2.0
            request.revolute_jump_threshold = MAX_CARTESIAN_JOINT_STEP_RAD
            request.avoid_collisions = True
            request.max_velocity_scaling_factor = MOVEIT_VELOCITY_SCALING
            request.max_acceleration_scaling_factor = MOVEIT_ACCELERATION_SCALING
            request.cartesian_speed_limited_link = TCP_LINK
            request.max_cartesian_speed = MAX_CARTESIAN_SPEED_M_S
            response = self._wait_for_future(
                self._cartesian_client.call_async(request),
                4.0,
                "MoveIt cartesiano non ha risposto in tempo.",
            )
            if response.error_code.val != MoveItErrorCodes.SUCCESS or response.fraction < 0.999:
                raise RuntimeError("Jog TCP bloccato: il percorso completo non e' raggiungibile in sicurezza.")
            targets = self._path_targets(response.solution.joint_trajectory, reference, cartesian=True)
            self._execute_targets(targets, f"tcp:{axis}")

    def start_hold(self, command: str, target: str, direction: int, step: float) -> None:
        """Avvia un jog continuo lato ROS, senza dipendere dal timer del browser."""
        if command == "joint_jog":
            if target not in JOINTS:
                raise ValueError("Giunto non riconosciuto.")
            if not 0.01 <= step <= MAX_JOINT_STEP_RAD:
                raise ValueError("Passo articolare fuori intervallo.")
        elif command == "axis_jog":
            if target not in ("x", "y", "z", "rx", "ry", "rz"):
                raise ValueError("Asse TCP non riconosciuto.")
            maximum = MAX_TRANSLATION_STEP_M if target in ("x", "y", "z") else MAX_ROTATION_STEP_RAD
            if not 0.001 <= step <= maximum:
                raise ValueError("Passo TCP fuori intervallo.")
        else:
            raise ValueError("Comando di pressione non riconosciuto.")
        if direction not in (-1, 1):
            raise ValueError("Direzione non valida.")
        self._motion_is_allowed()
        with self._lock:
            if self._hold_thread is not None and self._hold_thread.is_alive():
                raise RuntimeError("Un comando a pressione e' gia' attivo.")
            stop_event = threading.Event()
            self._hold_stop_event = stop_event
            self._last_error = None
            self._last_command = f"hold:{target}"
            self._hold_thread = threading.Thread(
                target=self._run_hold,
                args=(stop_event, command, target, direction, step),
                daemon=True,
            )
            self._hold_thread.start()

    def _run_hold(
        self,
        stop_event: threading.Event,
        command: str,
        target: str,
        direction: int,
        step: float,
    ) -> None:
        """Invia un passo successivo solo dopo il completamento del precedente."""
        try:
            while not stop_event.is_set():
                with self._lock:
                    motion_active = self._goal_handle is not None
                if motion_active:
                    stop_event.wait(0.03)
                    continue
                try:
                    if command == "joint_jog":
                        self.jog_joint(target, direction, step)
                    else:
                        self.jog_axis(target, direction, step)
                except (RuntimeError, ValueError) as error:
                    self.record_error(str(error))
                    return
                stop_event.wait(0.03)
        finally:
            with self._lock:
                if self._hold_stop_event is stop_event:
                    self._hold_thread = None
                    self._hold_stop_event = None

    def set_gripper(self, closed: bool) -> None:
        # Segnaposto software: il protocollo resta gia' pronto per il tool reale.
        with self._lock:
            self._gripper_closed = closed
            self._last_command = "gripper:close" if closed else "gripper:open"
            self._last_error = None

    def stop(self, disarm: bool = True) -> None:
        """Annulla la traiettoria virtuale e, per default, richiede nuovo consenso ARM."""
        with self._lock:
            if self._hold_stop_event is not None:
                self._hold_stop_event.set()
        with self._motion_lock:
            with self._lock:
                goal_handle = self._goal_handle
                self._goal_handle = None
                self._last_command = "stop" if disarm else "hold:released"
                # Il prossimo jog deve partire dalla posizione osservata, anche se
                # il rilascio ha interrotto una traiettoria a meta' movimento.
                self._commanded_positions = self._positions.copy()
                if disarm:
                    self._arm_enabled = False
            if goal_handle is not None:
                goal_handle.cancel_goal_async()
