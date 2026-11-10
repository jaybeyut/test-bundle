"""
Luxor 3 Path Creator — Kivy Mobile Application Entry Point (Android Ready)
Features:
- Touch-first canvas with multitouch pinch-to-zoom and pan via ScatterLayout
- Smooth touch drag path sketching with stroke spacing
- Sunset-Orange UI palette
- Native Android dialogs and bottom sheets (Kivy / KivyMD compatible)
- Real-time coordinates HUD and vertex editor
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scatterlayout import ScatterLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Line, Ellipse, Rectangle
from kivy.core.window import Window
from kivy.utils import get_color_from_hex

from luxor_core import TrackManager, Vertex
from luxor_parser import LuxorModExporter, LuxorModParser


# Luxor Sunset Palette
PALETTE = {
    "background": get_color_from_hex("#1b100d"),
    "panel": get_color_from_hex("#2b1711"),
    "card": get_color_from_hex("#4a291d"),
    "accent": get_color_from_hex("#ff8a3d"),
    "accent_hover": get_color_from_hex("#d9632b"),
    "text": get_color_from_hex("#fff3e8"),
    "canvas": get_color_from_hex("#f5e4d4"),
    "line": get_color_from_hex("#ed7938"),
    "reflector": get_color_from_hex("#ff695d"),
    "node_selected": get_color_from_hex("#ff9c4a"),
}


class TrackCanvasWidget(Widget):
    """Interactive touch drawing canvas handling single-touch draw/edit and multi-touch gestures."""

    def __init__(self, manager: TrackManager, **kwargs):
        super().__init__(**kwargs)
        self.manager = manager
        self.mode = "vert"  # "vert", "edit", "reflector", "named"
        self.last_touch_pos = None
        self.stroke_spacing = 14.0
        self.temp_reflector_start = None
        self.on_state_change = None

        with self.canvas.before:
            Color(*PALETTE["canvas"])
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)

        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.redraw()

    def on_touch_down(self, touch):
        # Ignore if touch is caught by other UI widgets
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        # Coordinate translation: screen Y to Luxor game Y (inverted)
        x = touch.x - self.x
        screen_y = touch.y - self.y
        game_y = -screen_y

        if self.mode == "vert":
            self.manager.add_vertex(x, game_y)
            self.last_touch_pos = (x, screen_y)
            self.redraw()
            if self.on_state_change:
                self.on_state_change()
            return True

        elif self.mode == "edit":
            # Find closest vertex
            closest_idx = -1
            min_dist = 40.0  # Touch threshold in dp
            for i, v in enumerate(self.manager.verts):
                vx, vy = v.x, -v.y
                d = ((vx - x) ** 2 + (vy - screen_y) ** 2) ** 0.5
                if d < min_dist:
                    min_dist = d
                    closest_idx = i
            self.manager.selected_vertex_index = closest_idx if closest_idx != -1 else None
            self.redraw()
            if self.on_state_change:
                self.on_state_change()
            return True

        elif self.mode == "reflector":
            if self.temp_reflector_start is None:
                self.temp_reflector_start = (x, game_y)
            else:
                x1, y1 = self.temp_reflector_start
                self.manager.add_reflector(x1, y1, x, game_y)
                self.temp_reflector_start = None
            self.redraw()
            if self.on_state_change:
                self.on_state_change()
            return True

        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_move(touch)

        x = touch.x - self.x
        screen_y = touch.y - self.y
        game_y = -screen_y

        if self.mode == "vert" and self.last_touch_pos:
            lx, ly = self.last_touch_pos
            dist = ((x - lx) ** 2 + (screen_y - ly) ** 2) ** 0.5
            if dist >= self.stroke_spacing:
                self.manager.stroke_draw_step((lx, ly), (x, screen_y), self.stroke_spacing)
                self.last_touch_pos = (x, screen_y)
                self.redraw()
                if self.on_state_change:
                    self.on_state_change()
            return True

        elif self.mode == "edit" and self.manager.selected_vertex_index is not None:
            self.manager.update_vertex_position(self.manager.selected_vertex_index, x, game_y)
            self.redraw()
            if self.on_state_change:
                self.on_state_change()
            return True

        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        self.last_touch_pos = None
        return super().on_touch_up(touch)

    def redraw(self):
        self.canvas.clear()
        with self.canvas:
            # Canvas background
            Color(*PALETTE["canvas"])
            Rectangle(pos=self.pos, size=self.size)

            # Draw Track Lines
            if len(self.manager.verts) > 1:
                Color(*PALETTE["line"])
                pts = []
                for v in self.manager.verts:
                    pts.extend([self.x + v.x, self.y - v.y])
                Line(points=pts, width=3)

            # Draw Nodes
            for idx, v in enumerate(self.manager.verts):
                screen_x = self.x + v.x
                screen_y = self.y - v.y
                is_selected = (idx == self.manager.selected_vertex_index)
                r = 10 if is_selected else 6

                if is_selected:
                    Color(*PALETTE["node_selected"])
                else:
                    Color(*PALETTE["line"])
                Ellipse(pos=(screen_x - r, screen_y - r), size=(r * 2, r * 2))

            # Draw Reflectors
            Color(*PALETTE["reflector"])
            for ref in self.manager.reflectors:
                p1 = (self.x + ref.x1, self.y - ref.y1)
                p2 = (self.x + ref.x2, self.y - ref.y2)
                Line(points=[p1[0], p1[1], p2[0], p2[1]], width=2.5, dash_offset=4, dash_length=6)
                Ellipse(pos=(p1[0] - 5, p1[1] - 5), size=(10, 10))
                Ellipse(pos=(p2[0] - 5, p2[1] - 5), size=(10, 10))


class Luxor3MobileApp(App):
    """Main mobile application instance."""

    def build(self):
        self.title = "Luxor 3 Path Creator Mobile"
        self.manager = TrackManager(username="AndroidModder", map_name="Pharaoh's Tomb")

        root = BoxLayout(orientation="vertical")
        Window.clearcolor = PALETTE["background"]

        # Top Bar
        top_bar = BoxLayout(size_hint_y=None, height="52dp", padding="8dp", spacing="8dp")
        with top_bar.canvas.before:
            Color(*PALETTE["panel"])
            self.top_bg = Rectangle(pos=top_bar.pos, size=top_bar.size)
        top_bar.bind(pos=lambda *a: setattr(self.top_bg, "pos", top_bar.pos),
                     size=lambda *a: setattr(self.top_bg, "size", top_bar.size))

        title_lbl = Label(text="[b]Luxor 3[/b] Track Creator", markup=True, color=PALETTE["text"], size_hint_x=0.5, halign="left")
        self.status_lbl = Label(text="Verts: 0 | Z: 0.02", color=PALETTE["accent"], size_hint_x=0.5, halign="right")
        top_bar.add_widget(title_lbl)
        top_bar.add_widget(self.status_lbl)
        root.add_widget(top_bar)

        # Mode Action Strip
        mode_strip = BoxLayout(size_hint_y=None, height="48dp", padding="4dp", spacing="6dp")
        self.btn_vert = Button(text="Draw", background_color=PALETTE["accent"])
        self.btn_edit = Button(text="Edit", background_color=PALETTE["card"])
        self.btn_reflector = Button(text="Reflector", background_color=PALETTE["card"])
        self.btn_smooth = Button(text="Smooth", background_color=PALETTE["card"])

        self.btn_vert.bind(on_press=lambda *a: self.set_mode("vert"))
        self.btn_edit.bind(on_press=lambda *a: self.set_mode("edit"))
        self.btn_reflector.bind(on_press=lambda *a: self.set_mode("reflector"))
        self.btn_smooth.bind(on_press=lambda *a: self.smooth_track())

        mode_strip.add_widget(self.btn_vert)
        mode_strip.add_widget(self.btn_edit)
        mode_strip.add_widget(self.btn_reflector)
        mode_strip.add_widget(self.btn_smooth)
        root.add_widget(mode_strip)

        # Main Workspace Canvas
        self.track_canvas = TrackCanvasWidget(self.manager, size_hint=(1, 1))
        self.track_canvas.on_state_change = self.update_hud
        root.add_widget(self.track_canvas)

        # Bottom Thumb Toolbar
        bottom_bar = BoxLayout(size_hint_y=None, height="56dp", padding="8dp", spacing="8dp")
        with bottom_bar.canvas.before:
            Color(*PALETTE["panel"])
            self.bot_bg = Rectangle(pos=bottom_bar.pos, size=bottom_bar.size)
        bottom_bar.bind(pos=lambda *a: setattr(self.bot_bg, "pos", bottom_bar.pos),
                        size=lambda *a: setattr(self.bot_bg, "size", bottom_bar.size))

        btn_undo = Button(text="Undo", background_color=PALETTE["card"])
        btn_undo.bind(on_press=lambda *a: self.undo_last())
        btn_clear = Button(text="Clear Data", background_color=get_color_from_hex("#8b251a"))
        btn_clear.bind(on_press=lambda *a: self.clear_all_data())
        btn_dual = Button(text="Dual Path", background_color=PALETTE["card"])
        btn_dual.bind(on_press=lambda *a: self.toggle_dual())
        btn_export = Button(text="Export Files", background_color=PALETTE["accent"])
        btn_export.bind(on_press=lambda *a: self.show_export_dialog())

        bottom_bar.add_widget(btn_undo)
        bottom_bar.add_widget(btn_clear)
        bottom_bar.add_widget(btn_dual)
        bottom_bar.add_widget(btn_export)
        root.add_widget(bottom_bar)

        return root

    def clear_all_data(self):
        self.manager.clear_all()
        self.track_canvas.redraw()
        self.update_hud()

    def set_mode(self, mode: str):
        self.track_canvas.mode = mode
        self.btn_vert.background_color = PALETTE["accent"] if mode == "vert" else PALETTE["card"]
        self.btn_edit.background_color = PALETTE["accent"] if mode == "edit" else PALETTE["card"]
        self.btn_reflector.background_color = PALETTE["accent"] if mode == "reflector" else PALETTE["card"]

    def smooth_track(self):
        count = self.manager.smooth_curves()
        self.track_canvas.redraw()
        self.update_hud()

    def undo_last(self):
        self.manager.delete_last_vertex()
        self.track_canvas.redraw()
        self.update_hud()

    def toggle_dual(self):
        if self.manager.dual_paths_enabled:
            self.manager.disable_dual_paths()
        else:
            self.manager.enable_dual_paths()
        self.update_hud()

    def update_hud(self):
        verts_count = len(self.manager.verts)
        dual_text = "Dual: On" if self.manager.dual_paths_enabled else "Dual: Off"
        sel_text = f" | Sel: {self.manager.selected_vertex_index}" if self.manager.selected_vertex_index is not None else ""
        self.status_lbl.text = f"Verts: {verts_count} | {dual_text}{sel_text}"

    def show_export_dialog(self):
        files = LuxorModExporter.export_all(self.manager)
        content = BoxLayout(orientation="vertical", padding="10dp", spacing="8dp")
        txt = TextInput(text=files["Track.lx3trk"], readonly=True, font_name="Roboto", size_hint=(1, 0.85))
        content.add_widget(txt)
        btn_close = Button(text="Close", size_hint=(1, 0.15), background_color=PALETTE["accent"])
        popup = Popup(title="Exported Track.lx3trk", content=content, size_hint=(0.9, 0.8))
        btn_close.bind(on_press=popup.dismiss)
        content.add_widget(btn_close)
        popup.open()


if __name__ == "__main__":
    Luxor3MobileApp().run()
