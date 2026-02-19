from adafruit_midi.midi_message import MIDIMessage
from time import monotonic
from pyswitch.controller.actions import Action
from pyswitch.clients.local.actions.custom import CUSTOM_MESSAGE
from pyswitch.hardware.devices.pa_midicaptain_mini_6 import *
from pyswitch.colors import Colors

from display import DISPLAY_HEADER_1, DISPLAY_HEADER_2, DISPLAY_HEADER_3
from display import DISPLAY_FOOTER_1, DISPLAY_FOOTER_2, DISPLAY_FOOTER_3
from display import DISPLAY_PAGE
from display import DISPLAY_MAIN

# MIDI channel is zero-based: 0 => MIDI channel 1
MIDI_CH = 0
HOLD_MS = 600

# Gig View mapping style
# - "short_current": short=current QC page, long=opposite QC page (current behavior)
# - "short_opposite": short=opposite QC page, long=current QC page
GIG_VIEW_STYLE = "short_current"

# Runtime state tracked on controller side.
_STATE = {
    "gig_view": False,
    "midi_page": 2,  # internal page (chain mode)
    "qc_page": 2,    # tracked hardware page (best effort)
    "power_code": -1,  # 0=USB, 1=BAT, 2=DC
    "power": "USB",
    "tuner": False,
    "mode_slot": 0,
    "scene_idx": 0,  # 0..7 (Page1 A-D, Page2 A-D)
}

# key0,key1,key3,key4 map to QC footswitch A,B,C,D
_CC_PAGE_1 = [35, 36, 37, 38]
_CC_PAGE_2 = [39, 40, 41, 42]
_SLOT_NAME = ["A", "B", "C", "D"]
_MODE_NAMES = ["PRE", "SCN", "STP"]
_MODE_COLORS_COOL = [
    Colors.BLUE,       # Preset
    Colors.TURQUOISE,  # Scene
    Colors.LIGHT_BLUE, # Stomp
]
_MODE_COLORS_WARM = [
    Colors.ORANGE, # Preset
    Colors.RED,    # Scene
    Colors.PURPLE, # Stomp
]
_PAGE_COLORS_COOL = {
    1: [Colors.BLUE, Colors.TURQUOISE, Colors.LIGHT_BLUE, Colors.DARK_BLUE],
    2: [Colors.LIGHT_BLUE, Colors.TURQUOISE, Colors.BLUE, Colors.DARK_BLUE],
}
_PAGE_COLORS_WARM = {
    1: [Colors.PINK, Colors.ORANGE, Colors.DARK_YELLOW, Colors.YELLOW],
    2: [Colors.LIGHT_RED, Colors.RED, Colors.PURPLE, Colors.ORANGE],
}


class _RawMessage(MIDIMessage):
    def __init__(self, data):
        self._data = bytearray(data)

    def __bytes__(self):
        return self._data


def _send_cc(appl, cc_num, value):
    appl.client.midi.send(_RawMessage([0xB0 + MIDI_CH, cc_num, value]))


def _refresh_ui(appl, reset=False):
    # reset_actions() only resets callback state; it does not redraw labels/LEDs.
    # Force a full display refresh so state changes are visible immediately.
    if reset:
        appl.reset_actions()

    for inp in appl.inputs:
        for action in inp.actions:
            action.update_displays()


class _StateEquals:
    def __init__(self, key, expected):
        self._key = key
        self._expected = expected

    def init(self, appl):
        pass

    def enabled(self, action):
        return _STATE[self._key] == self._expected


_GIG_ON = _StateEquals("gig_view", True)
_GIG_OFF = _StateEquals("gig_view", False)


def _mode_colors():
    return _MODE_COLORS_COOL if _STATE["gig_view"] else _MODE_COLORS_WARM


def _page_colors():
    return _PAGE_COLORS_COOL if _STATE["gig_view"] else _PAGE_COLORS_WARM

def _status_text():
    mode_name = _MODE_NAMES[_STATE["mode_slot"]]
    if _STATE["gig_view"]:
        short_target = "Current" if GIG_VIEW_STYLE == "short_current" else "Opposite"
        return f"GV {short_target} QP{_STATE['qc_page']}\n{mode_name}"

    # CH: keep internal MIDI page + tracked QC page visible.
    return f"CH\n{mode_name} MP{_STATE['midi_page']} QP{_STATE['qc_page']}"

def _update_status_label():
    tun = " T+" if _STATE["tuner"] else ""
    DISPLAY_PAGE.text = f"[PW: {_STATE['power']}{tun}]"
    if _STATE["tuner"]:
        DISPLAY_PAGE.back_color = Colors.RED
    else:
        DISPLAY_PAGE.back_color = Colors.DARK_BLUE if _STATE["gig_view"] else Colors.DARK_YELLOW
    if _STATE["gig_view"]:
        # Force-sync GV button labels so style toggle is always visible immediately.
        suffix = "C" if GIG_VIEW_STYLE == "short_current" else "O"
        DISPLAY_HEADER_1.text = f"A{suffix}"
        DISPLAY_HEADER_2.text = f"B{suffix}"
        DISPLAY_FOOTER_1.text = f"C{suffix}"
        DISPLAY_FOOTER_2.text = f"D{suffix}"
    DISPLAY_MAIN.text = _status_text()

def _toggle_gig_view_style():
    global GIG_VIEW_STYLE
    if GIG_VIEW_STYLE == "short_current":
        GIG_VIEW_STYLE = "short_opposite"
    else:
        GIG_VIEW_STYLE = "short_current"


class _ToggleCCAction(Action):
    def __init__(
        self,
        state_key,
        cc_num,
        display=None,
        text="",
        color_on=Colors.GREEN,
        color_off=Colors.RED,
        led_brightness=0.3,
        use_leds=True,
        enable_callback=None,
    ):
        Action.__init__(self, {
            "display": display,
            "useSwitchLeds": use_leds,
            "enableCallback": enable_callback,
        })
        self._state_key = state_key
        self._cc_num = cc_num
        self._text = text
        self._color_on = color_on
        self._color_off = color_off
        self._led_brightness = led_brightness

    def push(self):
        _STATE[self._state_key] = not _STATE[self._state_key]
        _send_cc(self.appl, self._cc_num, 127 if _STATE[self._state_key] else 0)
        _update_status_label()
        _refresh_ui(self.appl, reset=True)

    def update_displays(self):
        if not self.enabled:
            return

        is_on = _STATE[self._state_key]
        color = self._color_on if is_on else self._color_off

        self.switch_color = color
        self.switch_brightness = self._led_brightness

        if self.label:
            self.label.text = f"{self._text}{'+' if is_on else '-'}"  # <= 5 chars
            self.label.back_color = color
        _update_status_label()


class _PageSwapAction(Action):
    def __init__(
        self,
        state_key="qc_page",
        send_qc_swap=True,
        label_prefix="PG",
        split_led=False,
        display=None,
        color=Colors.YELLOW,
        led_brightness=0.25,
        use_leds=True,
        enable_callback=None,
    ):
        Action.__init__(self, {
            "display": display,
            "useSwitchLeds": use_leds,
            "enableCallback": enable_callback,
        })
        self._state_key = state_key
        self._send_qc_swap = send_qc_swap
        self._label_prefix = label_prefix
        self._split_led = split_led
        self._color = color
        self._led_brightness = led_brightness

    def push(self):
        _STATE[self._state_key] = 1 if _STATE[self._state_key] == 2 else 2

        if self._send_qc_swap:
            _send_cc(self.appl, 64, 127 if _STATE[self._state_key] == 2 else 0)

        _update_status_label()
        _refresh_ui(self.appl, reset=True)

    def update_displays(self):
        if not self.enabled:
            return

        page = _STATE[self._state_key]

        if self._split_led:
            if _STATE["gig_view"]:
                left_on = Colors.BLUE
                right_on = Colors.TURQUOISE
            else:
                left_on = Colors.ORANGE
                right_on = Colors.RED

            if page == 1:
                # QP1: left side on
                self.switch_color = [left_on, left_on, Colors.DARK_GRAY]
                color = left_on
            else:
                # QP2: right side on
                self.switch_color = [Colors.DARK_GRAY, right_on, right_on]
                color = right_on
        else:
            if _STATE["gig_view"]:
                color = Colors.BLUE if page == 1 else Colors.TURQUOISE
            else:
                color = Colors.ORANGE if page == 1 else Colors.RED
            self.switch_color = color

        self.switch_brightness = self._led_brightness

        if self.label:
            self.label.text = f"{self._label_prefix}{_STATE[self._state_key]}"  # <= 5 chars
            self.label.back_color = color
        _update_status_label()


class _QCSlotAction(Action):
    def __init__(
        self,
        slot_index,
        opposite,
        page_source="qc",  # "qc" or "midi"
        display=None,
        led_brightness=0.3,
        use_leds=True,
        enable_callback=None,
    ):
        Action.__init__(self, {
            "display": display,
            "useSwitchLeds": use_leds,
            "enableCallback": enable_callback,
        })
        self._slot = slot_index
        self._opposite = opposite
        self._page_source = page_source
        self._led_brightness = led_brightness

    def _effective_opposite(self):
        effective_opposite = self._opposite
        # In Gig View QC control, allow flipping short/long semantics by config.
        if self._page_source == "qc" and _STATE["gig_view"] and GIG_VIEW_STYLE == "short_opposite":
            effective_opposite = not effective_opposite
        return effective_opposite

    def _target_page(self):
        page_key = "midi_page" if self._page_source == "midi" else "qc_page"
        current = _STATE[page_key]
        effective_opposite = self._effective_opposite()

        if effective_opposite:
            return 1 if current == 2 else 2
        return current

    def push(self):
        page = self._target_page()
        cc = _CC_PAGE_1[self._slot] if page == 1 else _CC_PAGE_2[self._slot]
        _send_cc(self.appl, cc, 127)
        _update_status_label()

    def update_displays(self):
        if not self.enabled:
            return

        page = self._target_page()
        effective_opposite = self._effective_opposite()
        slot = _SLOT_NAME[self._slot]
        color = _page_colors()[page][self._slot]
        if effective_opposite:
            color = Colors.GRAY

        self.switch_color = color
        self.switch_brightness = self._led_brightness

        if self.label:
            if _STATE["gig_view"]:
                # GV: no page number, and reflect SC/SO-reversed target immediately.
                self.label.text = f"{slot}{'O' if effective_opposite else 'C'}"
            else:
                # CH: page number is useful here (MIDI page driven).
                self.label.text = f"{slot}{page}{'*' if self._opposite else ''}"  # <= 3 chars
            self.label.back_color = color
        _update_status_label()


class _ModeCycleAction(Action):
    def __init__(self, display=None, use_leds=True, enable_callback=None):
        Action.__init__(self, {
            "display": display,
            "useSwitchLeds": use_leds,
            "enableCallback": enable_callback,
        })
        self._values = [0, 1, 2]
        self._colors = [Colors.YELLOW, Colors.ORANGE, Colors.WHITE]

    def push(self):
        _STATE["mode_slot"] += 1
        if _STATE["mode_slot"] >= len(self._values):
            _STATE["mode_slot"] = 0

        _send_cc(self.appl, 47, self._values[_STATE["mode_slot"]])
        _update_status_label()
        self.update_displays()

    def update_displays(self):
        if not self.enabled:
            return

        idx = _STATE["mode_slot"]
        color = self._colors[idx]

        self.switch_color = color
        self.switch_brightness = 0.28

        if self.label:
            self.label.text = f"M{self._values[idx]}"  # <= 2 chars
            self.label.back_color = color
        _update_status_label()


class _ModeOrStyleDoubleClickAction(Action):
    # Single click: mode cycle (CC47)
    # Double click: Gig style toggle (SC <-> SO)
    def __init__(
        self,
        display=None,
        use_leds=True,
        enable_callback=None,
        double_click_window_ms=700,
    ):
        Action.__init__(self, {
            "display": display,
            "useSwitchLeds": use_leds,
            "enableCallback": enable_callback,
        })
        self._window_ms = double_click_window_ms
        self._pending = False
        self._first_click_ms = 0

    def push(self):
        now_ms = int(monotonic() * 1000)

        if self._pending and (now_ms - self._first_click_ms) <= self._window_ms:
            # Double click: toggle Gig View short/long style.
            self._pending = False
            _toggle_gig_view_style()
            _update_status_label()
            _refresh_ui(self.appl, reset=True)
            return

        # Wait to see if the second click comes in.
        self._pending = True
        self._first_click_ms = now_ms
        self.update_displays()

    def update(self):
        Action.update(self)

        if not self._pending:
            return

        now_ms = int(monotonic() * 1000)
        if (now_ms - self._first_click_ms) <= self._window_ms:
            return

        # Single click confirmed: cycle mode.
        self._pending = False
        _STATE["mode_slot"] += 1
        if _STATE["mode_slot"] >= 3:
            _STATE["mode_slot"] = 0

        _send_cc(self.appl, 47, _STATE["mode_slot"])
        _update_status_label()
        self.update_displays()

    def update_displays(self):
        if not self.enabled:
            return

        idx = _STATE["mode_slot"]
        color = _mode_colors()[idx]
        self.switch_color = color
        self.switch_brightness = 0.28

        if self.label:
            if self._pending:
                self.label.text = "DBL?"
            else:
                self.label.text = _MODE_NAMES[idx]
            self.label.back_color = color


class _PowerSenseAction(Action):
    # Polls power state and voltage monitor.
    # Display format example:
    #   [PW: BAT > 1.01V > 3.03V]
    def __init__(self):
        Action.__init__(self, {})
        self._pin_gp4 = None
        self._pin_gp6 = None
        self._pin_vbus = None
        self._vm = None
        self._last_text = None
        self._poll_interval_ms = 5000
        self._next_poll_ms = 0

    def init(self, appl, switch):
        Action.init(self, appl, switch)
        import board
        import digitalio
        import analogio

        # Open probes independently so one failure does not disable all.
        try:
            self._pin_gp4 = digitalio.DigitalInOut(board.GP4)
            self._pin_gp4.switch_to_input(pull=None)
        except Exception:
            self._pin_gp4 = None

        try:
            if hasattr(board, "GP6"):
                self._pin_gp6 = digitalio.DigitalInOut(board.GP6)
                self._pin_gp6.switch_to_input(pull=None)
        except Exception:
            self._pin_gp6 = None

        try:
            if hasattr(board, "VBUS_SENSE"):
                self._pin_vbus = digitalio.DigitalInOut(board.VBUS_SENSE)
                self._pin_vbus.switch_to_input(pull=None)
        except Exception:
            self._pin_vbus = None

        try:
            if hasattr(board, "VOLTAGE_MONITOR"):
                self._vm = analogio.AnalogIn(board.VOLTAGE_MONITOR)
        except Exception:
            self._vm = None

    def update(self):
        Action.update(self)
        now_ms = int(monotonic() * 1000)
        if now_ms < self._next_poll_ms:
            return
        self._next_poll_ms = now_ms + self._poll_interval_ms

        # Power source: GP4 works reliably for BAT on this board.
        gp4 = None if not self._pin_gp4 else (1 if self._pin_gp4.value else 0)
        gp6 = None if not self._pin_gp6 else (1 if self._pin_gp6.value else 0)
        if gp4 == 1:
            source = "BAT"
            code = 1
        elif gp6 == 1:
            source = "DC"
            code = 2
        else:
            source = "USB/DC"
            code = 0

        if self._vm:
            raw = self._vm.value
            v_est = (raw * 3.3) / 65535.0
            v_sys_est = v_est * 3.0
            text = f"{source} > {v_est:.2f}V > {v_sys_est:.2f}V"
        else:
            text = f"{source} > ?V > ?V"

        if text == self._last_text:
            return

        self._last_text = text
        _STATE["power_code"] = code
        _STATE["power"] = text
        _update_status_label()
        _refresh_ui(self.appl, reset=True)


class _SceneStepAction(Action):
    def __init__(
        self,
        step,
        display=None,
        color=Colors.LIGHT_GREEN,
        led_brightness=0.3,
        use_leds=True,
        enable_callback=None,
    ):
        Action.__init__(self, {
            "display": display,
            "useSwitchLeds": use_leds,
            "enableCallback": enable_callback,
        })
        self._step = step
        self._color = color
        self._led_brightness = led_brightness

    def push(self):
        _STATE["scene_idx"] = (_STATE["scene_idx"] + self._step) % 8
        _send_cc(self.appl, 43, _STATE["scene_idx"])

        # Keep internal QC page tracking aligned with selected scene group.
        _STATE["qc_page"] = 1 if _STATE["scene_idx"] < 4 else 2
        _update_status_label()
        _refresh_ui(self.appl, reset=True)

    def update_displays(self):
        if not self.enabled:
            return

        self.switch_color = self._color
        self.switch_brightness = self._led_brightness

        if self.label:
            self.label.text = f"SC{_STATE['scene_idx']}"  # <= 4 chars
            self.label.back_color = self._color
        _update_status_label()


_tuner_toggle = _ToggleCCAction(
    state_key="tuner",
    cc_num=45,
    display=DISPLAY_HEADER_1,
    text="TUN",
    color_on=Colors.RED,
    color_off=Colors.DARK_PURPLE,
    enable_callback=_GIG_OFF,
)

_gig_toggle = _ToggleCCAction(
    state_key="gig_view",
    cc_num=46,
    display=DISPLAY_FOOTER_3,
    text="GIG",
    color_on=Colors.GREEN,
    color_off=Colors.DARK_GREEN,
)

_mode_or_style = _ModeOrStyleDoubleClickAction(display=DISPLAY_HEADER_3, use_leds=False)
_power_sense = _PowerSenseAction()

Inputs = [
    # key0 (top-left)
    {
        "assignment": PA_MIDICAPTAIN_MINI_SWITCH_1,
        "holdTimeMillis": HOLD_MS,
        "actions": [
            # chain short: internal MIDI page A
            _QCSlotAction(
                slot_index=0,
                opposite=False,
                page_source="midi",
                display=DISPLAY_HEADER_1,
                enable_callback=_GIG_OFF,
            ),
            # gig short: current QC page A
            _QCSlotAction(
                slot_index=0,
                opposite=False,
                page_source="qc",
                display=DISPLAY_HEADER_1,
                enable_callback=_GIG_ON,
            ),
        ],
        "actionsHold": [
            # chain long: tuner
            _tuner_toggle,
            # gig long: opposite page A
            _QCSlotAction(
                slot_index=0,
                opposite=True,
                page_source="qc",
                display=DISPLAY_HEADER_1,
                enable_callback=_GIG_ON,
            ),
        ],
    },

    # key1 (top-middle)
    {
        "assignment": PA_MIDICAPTAIN_MINI_SWITCH_2,
        "holdTimeMillis": HOLD_MS,
        "actions": [
            # chain short: internal MIDI page B
            _QCSlotAction(
                slot_index=1,
                opposite=False,
                page_source="midi",
                display=DISPLAY_HEADER_2,
                enable_callback=_GIG_OFF,
            ),
            # gig short: current QC page B
            _QCSlotAction(
                slot_index=1,
                opposite=False,
                page_source="qc",
                display=DISPLAY_HEADER_2,
                enable_callback=_GIG_ON,
            ),
        ],
        "actionsHold": [
            # chain long: internal MIDI page swap (no CC64)
            _PageSwapAction(
                state_key="midi_page",
                send_qc_swap=False,
                label_prefix="MP",
                display=DISPLAY_HEADER_2,
                enable_callback=_GIG_OFF,
            ),
            # gig long: opposite page B
            _QCSlotAction(
                slot_index=1,
                opposite=True,
                page_source="qc",
                display=DISPLAY_HEADER_2,
                enable_callback=_GIG_ON,
            ),
        ],
    },

    # key2 (top-right)
    {
        "assignment": PA_MIDICAPTAIN_MINI_SWITCH_3,
        "holdTimeMillis": HOLD_MS,
        "actions": [
            # background power-source polling (GP4)
            _power_sense,
            # short: single=mode cycle, double=GV style toggle
            _mode_or_style,
        ],
        "actionsHold": [
            # chain long: actual QC page swap (CC64)
            _PageSwapAction(
                state_key="qc_page",
                send_qc_swap=True,
                label_prefix="QP",
                split_led=True,
                display=DISPLAY_HEADER_3,
                enable_callback=_GIG_OFF,
            ),
            # gig long: actual QC page swap (CC64)
            _PageSwapAction(
                state_key="qc_page",
                send_qc_swap=True,
                label_prefix="QP",
                split_led=True,
                display=DISPLAY_HEADER_3,
                enable_callback=_GIG_ON,
            ),
        ],
    },

    # key3 (bottom-left)
    {
        "assignment": PA_MIDICAPTAIN_MINI_SWITCH_A,
        "holdTimeMillis": HOLD_MS,
        "actions": [
            # chain short: internal MIDI page C
            _QCSlotAction(
                slot_index=2,
                opposite=False,
                page_source="midi",
                display=DISPLAY_FOOTER_1,
                enable_callback=_GIG_OFF,
            ),
            # gig short: current QC page C
            _QCSlotAction(
                slot_index=2,
                opposite=False,
                page_source="qc",
                display=DISPLAY_FOOTER_1,
                enable_callback=_GIG_ON,
            ),
        ],
        "actionsHold": [
            # chain long: scene backward
            _SceneStepAction(
                step=-1,
                display=DISPLAY_FOOTER_1,
                color=Colors.LIGHT_GREEN,
                enable_callback=_GIG_OFF,
            ),
            # gig long: opposite page C
            _QCSlotAction(
                slot_index=2,
                opposite=True,
                page_source="qc",
                display=DISPLAY_FOOTER_1,
                enable_callback=_GIG_ON,
            ),
        ],
    },

    # key4 (bottom-middle)
    {
        "assignment": PA_MIDICAPTAIN_MINI_SWITCH_B,
        "holdTimeMillis": HOLD_MS,
        "actions": [
            # chain short: internal MIDI page D
            _QCSlotAction(
                slot_index=3,
                opposite=False,
                page_source="midi",
                display=DISPLAY_FOOTER_2,
                enable_callback=_GIG_OFF,
            ),
            # gig short: current QC page D
            _QCSlotAction(
                slot_index=3,
                opposite=False,
                page_source="qc",
                display=DISPLAY_FOOTER_2,
                enable_callback=_GIG_ON,
            ),
        ],
        "actionsHold": [
            # chain long: scene forward
            _SceneStepAction(
                step=1,
                display=DISPLAY_FOOTER_2,
                color=Colors.DARK_PURPLE,
                enable_callback=_GIG_OFF,
            ),
            # gig long: opposite page D
            _QCSlotAction(
                slot_index=3,
                opposite=True,
                page_source="qc",
                display=DISPLAY_FOOTER_2,
                enable_callback=_GIG_ON,
            ),
        ],
    },

    # key5 (bottom-right)
    {
        "assignment": PA_MIDICAPTAIN_MINI_SWITCH_C,
        "holdTimeMillis": HOLD_MS,
        "actions": [
            # short: tap tempo in any mode
            CUSTOM_MESSAGE(
                message=[0xB0 + MIDI_CH, 44, 127],
                text="TAP",
                color=Colors.TURQUOISE,
                display=DISPLAY_FOOTER_3,
            ),
        ],
        "actionsHold": [
            # long: gig view mode toggle (enter/exit)
            _gig_toggle,
        ],
    },
]
