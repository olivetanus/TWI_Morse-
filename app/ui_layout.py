# app/ui_layout.py
import os
from PyQt5.QtWidgets import QWidget, QLabel, QLineEdit, QPlainTextEdit
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from app.widgets.image_buttons import ImageButton, ImageToggleButton, RotatingKnob

# Root del progetto = .../TWI_Morse
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR   = os.path.join(PROJECT_ROOT, "assets", "images")
CHASSIS      = os.path.join(ASSETS_DIR, "chassis.png")
SMETER_LIGHT = os.path.join(ASSETS_DIR, "smeter_light.png")

COORDS = dict(
    waterfall     =(  76, 101, 806, 370),
    smeter        =( 926, 104, 279, 160),
    server_box    =(1240, 230, 205,  39),
    btn_connect   =(1466, 228,  81,  43),
    channel_box   =( 927, 340, 279,  67),
    btn_web       =(1256, 349,  81,  42),
    btn_server    =(1256, 420,  81,  43),
    decoder_toggle=( 249, 492,  81,  43),
    decoder_box   =(  77, 547, 806,  57),
    knob_rf       =( 926, 416, 280, 280),
    knob_vol      =(1236, 520, 120, 120),
    btn_vertical  =(1373, 348,  81,  43),
    btn_paddle    =(1373, 415,  81,  43),
    btn_spacebar  =(1373, 482,  81,  43),
)

def build_ui(parent: QWidget):
    """Crea i widget principali e restituisce (widgets, coords)."""
    widgets = {}

    # Sfondo chassis
    bg = QLabel(parent); bg.setGeometry(0,0,1600,700)
    if os.path.exists(CHASSIS):
        pm = QPixmap(CHASSIS)
        bg.setPixmap(pm)
        bg.setScaledContents(True)
    else:
        bg.setStyleSheet("background:#111;")
    widgets["bg"] = bg

    # Server
    widgets["server_input"] = QLineEdit("http://5.250.190.24", parent)
    widgets["server_input"].setGeometry(*COORDS["server_box"])
    widgets["server_input"].setStyleSheet("background:#fff; color:#111; border-radius:6px; padding:6px;")

    # Connect
    widgets["btn_connect"] = ImageToggleButton("btn_connect_off.png","btn_connect_on.png",
                                               size=(COORDS["btn_connect"][2], COORDS["btn_connect"][3]), parent=parent)
    widgets["btn_connect"].setGeometry(*COORDS["btn_connect"])

    # Channel + knobs
    from PyQt5.QtGui import QIntValidator
    widgets["channel_edit"] = QLineEdit("000133", parent)
    widgets["channel_edit"].setGeometry(*COORDS["channel_box"])
    widgets["channel_edit"].setAlignment(Qt.AlignCenter)
    widgets["channel_edit"].setStyleSheet("background:#fff; color:#111; border-radius:8px; font: bold 42px 'Consolas';")
    widgets["channel_edit"].setValidator(QIntValidator(0, 999999, parent))

    widgets["knob_rf"]  = RotatingKnob("knob_rf.png",  size=(COORDS["knob_rf"][2],  COORDS["knob_rf"][3]),  minv=0, maxv=999999, val=133, parent=parent)
    widgets["knob_rf"].setGeometry(*COORDS["knob_rf"])
    widgets["knob_vol"] = RotatingKnob("knob_vol.png", size=(COORDS["knob_vol"][2], COORDS["knob_vol"][3]), minv=0, maxv=100, val=40, parent=parent)
    widgets["knob_vol"].setGeometry(*COORDS["knob_vol"])

    # Pulsanti info
    widgets["btn_site"]   = ImageButton("site.png",   size=(COORDS["btn_web"][2], COORDS["btn_web"][3]), parent=parent)
    widgets["btn_site"].setGeometry(*COORDS["btn_web"])
    widgets["btn_server"] = ImageButton("server.png", size=(COORDS["btn_server"][2], COORDS["btn_server"][3]), parent=parent)
    widgets["btn_server"].setGeometry(*COORDS["btn_server"])

    # Decoder
    widgets["btn_decoder"] = ImageToggleButton("btn_decoder_off.png","btn_decoder_on.png",
                                               size=(COORDS["decoder_toggle"][2], COORDS["decoder_toggle"][3]), parent=parent)
    widgets["btn_decoder"].setGeometry(*COORDS["decoder_toggle"])

    widgets["decoder_box"] = QPlainTextEdit(parent)
    widgets["decoder_box"].setGeometry(*COORDS["decoder_box"]); widgets["decoder_box"].setReadOnly(True)
    widgets["decoder_box"].setStyleSheet("background:#fff; color:#111; border-radius:6px; padding:6px;")

    # Key (grafica)
    widgets["btn_vertical"] = ImageToggleButton("btn_vertical_off.png","btn_vertical_on.png",
                                                size=(COORDS["btn_vertical"][2], COORDS["btn_vertical"][3]), parent=parent)
    widgets["btn_vertical"].setGeometry(*COORDS["btn_vertical"])
    widgets["btn_paddle"]   = ImageToggleButton("btn_paddle_off.png","btn_paddle_on.png",
                                                size=(COORDS["btn_paddle"][2], COORDS["btn_paddle"][3]), parent=parent)
    widgets["btn_paddle"].setGeometry(*COORDS["btn_paddle"])
    widgets["btn_spacebar"] = ImageToggleButton("btn_spacebar_off.png","btn_spacebar_on.png",
                                                size=(COORDS["btn_spacebar"][2], COORDS["btn_spacebar"][3]), parent=parent)
    widgets["btn_spacebar"].setGeometry(*COORDS["btn_spacebar"])

    # S-meter overlay (luce): sta SOPRA alla lancetta
    widgets["smeter_light"] = QLabel(parent)
    widgets["smeter_light"].setGeometry(*COORDS["smeter"])
    widgets["smeter_light"].setScaledContents(True)
    if os.path.exists(SMETER_LIGHT):
        pm = QPixmap(SMETER_LIGHT)
        widgets["smeter_light"].setPixmap(pm)
    widgets["smeter_light"].hide()

    return widgets, COORDS
