"""
Luxor 3 Mod File Parser and Serializer
Decoupled text parsing and export for .lx3trk, .lvl, pathGamePlayData.txt, MapInfo.txt, and Placeables.txt.
Runs on Android without desktop Tkinter dependencies.
"""

import os
import re
from typing import Dict, List, Optional
from luxor_core import TrackManager, Vertex, Reflector, NamedPoint, Placeable


class LuxorModParser:
    @staticmethod
    def parse_lx3trk(lines: List[str], manager: TrackManager):
        manager.verts.clear()
        manager.sections.clear()
        manager.reflectors.clear()
        manager.named_points.clear()
        manager.selected_vertex_index = None

        current_block = None
        for line in lines:
            line = line.strip()
            if not line or line.startswith("//") or line in ("{", "}"):
                continue
            if line.startswith("Verts"):
                current_block = "verts"
                continue
            if line.startswith("Sections"):
                current_block = "sections"
                continue
            if line.startswith("Reflectors"):
                current_block = "reflectors"
                continue
            if line.startswith("NamedPoints"):
                current_block = "namedpoints"
                continue

            if current_block == "verts" and line.startswith("Vert"):
                parts = line.split()
                if len(parts) >= 4:
                    manager.verts.append(Vertex(float(parts[1]), float(parts[2]), float(parts[3])))
            elif current_block == "sections" and line.startswith('"'):
                match = re.match(r'"([^"]+)"\s*\{\s*(.*?)\s*\}', line)
                if match:
                    manager.sections[match.group(1)] = [int(x) for x in match.group(2).split() if x.isdigit()]
            elif current_block == "reflectors" and line.startswith('"'):
                match = re.match(
                    r'"([^"]+)"\s*\{\s*\(\s*([^,]+),\s*([^)]+)\s*\)\s*to\s*\(\s*([^,]+),\s*([^)]+)\s*\)\s*\}',
                    line
                )
                if match:
                    name, x1, y1, x2, y2 = match.groups()
                    manager.reflectors.append(Reflector(float(x1), float(y1), float(x2), float(y2), name))
            elif current_block == "reflectors" and line.startswith("Reflector"):
                parts = line.split()
                if len(parts) >= 5:
                    fallback_name = f"reflect{len(manager.reflectors) + 1:02d}"
                    manager.reflectors.append(Reflector(float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]), fallback_name))
            elif current_block == "namedpoints" and line.startswith('"'):
                match = re.match(r'"([^"]+)"\s*\(\s*([^,]+),\s*([^)]+)\s*\)', line)
                if match:
                    name = match.group(1)
                    manager.named_points[name] = NamedPoint(name, float(match.group(2)), float(match.group(3)))

        # Update dual path state based on imported sections
        side_map = {}
        for name in manager.sections:
            stem, side = manager.section_suffix(name)
            if side:
                side_map.setdefault(stem, set()).add(side)
        manager.dual_paths_enabled = any({"L", "R"}.issubset(sides) for sides in side_map.values())
        manager.dual_path_name_map = {}
        if manager.dual_paths_enabled:
            for name in manager.sections:
                stem, side = manager.section_suffix(name)
                if side:
                    manager.dual_path_name_map[name] = stem

    @staticmethod
    def parse_lvl(lines: List[str], manager: TrackManager):
        content = "".join(lines)
        if "AvailableGamePieceFlavors" in content and "WinTrain" in content:
            manager.play_mode = "nile"
        elif "Ammo" in content and "Train" in content and "WinTrain" not in content:
            manager.play_mode = "puzzle"
        else:
            manager.play_mode = "classic"

    @staticmethod
    def parse_mapinfo(lines: List[str], manager: TrackManager):
        for line in lines:
            match = re.match(r'\s*MapName\s+"(.*?)"', line, flags=re.IGNORECASE)
            if match:
                manager.mapinfo_data["map_name"] = match.group(1)
                break

    @staticmethod
    def parse_gameplay(lines: List[str], manager: TrackManager):
        custom_rules = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "#", ";")):
                continue
            min_match = re.match(r"MinScale\s+(.+)", stripped, flags=re.IGNORECASE)
            max_match = re.match(r"MaxScale\s+(.+)", stripped, flags=re.IGNORECASE)
            if min_match:
                manager.gameplay_data["min_scale"] = min_match.group(1).strip()
            elif max_match:
                manager.gameplay_data["max_scale"] = max_match.group(1).strip()
            else:
                custom_rules.append(line.rstrip())
        manager.gameplay_data["custom_rules"] = "\n".join(custom_rules).strip()

    @staticmethod
    def parse_obj(lines: List[str], manager: TrackManager) -> int:
        added = 0
        for line in lines:
            line = line.strip()
            if line.startswith("v "):
                parts = line.split()
                if len(parts) >= 4:
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    manager.verts.append(Vertex(x, y, z))
                    added += 1
        return added


class LuxorModExporter:
    @staticmethod
    def export_all(manager: TrackManager) -> Dict[str, str]:
        """Generate string outputs for all mod files."""
        return {
            "Track.lx3trk": LuxorModExporter.export_lx3trk(manager),
            "Level.lvl": LuxorModExporter.export_lvl(manager),
            "Placeables.txt": LuxorModExporter.export_placeables(manager),
            "pathGamePlayData.txt": LuxorModExporter.export_gameplay(manager),
            "MapInfo.txt": LuxorModExporter.export_mapinfo(manager),
        }

    @staticmethod
    def export_lx3trk(manager: TrackManager) -> str:
        out = "// ==========================================\n"
        out += f"// Map Name: {manager.map_name}\n"
        out += f"// Modder: {manager.username}\n"
        out += f"// Software: Luxor 3 Mobile Path Creator\n"
        out += "// ==========================================\n\n"

        out += "Verts\n{\n"
        for v in manager.verts:
            out += f"\tVert {v.x:.3f} {v.y:.3f} {v.z:.3f}\n"
        out += "}\n\nSections\n{\n"

        for sec_name, indices in manager.sections.items():
            source_indices = list(range(len(manager.verts))) if sec_name in manager.auto_sections else indices
            valid_indices = [i for i in source_indices if isinstance(i, int) and 0 <= i < len(manager.verts)]
            if valid_indices:
                idx_str = " ".join(str(i) for i in valid_indices)
                out += f'\t"{sec_name}" {{ {idx_str} }}\n'
        out += "}\n\nReflectors\n{\n"

        for idx, r in enumerate(manager.reflectors, start=1):
            reflector_name = r.name if r.name else f"reflect{idx:02d}"
            out += f'\t"{reflector_name}" {{ ( {r.x1:.2f}, {r.y1:.2f} ) to ( {r.x2:.2f}, {r.y2:.2f} ) }}\n'
        out += "}\n\nNamedPoints\n{\n"

        for name, pt in manager.named_points.items():
            out += f'\t"{name}" ( {pt.x:.2f}, {pt.y:.2f} )\n'
        out += "}\n"
        return out

    @staticmethod
    def export_lvl(manager: TrackManager) -> str:
        if manager.play_mode == "nile":
            out = f'MapPath "{manager.nile_data["map_path"]}"\n'
            out += f'LevelDisplayName "{manager.nile_data["display_name"]}"\n'
            out += f'BonusTime {manager.nile_data["bonus_time"]}\n\n'
            out += f'LevelMusic "{manager.nile_data["music"]}"\n\n'

            out += "AvailableGamePieceFlavors\n{\n"
            for f, active in manager.nile_data["flavors"].items():
                if active:
                    out += f"\t{f}\n"
            out += "}\n\n"

            out += "WinTrain\n{\n"
            out += f'\tTrackSection "{manager.nile_data["win_train"]["section"]}"\n'
            out += f'\tSpeed {manager.nile_data["win_train"]["speed"]}\n'
            out += "\tFlavors\n\t{\n"
            for f in manager.nile_data["win_train"]["flavors"]:
                out += f"\t\t{f}\n"
            out += "\t}\n}\n\n"

            for t in manager.nile_data["train_tracks"]:
                out += "TrainTrack\n{\n"
                out += f'\tTrackSection "{t["section"]}"\n'
                out += f'\tSpeed {t["speed"]}\n'
                out += f'\tNumSpheresToSpawnWith {t["spheres"]}\n'
                out += f'\tColorSpawnStreak {t["streak"]}\n'
                out += f'\tLengthWhenNextTrainSpawns {t["length"]}\n'
                out += "}\n\n"

            out += '#include "powerups.txt"\n#include "treasure_3.txt"\n'
            return out

        elif manager.play_mode == "puzzle":
            out = f'MapPath "{manager.lvl_data["map_path"]}"\nLevelDisplayName "{manager.lvl_data["display_name"]}"\nLevelMusic "MenuMusic"\n\n'
            out += "Ammo\n{\n"
            for a in manager.puzzle_data["ammo"]:
                out += f"\t{a}\n"
            out += "}\n\n"

            for t in manager.puzzle_data["trains"]:
                out += "Train\n{\n"
                out += f'\tTrackSegment "{t["segment"]}"\n'
                out += f'\tTrackSegmentOffset {t["offset"]}\n'
                out += "\tFlavorList\n\t{\n"
                for f in t["flavors"]:
                    out += f"\t\t{f}\n"
                out += "\t}\n}\n\n"
            out += '#include "treasure.txt"\n'
            return out

        else:  # Classic
            out = f'MapPath "{manager.lvl_data["map_path"]}"\nLevelDisplayName "{manager.lvl_data["display_name"]}"\nLevelMusic "LevelMusicClassic"\n'
            out += f'TrainConstructionData\n{{\n\tNumSpheresToSpawnWith\t{manager.lvl_data["spheres"]}\n\tColorSpawnStreak\t{manager.lvl_data["streak"]}\n}}\n'
            out += f'NumTrainsToSpawn\t{manager.lvl_data["trains"]}\nMinSecondsBeforeNextTrainCanSpawn {manager.lvl_data["seconds"]}\n'

            start_name = str(manager.lvl_data.get("start_sec", "initial01")).strip() or "initial01"
            if not manager.dual_paths_enabled:
                start_sections = [start_name]
            else:
                stem, _side = manager.section_suffix(start_name)
                if stem == "initial":
                    stem = "initial01"
                start_sections = [f"{stem}_L", f"{stem}_R"]

            out += "StartingTrackSectionSpawnOrder\n{\n"
            for s in start_sections:
                out += f"\t{s}\n"
            out += "}\n"
            out += '#include "flavors_classic.txt"\n#include "treasure_freeplay.txt"\n'
            return out

    @staticmethod
    def export_gameplay(manager: TrackManager) -> str:
        raw_rules = manager.gameplay_data.get("custom_rules", "")
        if manager.dual_paths_enabled:
            targets = {}
            for section_name, original_name in manager.dual_path_name_map.items():
                stem, side = manager.section_suffix(section_name)
                if side:
                    targets.setdefault(original_name, stem)
                    targets.setdefault(stem, stem)

            expanded = []
            for raw_line in raw_rules.splitlines():
                parts = raw_line.split()
                if len(parts) >= 2 and parts[1] in targets:
                    stem = targets[parts[1]]
                    expanded.append(" ".join([parts[0], f"{stem}_L", *parts[2:]]))
                    expanded.append(" ".join([parts[0], f"{stem}_R", *parts[2:]]))
                else:
                    expanded.append(raw_line)
            rules_text = "\n".join(expanded)
        else:
            rules_text = raw_rules

        return (
            "// Please see http://wiki.ritual.com/index.php/Luxor3_PathGamePlayData_File for how this file works.\n\n"
            f"MinScale {manager.gameplay_data['min_scale']}\n"
            f"MaxScale {manager.gameplay_data['max_scale']}\n\n"
            f"{rules_text}\n"
        )

    @staticmethod
    def export_mapinfo(manager: TrackManager) -> str:
        return (
            "// please see http://wiki.ritual.com/index.php/Luxor3_MapInfoFile for how this file works\n\n"
            f'MapName "{manager.mapinfo_data["map_name"]}"\n'
        )

    @staticmethod
    def export_placeables(manager: TrackManager) -> str:
        out = ""
        if manager.canopic_jar_points:
            out += "CanopicJarSpawnPoints\n{\n"
            for jar in manager.canopic_jar_points:
                out += f'\tpos "{jar}"\n'
            out += "}\n\n"

        for p in manager.placeables:
            out += "Placeable\n{\n"
            out += f'\tdrawLayer "{p.draw_layer}"\n'
            out += f'\tname "{p.name}"\n'
            out += f'\teffect "{p.effect}"\n'
            out += f'\tpos {p.pos}\n'
            out += f'\ttrackSectionLink "{p.track_section_link}"\n'
            out += "}\n\n"

        return out if out.strip() else "// No custom placeables defined\n"
