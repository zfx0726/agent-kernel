from __future__ import annotations

import json
import re
from typing import Any


UNSUPPORTED_PATTERNS = [
    (re.compile(r"(^|\s)[|>][-+]?\s*$"), "multiline scalars are not supported"),
    (re.compile(r"(^|\s)[&*][A-Za-z0-9_-]+"), "anchors and aliases are not supported"),
]


def _enforce_subset(text: str) -> None:
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        if "	" in raw_line:
            raise ValueError(f"Unsupported YAML subset at line {lineno}: tabs are not supported")
        for pattern, message in UNSUPPORTED_PATTERNS:
            if pattern.search(raw_line):
                raise ValueError(f"Unsupported YAML subset at line {lineno}: {message}")


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    if value in {"[]", "[ ]"}:
        return []
    if value in {"{}", "{ }"}:
        return {}
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value in {"true", "false"}:
        return value == "true"
    if value.isdigit():
        return int(value)
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    if value.startswith("{") and value.endswith("}"):
        inner = value[1:-1].strip()
        if not inner:
            return {}
        result = {}
        for part in inner.split(","):
            key, raw = part.split(":", 1)
            result[key.strip()] = _parse_scalar(raw.strip())
        return result
    return value


def _next_nonempty(lines: list[str], index: int) -> int | None:
    for i in range(index, len(lines)):
        if lines[i].strip() and not lines[i].lstrip().startswith("#"):
            return i
    return None


def _parse_block(lines: list[str], start: int, indent: int) -> tuple[Any, int]:
    index = _next_nonempty(lines, start)
    if index is None:
        return {}, len(lines)
    line = lines[index]
    current_indent = len(line) - len(line.lstrip(" "))
    if current_indent < indent:
        return {}, index
    if line.lstrip().startswith("- "):
        items = []
        while index < len(lines):
            line = lines[index]
            if not line.strip() or line.lstrip().startswith("#"):
                index += 1
                continue
            line_indent = len(line) - len(line.lstrip(" "))
            if line_indent != indent or not line.lstrip().startswith("- "):
                break
            payload = line.strip()[2:]
            if not payload:
                value, index = _parse_block(lines, index + 1, indent + 2)
                items.append(value)
                continue
            if ":" in payload and not payload.startswith(("\"", "'")):
                key, raw = payload.split(":", 1)
                item = {key.strip(): _parse_scalar(raw.strip()) if raw.strip() else None}
                index += 1
                while index < len(lines):
                    nested_index = _next_nonempty(lines, index)
                    if nested_index is None:
                        index = len(lines)
                        break
                    nested = lines[nested_index]
                    nested_indent = len(nested) - len(nested.lstrip(" "))
                    if nested_indent <= indent:
                        index = nested_index
                        break
                    if nested_indent == indent + 2 and ":" in nested.strip():
                        nkey, nraw = nested.strip().split(":", 1)
                        if nraw.strip():
                            item[nkey.strip()] = _parse_scalar(nraw.strip())
                            index = nested_index + 1
                        else:
                            value, index = _parse_block(lines, nested_index + 1, indent + 4)
                            item[nkey.strip()] = value
                    else:
                        break
                items.append(item)
                continue
            items.append(_parse_scalar(payload))
            index += 1
        return items, index
    mapping = {}
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        line_indent = len(line) - len(line.lstrip(" "))
        if line_indent < indent:
            break
        if line_indent > indent:
            raise ValueError(f"Unexpected indentation: {line}")
        stripped = line.strip()
        if ":" not in stripped:
            raise ValueError(f"Invalid line: {line}")
        key, raw = stripped.split(":", 1)
        if raw.strip():
            mapping[key.strip()] = _parse_scalar(raw.strip())
            index += 1
        else:
            value, index = _parse_block(lines, index + 1, indent + 2)
            mapping[key.strip()] = value
    return mapping, index


def safe_load(text: str) -> Any:
    _enforce_subset(text)
    lines = text.splitlines()
    value, _ = _parse_block(lines, 0, 0)
    return value


def _dump_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value == []:
        return "[]"
    if value == {}:
        return "{}"
    return json.dumps(str(value))


def _dump_block(value: Any, indent: int) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)) and item not in ({}, []):
                lines.append(f"{prefix}{key}:")
                lines.extend(_dump_block(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_dump_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                first = True
                for key, val in item.items():
                    if first:
                        if isinstance(val, (dict, list)) and val not in ({}, []):
                            lines.append(f"{prefix}- {key}:")
                            lines.extend(_dump_block(val, indent + 4))
                        else:
                            lines.append(f"{prefix}- {key}: {_dump_scalar(val)}")
                        first = False
                    else:
                        if isinstance(val, (dict, list)) and val not in ({}, []):
                            lines.append(f"{prefix}  {key}:")
                            lines.extend(_dump_block(val, indent + 4))
                        else:
                            lines.append(f"{prefix}  {key}: {_dump_scalar(val)}")
            elif isinstance(item, list):
                lines.append(f"{prefix}-")
                lines.extend(_dump_block(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_dump_scalar(item)}")
        return lines
    return [f"{prefix}{_dump_scalar(value)}"]


def safe_dump(value: Any, sort_keys: bool = False) -> str:
    if sort_keys and isinstance(value, dict):
        value = {key: value[key] for key in sorted(value)}
    return "\n".join(_dump_block(value, 0)) + "\n"
