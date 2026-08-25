"""API HTTP/WebSocket e hosting della web app mobile Nova5."""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import rclpy
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from rclpy.executors import MultiThreadedExecutor

from ros_driver import SimulationArmDriver


class GatewayRuntime:
    """Gestisce l'executor ROS in background per lasciare libero il loop FastAPI."""

    def __init__(self) -> None:
        rclpy.init(args=None)
        self.node = SimulationArmDriver()
        self.executor = MultiThreadedExecutor()
        self.executor.add_node(self.node)
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def _spin(self) -> None:
        """Ferma silenziosamente l'executor quando ROS riceve un segnale."""
        try:
            self.executor.spin()
        except Exception:
            # Durante lo shutdown Uvicorn e rclpy possono gestire lo stesso
            # segnale. In quel caso il contesto ROS e' gia' invalido.
            if rclpy.ok():
                raise

    def close(self) -> None:
        self.executor.shutdown()
        self.node.destroy_node()
        # rclpy puo' aver gia' ricevuto SIGINT/SIGTERM durante lo shutdown di
        # Uvicorn; non tentare un secondo shutdown sullo stesso contesto.
        if rclpy.ok():
            rclpy.shutdown()
        self.thread.join(timeout=2.0)


runtime: GatewayRuntime | None = None
ROOT = Path(__file__).parent
WEB = ROOT / "web"


@asynccontextmanager
async def lifespan(_: FastAPI):
    global runtime
    runtime = GatewayRuntime()
    try:
        yield
    finally:
        if runtime is not None:
            runtime.close()
            runtime = None


app = FastAPI(title="Nova5 Mobile Simulation Gateway", lifespan=lifespan)
app.mount("/assets", StaticFiles(directory=WEB), name="assets")


@app.get("/")
async def dashboard() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/health")
async def health() -> dict[str, Any]:
    assert runtime is not None
    return runtime.node.state()


async def handle_command(payload: dict[str, Any]) -> dict[str, Any]:
    """Converte il piccolo protocollo WebSocket in chiamate tipizzate del driver."""
    assert runtime is not None
    command = payload.get("command")
    try:
        if command == "arm":
            runtime.node.set_arm_enabled(_required_bool(payload, "enabled"))
        elif command == "platform":
            runtime.node.set_platform_stable(_required_bool(payload, "stable"))
        elif command == "pose":
            await asyncio.to_thread(runtime.node.move_pose, str(payload.get("pose")))
        elif command == "joint_jog":
            await asyncio.to_thread(
                runtime.node.jog_joint,
                str(payload.get("joint")),
                int(payload.get("direction")),
                float(payload.get("step")),
            )
        elif command == "axis_jog":
            await asyncio.to_thread(
                runtime.node.jog_axis,
                str(payload.get("axis")),
                int(payload.get("direction")),
                float(payload.get("step")),
            )
        elif command == "hold_start":
            motion = _required_hold_motion(payload)
            await asyncio.to_thread(
                runtime.node.start_hold,
                motion["command"],
                motion["target"],
                motion["direction"],
                motion["step"],
            )
        elif command == "gripper":
            runtime.node.set_gripper(_required_bool(payload, "closed"))
        elif command == "hold_stop":
            # Il rilascio di un pulsante di jog interrompe il solo movimento;
            # ARM resta abilitato per consentire il successivo comando touch.
            runtime.node.stop(disarm=False)
        elif command == "stop":
            runtime.node.stop()
        else:
            raise ValueError("Comando non riconosciuto.")
        return {"type": "ack", "command": command}
    except (RuntimeError, TypeError, ValueError) as error:
        runtime.node.record_error(str(error))
        return {"type": "error", "message": str(error)}


def _required_bool(payload: dict[str, Any], field: str) -> bool:
    """Accetta esclusivamente booleani JSON per i comandi che cambiano stato."""
    value = payload.get(field)
    if not isinstance(value, bool):
        raise ValueError(f"Il campo '{field}' deve essere booleano.")
    return value


def _required_hold_motion(payload: dict[str, Any]) -> dict[str, Any]:
    """Valida il messaggio unico inviato alla pressione di un pulsante jog."""
    motion = payload.get("motion")
    if not isinstance(motion, dict):
        raise ValueError("Comando di pressione non valido.")
    command = motion.get("command")
    if command == "joint_jog":
        target = motion.get("joint")
    elif command == "axis_jog":
        target = motion.get("axis")
    else:
        raise ValueError("Comando di pressione non riconosciuto.")
    direction = motion.get("direction")
    step = motion.get("step")
    if not isinstance(target, str) or isinstance(direction, bool) or not isinstance(direction, int):
        raise ValueError("Parametri di pressione non validi.")
    if isinstance(step, bool) or not isinstance(step, (int, float)):
        raise ValueError("Passo di pressione non valido.")
    return {"command": command, "target": target, "direction": direction, "step": float(step)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Invia telemetria a 5 Hz e gestisce i comandi touch in arrivo."""
    await websocket.accept()
    try:
        while True:
            try:
                payload = await asyncio.wait_for(websocket.receive_json(), timeout=0.20)
                await websocket.send_json(await handle_command(payload))
            except TimeoutError:
                pass
            assert runtime is not None
            await websocket.send_json({"type": "state", "data": runtime.node.state()})
    except WebSocketDisconnect:
        return
