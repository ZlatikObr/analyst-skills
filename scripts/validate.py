#!/usr/bin/env python3
"""Проверка структуры репозитория навыков.

Запуск: python3 scripts/validate.py
Возвращает код 1, если найдены ошибки.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
BLOCKED_EXT = {".xlsx", ".xls", ".xlsm", ".csv", ".docx", ".pptx"}

errors = []
warnings = []


def read_frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end]
    data = {}
    key = None
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            key = m.group(1)
            data[key] = m.group(2).strip().strip('"').strip("'")
        elif key and line.strip():
            data[key] = (data[key] + " " + line.strip()).strip()
    return data


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        errors.append(f"{path}: некорректный JSON, {exc}")
        return None


market_path = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
if not os.path.exists(market_path):
    errors.append("нет файла .claude-plugin/marketplace.json")
    market = None
else:
    market = load_json(market_path)

if market:
    for field in ("name", "owner", "plugins"):
        if field not in market:
            errors.append(f"marketplace.json: нет обязательного поля {field}")
    if "name" in market and not NAME_RE.match(market["name"]):
        errors.append(f"marketplace.json: name '{market['name']}' не в формате kebab-case")

    for entry in market.get("plugins", []):
        pname = entry.get("name", "")
        src = entry.get("source", "")
        if not NAME_RE.match(pname):
            errors.append(f"marketplace.json: name плагина '{pname}' не в формате kebab-case")
        if not isinstance(src, str):
            continue
        pdir = os.path.normpath(os.path.join(ROOT, src))
        if not os.path.isdir(pdir):
            errors.append(f"marketplace.json: плагин '{pname}' указывает на несуществующую папку {src}")
            continue
        manifest = os.path.join(pdir, ".claude-plugin", "plugin.json")
        if not os.path.exists(manifest):
            errors.append(f"{src}: нет .claude-plugin/plugin.json")
        else:
            data = load_json(manifest)
            if data and data.get("name") != pname:
                errors.append(
                    f"{src}: name в plugin.json '{data.get('name')}' не совпадает с '{pname}' в marketplace.json"
                )

plugins_dir = os.path.join(ROOT, "plugins")
if os.path.isdir(plugins_dir):
    declared = {p.get("name") for p in (market or {}).get("plugins", [])}
    for pname in sorted(os.listdir(plugins_dir)):
        pdir = os.path.join(plugins_dir, pname)
        if not os.path.isdir(pdir):
            continue
        if pname not in declared:
            warnings.append(f"плагин '{pname}' лежит в plugins/, но не объявлен в marketplace.json")
        skills_dir = os.path.join(pdir, "skills")
        if not os.path.isdir(skills_dir):
            continue
        for sname in sorted(os.listdir(skills_dir)):
            sdir = os.path.join(skills_dir, sname)
            if not os.path.isdir(sdir):
                continue
            skill_md = os.path.join(sdir, "SKILL.md")
            rel = f"plugins/{pname}/skills/{sname}"
            if not os.path.exists(skill_md):
                errors.append(f"{rel}: нет SKILL.md")
                continue
            if not NAME_RE.match(sname):
                errors.append(f"{rel}: имя папки не в формате kebab-case")
            fm = read_frontmatter(skill_md)
            if fm is None:
                errors.append(f"{rel}/SKILL.md: нет YAML frontmatter")
                continue
            if "description" not in fm or not fm["description"]:
                errors.append(f"{rel}/SKILL.md: нет поля description")
            if "name" in fm and fm["name"] != sname:
                errors.append(
                    f"{rel}/SKILL.md: name '{fm['name']}' не совпадает с именем папки '{sname}'"
                )
            lines = sum(1 for _ in open(skill_md, encoding="utf-8"))
            if lines > 500:
                warnings.append(f"{rel}/SKILL.md: {lines} строк, рекомендуется вынести часть в reference.md")

for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__"}]
    for fname in files:
        ext = os.path.splitext(fname)[1].lower()
        if ext in BLOCKED_EXT:
            rel = os.path.relpath(os.path.join(base, fname), ROOT)
            errors.append(f"{rel}: рабочие файлы с данными в репозитории навыков не хранятся")

for w in warnings:
    print(f"ПРЕДУПРЕЖДЕНИЕ  {w}")
for e in errors:
    print(f"ОШИБКА         {e}")

if errors:
    print(f"\nПроверка не пройдена: {len(errors)} ошибок, {len(warnings)} предупреждений.")
    sys.exit(1)

print(f"Проверка пройдена. Предупреждений: {len(warnings)}.")
