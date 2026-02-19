from micropython import const
from pyswitch.ui.ui import DisplayElement, DisplayBounds
from pyswitch.ui.elements import DisplayLabel
from pyswitch.colors import DEFAULT_LABEL_COLOR
from pyswitch.clients.local.callbacks.splashes import SplashesCallback

_ACTION_LABEL_LAYOUT = {
    "font": "/fonts/H20.pcf",
    "backColor": DEFAULT_LABEL_COLOR,
    "stroke": 1
}

_DISPLAY_WIDTH = const(240)
_DISPLAY_HEIGHT = const(240)
_SLOT_WIDTH = const(80)
_SLOT_HEIGHT = const(40)
_FOOTER_Y = const(200)
_PAGE_Y = const(180)

DISPLAY_HEADER_1 = DisplayLabel(
    layout = _ACTION_LABEL_LAYOUT,
    bounds = DisplayBounds(0, 0, _SLOT_WIDTH, _SLOT_HEIGHT)
)
DISPLAY_HEADER_2 = DisplayLabel(
    layout = _ACTION_LABEL_LAYOUT,
    bounds = DisplayBounds(_SLOT_WIDTH, 0, _SLOT_WIDTH, _SLOT_HEIGHT)
)
DISPLAY_HEADER_3 = DisplayLabel(
    layout = _ACTION_LABEL_LAYOUT,
    bounds = DisplayBounds(_SLOT_WIDTH * 2, 0, _SLOT_WIDTH, _SLOT_HEIGHT)
)

DISPLAY_FOOTER_1 = DisplayLabel(
    layout = _ACTION_LABEL_LAYOUT,
    bounds = DisplayBounds(0, _FOOTER_Y, _SLOT_WIDTH, _SLOT_HEIGHT)
)
DISPLAY_FOOTER_2 = DisplayLabel(
    layout = _ACTION_LABEL_LAYOUT,
    bounds = DisplayBounds(_SLOT_WIDTH, _FOOTER_Y, _SLOT_WIDTH, _SLOT_HEIGHT)
)
DISPLAY_FOOTER_3 = DisplayLabel(
    layout = _ACTION_LABEL_LAYOUT,
    bounds = DisplayBounds(_SLOT_WIDTH * 2, _FOOTER_Y, _SLOT_WIDTH, _SLOT_HEIGHT)
)

DISPLAY_PAGE = DisplayLabel(
    layout = {
        "font": "/fonts/A12.pcf",
        "backColor": (0, 0, 0),
        "text": "QC MINI - PAGE"
    },
    bounds = DisplayBounds(0, _PAGE_Y, _DISPLAY_WIDTH, 20)
)

DISPLAY_MAIN = DisplayLabel(
    bounds = DisplayBounds(0, 40, _DISPLAY_WIDTH, 140),
    layout = {
        "font": "/fonts/PTSans-NarrowBold-40.pcf",
        "lineSpacing": 0.8,
        "maxTextWidth": 220,
        "text": "CH M0\nMP2 QP2"
    }
)

_SPLASH_ROOT = DisplayElement(
    bounds = DisplayBounds(0, 0, _DISPLAY_WIDTH, _DISPLAY_HEIGHT),
    children = [
        DISPLAY_HEADER_1,
        DISPLAY_HEADER_2,
        DISPLAY_HEADER_3,
        DISPLAY_FOOTER_1,
        DISPLAY_FOOTER_2,
        DISPLAY_FOOTER_3,
        DISPLAY_PAGE,
        DISPLAY_MAIN
    ]
)

Splashes = SplashesCallback(_SPLASH_ROOT)
