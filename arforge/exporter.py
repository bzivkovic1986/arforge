from __future__ import annotations

from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .model import Project, Swc

def _env(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(enabled_extensions=("xml", "arxml", "j2")),
        trim_blocks=True,
        lstrip_blocks=True,
    )

def _split_interfaces(project: Project):
    sr = [i for i in project.interfaces if i.type == "senderReceiver"]
    cs = [i for i in project.interfaces if i.type == "clientServer"]
    sr = sorted(sr, key=lambda x: x.name)
    cs = sorted(cs, key=lambda x: x.name)
    return sr, cs

def render_shared(project: Project, template_dir: Path, template_name: str = "shared_42.arxml.j2") -> str:
    env = _env(template_dir)
    tpl = env.get_template(template_name)
    datatypes = sorted(project.datatypes, key=lambda x: x.name)
    sr, cs = _split_interfaces(project)
    return tpl.render(root_pkg=project.rootPackage, datatypes=datatypes, sr_interfaces=sr, cs_interfaces=cs)

def render_swc(project: Project, swc: Swc, template_dir: Path, template_name: str = "swc_42.arxml.j2") -> str:
    env = _env(template_dir)
    tpl = env.get_template(template_name)
    return tpl.render(root_pkg=project.rootPackage, swc=swc)

def render_system(project: Project, template_dir: Path, template_name: str = "system_42.arxml.j2") -> str:
    env = _env(template_dir)
    tpl = env.get_template(template_name)
    connections = [{
        "from_swc": c.from_swc,
        "from_port": c.from_port,
        "to_swc": c.to_swc,
        "to_port": c.to_port,
        "dataElement": c.dataElement,
        "operation": c.operation,
    } for c in project.connections]
    return tpl.render(root_pkg=project.rootPackage, connections=connections)

def write_outputs(project: Project, template_dir: Path, out: Path, split_by_swc: bool) -> List[Path]:
    written: List[Path] = []
    if not split_by_swc:
        env = _env(template_dir)
        tpl = env.get_template("all_42.arxml.j2")
        datatypes = sorted(project.datatypes, key=lambda x: x.name)
        swcs = sorted(project.swcs, key=lambda x: x.name)
        sr, cs = _split_interfaces(project)
        connections = [{
            "from_swc": c.from_swc,
            "from_port": c.from_port,
            "to_swc": c.to_swc,
            "to_port": c.to_port,
            "dataElement": c.dataElement,
            "operation": c.operation,
        } for c in project.connections]
        xml = tpl.render(root_pkg=project.rootPackage, datatypes=datatypes, sr_interfaces=sr, cs_interfaces=cs, swcs=swcs, connections=connections)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(xml, encoding="utf-8")
        written.append(out)
        return written

    out.mkdir(parents=True, exist_ok=True)

    shared_path = out / "shared.arxml"
    shared_path.write_text(render_shared(project, template_dir), encoding="utf-8")
    written.append(shared_path)

    for swc in sorted(project.swcs, key=lambda x: x.name):
        p = out / f"{swc.name}.arxml"
        p.write_text(render_swc(project, swc=swc, template_dir=template_dir), encoding="utf-8")
        written.append(p)

    system_path = out / "system.arxml"
    system_path.write_text(render_system(project, template_dir), encoding="utf-8")
    written.append(system_path)

    return written
