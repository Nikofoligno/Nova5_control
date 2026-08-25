// La UI non conosce ROS: invia solo piccoli messaggi al gateway WebSocket.
// Questa separazione permette di sostituire il simulatore con un driver reale
// senza riscrivere l'app installata su tablet.
const JOINTS = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"];
const JOINT_LABELS = [
  "Base",
  "Spalla",
  "Gomito",
  "Polso 1",
  "Polso 2",
  "Polso 3",
];
const errorRoot = document.querySelector("#error-message");
let socket;
let lastState = null;
let motionMode = "single";
let activeHold = null;
let motionPending = false;

function send(command) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    errorRoot.textContent = "Gateway non connesso.";
    return false;
  }
  errorRoot.textContent = "";
  socket.send(JSON.stringify(command));
  return true;
}

function sendMotion(command) {
  if (motionPending) return false;
  if (lastState?.motion_active) return false;
  motionPending = send(command);
  return motionPending;
}

function stopActiveHold() {
  if (!activeHold) return;
  const { button } = activeHold;
  button.classList.remove("holding");
  activeHold = null;
  send({ command: "hold_stop" });
}

function motionButton(label, command) {
  const button = document.createElement("button");
  button.textContent = label;
  button.dataset.motion = "true";
  button.addEventListener("click", () => {
    if (motionMode === "single") sendMotion(command());
  });
  button.addEventListener("pointerdown", (event) => {
    if (motionMode !== "hold" || button.disabled) return;
    event.preventDefault();
    stopActiveHold();
    if (motionPending || lastState?.motion_active || lastState?.hold_active) {
      errorRoot.textContent = "Attendi il completamento del movimento corrente.";
      return;
    }
    if (button.setPointerCapture) button.setPointerCapture(event.pointerId);
    button.classList.add("holding");
    activeHold = {
      button,
      pointerId: event.pointerId,
    };
    if (!send({ command: "hold_start", motion: command() })) stopActiveHold();
  });
  ["pointerup", "pointercancel", "lostpointercapture"].forEach((eventName) =>
    button.addEventListener(eventName, (event) => {
      if (
        activeHold?.button === button &&
        activeHold.pointerId === event.pointerId
      ) {
        stopActiveHold();
      }
    }),
  );
  return button;
}

function addAxisControls(target, axes, rotation = false) {
  for (const axis of axes) {
    const cell = document.createElement("div");
    cell.className = "axis-control";
    cell.innerHTML = `<b>${axis.toUpperCase()}${rotation ? " °" : ""}</b>`;
    const step = () =>
      rotation ? 0.0349 : Number(document.querySelector("#axis-step").value);
    cell.append(
      motionButton("−", () => ({
        command: "axis_jog",
        axis,
        direction: -1,
        step: step(),
      })),
      motionButton("+", () => ({
        command: "axis_jog",
        axis,
        direction: 1,
        step: step(),
      })),
    );
    target.append(cell);
  }
}

addAxisControls(document.querySelector("#translation-controls"), [
  "x",
  "y",
  "z",
]);
addAxisControls(
  document.querySelector("#rotation-controls"),
  ["rx", "ry", "rz"],
  true,
);

const jointControls = document.querySelector("#joint-controls");
JOINTS.forEach((joint, index) => {
  const row = document.createElement("div");
  row.className = "joint-row";
  row.innerHTML = `<div><b>J${index + 1} · ${JOINT_LABELS[index]}</b><small>${joint}</small></div>`;
  row.append(
    motionButton("−", () => ({
      command: "joint_jog",
      joint,
      direction: -1,
      step: Number(document.querySelector("#joint-step").value),
    })),
    motionButton("+", () => ({
      command: "joint_jog",
      joint,
      direction: 1,
      step: Number(document.querySelector("#joint-step").value),
    })),
  );
  jointControls.append(row);
});

document.querySelector("#arm-button").onclick = () =>
  send({ command: "arm", enabled: !lastState?.arm_enabled });
document.querySelector("#platform-toggle").onchange = ({ target }) =>
  send({ command: "platform", stable: target.checked });
document.querySelector("#stop-button").onclick = () =>
  send({ command: "stop" });
document.querySelector("#open-gripper").onclick = () =>
  send({ command: "gripper", closed: false });
document.querySelector("#close-gripper").onclick = () =>
  send({ command: "gripper", closed: true });
document.querySelector("#mission-grip").onclick = () =>
  send({ command: "gripper", closed: true });
document.querySelectorAll("[data-pose]").forEach((button) => {
  button.onclick = () => send({ command: "pose", pose: button.dataset.pose });
});
document.querySelectorAll(".mode").forEach(
  (button) =>
    (button.onclick = () => {
      document
        .querySelectorAll(".mode")
        .forEach((item) => item.classList.toggle("active", item === button));
      document
        .querySelector("#axis-panel")
        .classList.toggle("hidden", button.dataset.mode !== "axis");
      document
        .querySelector("#joint-panel")
        .classList.toggle("hidden", button.dataset.mode !== "joint");
    }),
);
document.querySelectorAll("[data-motion-mode]").forEach((button) => {
  button.onclick = () => {
    stopActiveHold();
    motionMode = button.dataset.motionMode;
    document
      .querySelectorAll("[data-motion-mode]")
      .forEach((item) => item.classList.toggle("active", item === button));
  };
});
window.addEventListener("blur", stopActiveHold);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) stopActiveHold();
});
document.querySelectorAll(".nav-item").forEach(
  (button) =>
    (button.onclick = () => {
      document
        .querySelectorAll(".nav-item")
        .forEach((item) => item.classList.toggle("active", item === button));
      document
        .querySelectorAll(".tab-page")
        .forEach((page) =>
          page.classList.toggle(
            "active",
            page.id === `${button.dataset.tab}-tab`,
          ),
        );
    }),
);

function render(state) {
  lastState = state;
  // L'ACK conferma solo la ricezione del messaggio. Il pulsante torna
  // disponibile solo quando ROS segnala che la traiettoria e' conclusa.
  if (motionPending && !state.motion_active) motionPending = false;
  const canMove = state.connected && state.arm_enabled && state.platform_stable;
  const dot = document.querySelector("#connection-dot");
  dot.classList.toggle("online", state.connected);
  document.querySelector("#connection-label").textContent = state.connected
    ? "Simulatore online"
    : "Simulatore assente";
  const arm = document.querySelector("#arm-button");
  arm.classList.toggle("active", state.arm_enabled);
  arm.textContent = state.arm_enabled ? "ARM ABILITATO" : "ABILITA ARM";
  document.querySelector("#arm-status").textContent = state.arm_enabled
    ? "Braccio abilitato"
    : "Braccio bloccato";
  document.querySelector("#platform-status").textContent = state.platform_stable
    ? "B2 stabile · interlock pronto"
    : "B2 in movimento · interlock attivo";
  document.querySelector("#platform-toggle").checked = state.platform_stable;
  document.querySelector("#gripper-state").textContent = state.gripper_closed
    ? "Chiusa"
    : "Aperta";
  document.querySelector("#last-command").textContent = state.motion_active
    ? `${state.last_command} · in movimento`
    : state.last_command;
  document.querySelectorAll("[data-motion]").forEach((button) => {
    const isHeldButton = activeHold?.button === button;
    const jogBusy = motionPending || state.motion_active || state.hold_active;
    button.disabled = !canMove || (!isHeldButton && jogBusy);
  });
  document.querySelectorAll("[data-pose], #mission-grip").forEach((button) => {
    button.disabled = !canMove || state.motion_active;
  });
  const values = document.querySelector("#joint-values");
  values.innerHTML = "";
  JOINTS.forEach((joint, index) => {
    const cell = document.createElement("div");
    cell.className = "joint-value";
    cell.innerHTML = `<b>J${index + 1}</b>${Number(state.joints[joint]).toFixed(3)} rad`;
    values.append(cell);
  });
  if (state.last_error) errorRoot.textContent = state.last_error;
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${location.host}/ws`);
  socket.onmessage = ({ data }) => {
    const message = JSON.parse(data);
    if (message.type === "state") render(message.data);
    if (message.type === "error") {
      motionPending = false;
      if (activeHold) {
        activeHold.button.classList.remove("holding");
        activeHold = null;
      }
      errorRoot.textContent = message.message;
    }
  };
  socket.onclose = () => {
    motionPending = false;
    activeHold = null;
    window.setTimeout(connect, 1500);
  };
}
connect();
if ("serviceWorker" in navigator)
  navigator.serviceWorker.register("/assets/sw.js");
