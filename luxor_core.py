"""
Luxor 3 Mobile Core Engine (Zero UI Dependencies)
Decoupled geometric calculations, track state management, and Chaikin curve smoothing.
Compatible with Python on Android (Kivy, Chaquopy, BeeWare, Termux).
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set


@dataclass
class Vertex:
    x: float
    y: float
    z: float = 0.02

    def to_game_coords(self) -> Tuple[float, float, float]:
        """Luxor 3 stores Y inverted relative to screen canvas pixels."""
        return (self.x, self.y, self.z)

    def to_list(self) -> List[float]:
        return [self.x, self.y, self.z]


@dataclass
class Reflector:
    x1: float
    y1: float
    x2: float
    y2: float
    name: str = "reflect01"


@dataclass
class NamedPoint:
    name: str
    x: float
    y: float


@dataclass
class Placeable:
    name: str
    draw_layer: str
    effect: str
    pos: str
    track_section_link: str


class TrackManager:
    """Core state container for Luxor 3 track paths, sections, and game configurations."""

    def __init__(self, username: str = "Modder", map_name: str = "Map 01", canvas_size: Tuple[int, int] = (800, 600)):
        self.username = username
        self.map_name = map_name
        self.canvas_size = list(canvas_size)

        self.verts: List[Vertex] = []
        self.sections: Dict[str, List[int]] = {
            "initial": [],
            "slowdown01": [],
            "occlude01": [],
            "slowdown02": [],
            "restrict": [],
            "pyramid_gate": [],
            "pyramid": []
        }
        self.auto_sections: Set[str] = set()
        self.named_points: Dict[str, NamedPoint] = {}
        self.reflectors: List[Reflector] = []
        self.canopic_jar_points: List[str] = []
        self.placeables: List[Placeable] = []

        self.dual_paths_enabled = False
        self.dual_path_name_map: Dict[str, str] = {}

        # Play Modes: "classic", "puzzle", "nile"
        self.play_mode = "classic"

        # Classic Mode Configuration
        self.lvl_data = {
            "map_path": "data/maps/template/",
            "display_name": "#custom",
            "spheres": "50",
            "streak": "0.4",
            "trains": "5",
            "seconds": "50.0",
            "start_sec": "initial01"
        }

        # Puzzle Mode Configuration
        self.puzzle_data = {
            "ammo": ["Red", "Green", "Blue", "Yellow"],
            "trains": [
                {"segment": "initial", "offset": "80.0", "flavors": ["Red", "Green", "Green", "Green", "Red", "Red"]}
            ]
        }

        # Crossing the Nile Configuration
        self.nile_data = {
            "map_path": "data/maps/CrossingTheNile/",
            "display_name": "#crossingcustom01",
            "bonus_time": "60",
            "music": "LevelMusicNile",
            "flavors": {
                "Red": True, "Orange": False, "Yellow": True, "Green": False,
                "Teal": False, "Turquoise": False, "Blue": True, "Purple": False,
                "White": False, "Black": False
            },
            "win_train": {
                "section": "targetline",
                "speed": "20",
                "flavors": ["Red", "Yellow", "Blue", "Yellow", "Red"]
            },
            "train_tracks": [
                {"section": "line01_R", "speed": "30", "spheres": "10", "streak": "0.5", "length": "160"},
                {"section": "line03_R", "speed": "25", "spheres": "15", "streak": "0.5", "length": "192"},
                {"section": "line05_R", "speed": "20", "spheres": "20", "streak": "0.5", "length": "256"}
            ]
        }

        self.gameplay_data = {
            "min_scale": "0.75",
            "max_scale": "0.90",
            "custom_rules": "EndSpeed occlude01 16\nDanger pyramid_gate\nOccluded pyramid\nUnshootable pyramid"
        }

        self.mapinfo_data = {
            "map_name": "#custom"
        }

        self.selected_vertex_index: Optional[int] = None
        self.current_z: float = 0.02

    def add_vertex(self, x: float, game_y: float, z: Optional[float] = None) -> int:
        if z is None:
            z = self.current_z
        z = max(0.0, min(5.0, float(z)))
        v = Vertex(x=float(x), y=float(game_y), z=z)
        self.verts.append(v)
        self.selected_vertex_index = len(self.verts) - 1
        return self.selected_vertex_index

    def update_vertex_position(self, index: int, x: float, game_y: float) -> bool:
        if 0 <= index < len(self.verts):
            self.verts[index].x = float(x)
            self.verts[index].y = float(game_y)
            return True
        return False

    def set_vertex_z(self, index: int, z: float) -> bool:
        if 0 <= index < len(self.verts):
            self.verts[index].z = max(0.0, min(5.0, float(z)))
            return True
        return False

    def apply_z_to_all(self, z: float):
        z = max(0.0, min(5.0, float(z)))
        self.current_z = z
        for v in self.verts:
            v.z = z

    def delete_last_vertex(self) -> Optional[Vertex]:
        if self.verts:
            popped = self.verts.pop()
            if self.selected_vertex_index is not None and self.selected_vertex_index >= len(self.verts):
                self.selected_vertex_index = len(self.verts) - 1 if self.verts else None
            return popped
        return None

    def clear_all(self):
        self.verts.clear()
        self.reflectors.clear()
        self.named_points.clear()
        self.canopic_jar_points.clear()
        self.placeables.clear()
        self.selected_vertex_index = None

    def add_reflector(self, x1: float, y1: float, x2: float, y2: float, name: str = "") -> Reflector:
        if not name:
            name = f"reflect{len(self.reflectors) + 1:02d}"
        clean_name = name.replace('"', '').replace('\n', '').strip()
        reflector = Reflector(x1=x1, y1=y1, x2=x2, y2=y2, name=clean_name)
        self.reflectors.append(reflector)
        return reflector

    def add_named_point(self, name: str, x: float, y: float) -> NamedPoint:
        clean_name = name.replace('"', '').strip()
        pt = NamedPoint(name=clean_name, x=x, y=y)
        self.named_points[clean_name] = pt
        return pt

    # --- GEOMETRIC ALGORITHMS ---
    def smooth_curves(self) -> int:
        """Chaikin subdivision algorithm to round corners while preserving Z interpolation."""
        if len(self.verts) < 3:
            return len(self.verts)

        smoothed: List[Vertex] = [Vertex(self.verts[0].x, self.verts[0].y, self.verts[0].z)]
        for first, second in zip(self.verts, self.verts[1:]):
            for ratio in (0.25, 0.75):
                smoothed.append(Vertex(
                    x=first.x * (1.0 - ratio) + second.x * ratio,
                    y=first.y * (1.0 - ratio) + second.y * ratio,
                    z=first.z * (1.0 - ratio) + second.z * ratio,
                ))
        smoothed.append(Vertex(self.verts[-1].x, self.verts[-1].y, self.verts[-1].z))
        self.verts = smoothed
        self.selected_vertex_index = None
        return len(self.verts)

    def stroke_draw_step(self, last_pt: Tuple[float, float], curr_pt: Tuple[float, float], spacing: float = 10.0) -> List[int]:
        """Used for touch/mouse drag sketching with regular interpolation."""
        lx, ly = last_pt
        cx, cy = curr_pt
        dist = math.hypot(cx - lx, cy - ly)
        added_indices = []
        if dist >= spacing:
            steps = max(1, int(dist // spacing))
            for step in range(1, steps + 1):
                ratio = min(1.0, step * spacing / dist)
                px = lx + (cx - lx) * ratio
                py = ly + (cy - ly) * ratio
                idx = self.add_vertex(px, -py, self.current_z)
                added_indices.append(idx)
        return added_indices

    # --- DUAL PATH TOPOLOGY ---
    @staticmethod
    def section_suffix(name: str) -> Tuple[str, Optional[str]]:
        if name.endswith("_L"):
            return name[:-2], "L"
        if name.endswith("_R"):
            return name[:-2], "R"
        return name, None

    def enable_dual_paths(self):
        if self.dual_paths_enabled:
            return

        groups: Dict[str, Dict] = {}
        for name, indices in self.sections.items():
            stem, side = self.section_suffix(name)
            if side is None and name == "initial" and "initial01" not in self.sections:
                stem = "initial01"
            group = groups.setdefault(stem, {"base_name": name if side is None else stem, "base": None, "L": None, "R": None})
            if side is None:
                group["base"] = list(indices)
                group["base_name"] = name
            else:
                group[side] = list(indices)

        expanded: Dict[str, List[int]] = {}
        auto: Set[str] = set()
        name_map: Dict[str, str] = {}

        for stem, group in groups.items():
            original_name = group["base_name"]
            fallback = group["base"]
            left_indices = group["L"] if group["L"] is not None else (fallback or group["R"] or [])
            right_indices = group["R"] if group["R"] is not None else (fallback or group["L"] or [])
            left_name, right_name = f"{stem}_L", f"{stem}_R"
            expanded[left_name] = list(left_indices)
            expanded[right_name] = list(right_indices)
            name_map[left_name] = original_name
            name_map[right_name] = original_name
            if (original_name in self.auto_sections or stem in self.auto_sections or
                    left_name in self.auto_sections or right_name in self.auto_sections):
                auto.update((left_name, right_name))

        self.sections = expanded
        self.auto_sections = auto
        self.dual_path_name_map = name_map
        self.dual_paths_enabled = True

    def disable_dual_paths(self):
        if not self.dual_paths_enabled:
            return

        collapsed: Dict[str, Dict] = {}
        auto: Set[str] = set()
        for name, indices in self.sections.items():
            stem, side = self.section_suffix(name)
            original_name = self.dual_path_name_map.get(name, stem if side else name)
            if original_name not in collapsed:
                collapsed[original_name] = {"L": None, "R": None, "plain": None, "auto": False}
            group = collapsed[original_name]
            if side in ("L", "R"):
                group[side] = list(indices)
            else:
                group["plain"] = list(indices)
            if name in self.auto_sections:
                group["auto"] = True

        restored: Dict[str, List[int]] = {}
        for original_name, group in collapsed.items():
            chosen = group["L"] if group["L"] is not None else group["R"]
            if chosen is None:
                chosen = group["plain"] or []
            restored[original_name] = list(chosen)
            if group["auto"]:
                auto.add(original_name)

        self.sections = restored
        self.auto_sections = auto
        self.dual_path_name_map = {}
        self.dual_paths_enabled = False
