# -*- coding: utf-8 -*-
"""Программная правка графов ComfyUI (формат user/default/workflows/*.json).

Когда в воркфлоу 200+ нод, править его мышью нерентабельно: одно неверное
перетаскивание рвёт связь, а найти разрыв глазами потом тяжело. Здесь граф
правится как данные — операциями, которые сохраняют целостность связей.

Формат, с которым работаем:
    nodes: [{id, type, title, pos, mode, inputs:[{name, link}],
             outputs:[{name, links:[]}], widgets_values:[...]}, ...]
    links: [[link_id, from_node, from_slot, to_node, to_slot, type], ...]

Граф в ComfyUI хранит связь в трёх местах сразу (в links, в inputs.link
приёмника и в outputs.links источника). Любая правка должна трогать все три,
иначе фронтенд покажет «висящий» провод.

CLI:
    python patch_workflow.py graph.json --list
    python patch_workflow.py graph.json --swap-model old.safetensors new.safetensors
    python patch_workflow.py graph.json --bypass "Апскейл"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

MODE_ACTIVE = 0
MODE_BYPASS = 4  # в UI это «Обход»: нода пропускает сигнал мимо себя


class Workflow:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.data = data
        self.nodes = data["nodes"]
        self.links = data["links"]

    # ---------- поиск ----------

    def by_id(self, node_id: int) -> dict:
        return next(n for n in self.nodes if n["id"] == node_id)

    def find(self, *, type: str | None = None, title: str | None = None) -> list[dict]:
        """Ноды по типу и/или подстроке заголовка (заголовок часто единственный
        способ отличить пять одинаковых лоадеров друг от друга)."""
        out = []
        for n in self.nodes:
            if type is not None and n.get("type") != type:
                continue
            if title is not None and title.lower() not in str(n.get("title", "")).lower():
                continue
            out.append(n)
        return out

    def link_of(self, node: dict, input_name: str):
        """Связь, входящая в именованный вход ноды."""
        inp = next((i for i in node.get("inputs", []) if i["name"] == input_name), None)
        if inp is None or inp.get("link") is None:
            return None
        return next((l for l in self.links if l[0] == inp["link"]), None)

    # ---------- правка связей ----------

    def _next_link_id(self) -> int:
        self.data["last_link_id"] = self.data.get("last_link_id", 0) + 1
        return self.data["last_link_id"]

    def _drop_links(self, link_ids: set[int]) -> None:
        """Удаляет связи и подчищает все три места, где они упомянуты."""
        if not link_ids:
            return
        self.links[:] = [l for l in self.links if l[0] not in link_ids]
        for n in self.nodes:
            for i in n.get("inputs", []) or []:
                if i.get("link") in link_ids:
                    i["link"] = None
            for o in n.get("outputs", []) or []:
                if o.get("links"):
                    o["links"] = [x for x in o["links"] if x not in link_ids]

    def connect(self, src: dict, src_slot: int, dst: dict, dst_slot: int, type_: str = "*") -> int:
        """Соединяет выход src со входом dst, снимая прежнюю связь с этого входа."""
        old = dst["inputs"][dst_slot].get("link")
        if old is not None:
            self._drop_links({old})
        lid = self._next_link_id()
        self.links.append([lid, src["id"], src_slot, dst["id"], dst_slot, type_])
        dst["inputs"][dst_slot]["link"] = lid
        outs = src["outputs"][src_slot]
        outs["links"] = (outs.get("links") or []) + [lid]
        return lid

    def detach_input(self, node: dict, input_name: str) -> bool:
        """Отвязывает вход от провода, чтобы нода слушала собственный виджет.

        Нужно, когда размер кадра «втихую» диктуется подключённой нодой
        (например, латент берёт ширину/высоту от ресайза референса),
        и из-за этого настройки в полях игнорируются.
        """
        inp = next((i for i in node.get("inputs", []) if i["name"] == input_name), None)
        if inp is None or inp.get("link") is None:
            return False
        self._drop_links({inp["link"]})
        return True

    def remove_passthrough(self, node: dict, in_name: str = None, out_slot: int = 0) -> bool:
        """Убирает ноду из цепи, соединяя её источник напрямую с потребителями.

        Для нод-«посредников» (превью с выбором, промежуточные ресайзы):
        удалить кнопкой нельзя — разорвётся цепь, нужно переподключение.
        """
        inputs = node.get("inputs") or []
        inp = (next((i for i in inputs if i["name"] == in_name), None)
               if in_name else (inputs[0] if inputs else None))
        if inp is None or inp.get("link") is None:
            return False
        src_link = next(l for l in self.links if l[0] == inp["link"])
        src_node, src_slot = self.by_id(src_link[1]), src_link[2]

        consumers = []
        for lid in (node["outputs"][out_slot].get("links") or []):
            l = next((x for x in self.links if x[0] == lid), None)
            if l:
                consumers.append((self.by_id(l[3]), l[4], l[5]))

        self._drop_links({inp["link"], *(node["outputs"][out_slot].get("links") or [])})
        self.nodes[:] = [n for n in self.nodes if n["id"] != node["id"]]
        for dst, dst_slot, type_ in consumers:
            self.connect(src_node, src_slot, dst, dst_slot, type_)
        return True

    # ---------- массовые операции ----------

    def swap_widget_value(self, old: str, new: str, *, contains: bool = False) -> int:
        """Подмена значения виджета во всём графе — пути моделей при переносе
        воркфлоу между машинами, где файлы разложены иначе."""
        hits = 0
        for n in self.nodes:
            wv = n.get("widgets_values")
            if not isinstance(wv, list):
                continue
            for i, v in enumerate(wv):
                if not isinstance(v, str):
                    continue
                if (old in v) if contains else (v == old):
                    wv[i] = v.replace(old, new) if contains else new
                    hits += 1
        return hits

    def set_mode(self, nodes: list[dict], mode: int) -> int:
        """Обход вместо удаления: цепь остаётся целой, нода просто не считается."""
        for n in nodes:
            n["mode"] = mode
        return len(nodes)

    def save(self, path: str | Path | None = None) -> Path:
        out = Path(path) if path else self.path
        out.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Правка графа ComfyUI без открытия UI")
    ap.add_argument("workflow")
    ap.add_argument("--list", action="store_true", help="перечислить ноды")
    ap.add_argument("--swap-model", nargs=2, metavar=("OLD", "NEW"))
    ap.add_argument("--bypass", metavar="TITLE", help="перевести ноды в режим обхода")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    wf = Workflow(args.workflow)

    if args.list:
        for n in wf.nodes:
            print(f"{n['id']:>5}  {n.get('type','?'):<32} {n.get('title','')}")
        return

    changed = False
    if args.swap_model:
        hits = wf.swap_widget_value(*args.swap_model, contains=True)
        print(f"подменено значений: {hits}")
        changed = hits > 0
    if args.bypass:
        hits = wf.set_mode(wf.find(title=args.bypass), MODE_BYPASS)
        print(f"переведено в обход: {hits}")
        changed = changed or hits > 0

    if changed:
        print("сохранено:", wf.save(args.out))


if __name__ == "__main__":
    main()
