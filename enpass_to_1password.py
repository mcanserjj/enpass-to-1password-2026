#!/usr/bin/env python3
"""Convert an Enpass JSON export into 1Password-compatible CSV files."""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


LOGIN_HEADERS = [
    "Title",
    "Website",
    "Username",
    "Password",
    "One-time password",
    "Favorite",
    "Archived",
    "Tags",
    "Notes",
]
CREDIT_CARD_HEADERS = [
    "Title",
    "Card Number",
    "Expiry Date",
    "Security Code",
    "Cardholder",
    "Favorite",
    "Archived",
    "Tags",
    "Notes",
]
SECURE_NOTE_HEADERS = ["Title", "Notes", "Tags"]

LOGIN_CATEGORIES = {"login", "password", "uncategorized"}
CARD_CATEGORIES = {"creditcard", "credit_card", "credit card"}
class ConversionError(ValueError):
    """Raised when the input is not a supported Enpass JSON export."""


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def truthy_flag(value: Any) -> str:
    return "true" if value in (1, True, "1", "true", "True") else "false"


def field_value(field: dict[str, Any]) -> str:
    return text(field.get("value")).strip()


def first_field(
    fields: list[dict[str, Any]],
    *,
    types: Iterable[str] = (),
    labels: Iterable[str] = (),
    excluded: set[int] | None = None,
) -> tuple[str, int | None]:
    wanted_types = {item.casefold() for item in types}
    wanted_labels = {item.casefold() for item in labels}
    excluded = excluded or set()
    for index, field in enumerate(fields):
        if index in excluded or field.get("deleted") in (1, True, "1"):
            continue
        value = field_value(field)
        if not value:
            continue
        field_type = text(field.get("type")).strip().casefold()
        label = text(field.get("label")).strip().casefold()
        if field_type in wanted_types or label in wanted_labels:
            return value, index
    return "", None


def safe_component(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", value).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned[:80] or fallback)


def load_export(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ConversionError(f"Input file not found: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConversionError(f"Input is not valid UTF-8 Enpass JSON: {exc}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ConversionError("Expected a JSON object containing an 'items' array.")
    if not all(isinstance(item, dict) for item in data["items"]):
        raise ConversionError("Every entry in 'items' must be a JSON object.")
    return data


def folder_map(data: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for folder in data.get("folders", []):
        if isinstance(folder, dict) and folder.get("uuid") and folder.get("title"):
            result[text(folder["uuid"])] = text(folder["title"])
    return result


def item_tags(item: dict[str, Any], folders: dict[str, str]) -> list[str]:
    tags: list[str] = []
    for folder_id in item.get("folders", []):
        name = folders.get(text(folder_id))
        if name and name not in tags:
            tags.append(name)
    raw_tags = item.get("tags", [])
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    if isinstance(raw_tags, list):
        for value in raw_tags:
            value = text(value).strip()
            if value and value not in tags:
                tags.append(value)
    return tags


def extract_attachments(
    item: dict[str, Any],
    output_dir: Path,
    source_index: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    references: list[str] = []
    events: list[dict[str, Any]] = []
    attachments = item.get("attachments", [])
    if not isinstance(attachments, list):
        return references, [{"source_index": source_index, "status": "invalid-list"}]

    for attachment_index, attachment in enumerate(attachments, 1):
        if not isinstance(attachment, dict):
            events.append({"source_index": source_index, "status": "invalid-entry"})
            continue
        original_name = text(attachment.get("name")).strip() or f"attachment-{attachment_index}.bin"
        encoded = text(attachment.get("data")).strip()
        event = {
            "source_index": source_index,
            "attachment_index": attachment_index,
            "name": original_name,
        }
        if not encoded:
            event["status"] = "missing-data"
            events.append(event)
            continue
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            event["status"] = "invalid-base64"
            events.append(event)
            continue

        item_name = safe_component(text(item.get("title")), f"item-{source_index}")
        file_name = safe_component(original_name, f"attachment-{attachment_index}.bin")
        attachment_dir = output_dir / "attachments"
        attachment_dir.mkdir(parents=True, exist_ok=True)
        destination = attachment_dir / f"{source_index:04d}_{item_name}_{attachment_index}_{file_name}"
        destination.write_bytes(payload)
        relative = destination.relative_to(output_dir).as_posix()
        references.append(relative)
        event.update({"status": "extracted", "path": relative, "bytes": len(payload)})
        events.append(event)
    return references, events


def build_notes(
    item: dict[str, Any],
    fields: list[dict[str, Any]],
    consumed: set[int],
    tags: list[str],
    attachment_paths: list[str],
) -> str:
    blocks: list[str] = []
    original_note = text(item.get("note")).strip()
    if original_note:
        blocks.append(original_note)

    metadata = [f"Enpass category: {text(item.get('category')).strip() or 'unknown'}"]
    if tags:
        metadata.append(f"Enpass folders/tags: {', '.join(tags)}")
    for key in ("favorite", "archived", "trashed", "created_at", "updated_at"):
        if key in item:
            metadata.append(f"Enpass {key}: {text(item[key])}")
    blocks.append("[Migration metadata]\n" + "\n".join(metadata))

    remaining: list[str] = []
    section = ""
    for index, field in enumerate(fields):
        if field.get("deleted") in (1, True, "1"):
            continue
        field_type = text(field.get("type")).strip()
        label = text(field.get("label")).strip()
        value = field_value(field)
        if field_type.casefold() == "section":
            section = label or value
            if section:
                remaining.append(f"-- {section} --")
            continue
        if index in consumed or not value or field_type.casefold() == ".android#":
            continue
        display_label = label or field_type or f"Field {index + 1}"
        sensitive = " [sensitive]" if field.get("sensitive") in (1, True, "1") else ""
        remaining.append(f"{display_label}{sensitive}: {value}")
    if remaining:
        blocks.append("[Additional Enpass fields]\n" + "\n".join(remaining))

    histories: list[str] = []
    for index, field in enumerate(fields, 1):
        label = text(field.get("label")).strip() or f"Field {index}"
        for key, value in field.items():
            if "history" in text(key).casefold() and value not in (None, "", []):
                histories.append(f"{label} {key}: {text(value)}")
    for key, value in item.items():
        if "history" in text(key).casefold() and value not in (None, "", []):
            histories.append(f"Item {key}: {text(value)}")
    if histories:
        blocks.append("[Password history; retained as text]\n" + "\n".join(histories))
    if attachment_paths:
        blocks.append(
            "[Attachments extracted; CSV cannot import files]\n" + "\n".join(attachment_paths)
        )
    return "\n\n".join(blocks)


def as_fields(item: dict[str, Any]) -> list[dict[str, Any]]:
    fields = item.get("fields", [])
    return [field for field in fields if isinstance(field, dict)] if isinstance(fields, list) else []


def convert_item(
    item: dict[str, Any],
    folders: dict[str, str],
    output_dir: Path,
    source_index: int,
) -> tuple[str, dict[str, str], dict[str, Any]]:
    category = text(item.get("category")).strip().casefold()
    fields = as_fields(item)
    tags = item_tags(item, folders)
    attachment_paths, attachment_events = extract_attachments(item, output_dir, source_index)
    common_report: dict[str, Any] = {
        "source_index": source_index,
        "source_category": category or "unknown",
        "attachments": attachment_events,
    }
    title = text(item.get("title")).strip() or f"Untitled Enpass item {source_index}"
    favorite = truthy_flag(item.get("favorite"))
    archived = truthy_flag(item.get("archived"))
    tag_value = ", ".join(tags)

    if category in CARD_CATEGORIES:
        consumed: set[int] = set()
        number, number_index = first_field(fields, types={"ccnumber"})
        expiry, expiry_index = first_field(
            fields,
            types={"month"},
            labels={"expiry", "expiration", "expiry date", "expiration date", "valid thru"},
        )
        if number_index is not None:
            consumed.add(number_index)
        if expiry_index is not None:
            consumed.add(expiry_index)
        security_code, code_index = first_field(
            fields,
            types={"pin"},
            labels={"cvv", "cvc", "security code", "verification code"},
            excluded=consumed,
        )
        cardholder, holder_index = first_field(
            fields,
            labels={"cardholder", "card holder", "name on card"},
            excluded=consumed,
        )
        for index in (code_index, holder_index):
            if index is not None:
                consumed.add(index)
        if number and expiry:
            notes = build_notes(item, fields, consumed, tags, attachment_paths)
            return "credit_cards", {
                "Title": title,
                "Card Number": number,
                "Expiry Date": expiry,
                "Security Code": security_code,
                "Cardholder": cardholder,
                "Favorite": favorite,
                "Archived": archived,
                "Tags": tag_value,
                "Notes": notes,
            }, common_report
        common_report["downgrade_reason"] = "credit card missing number or expiry date"

    elif category in LOGIN_CATEGORIES:
        consumed = set()
        website, website_index = first_field(fields, types={"url"})
        username, username_index = first_field(fields, types={"username", "email"})
        password, password_index = first_field(fields, types={"password"})
        otp, otp_index = first_field(fields, types={"totp", "otp"})
        for index in (website_index, username_index, password_index, otp_index):
            if index is not None:
                consumed.add(index)
        if website and username and password:
            notes = build_notes(item, fields, consumed, tags, attachment_paths)
            return "logins", {
                "Title": title,
                "Website": website,
                "Username": username,
                "Password": password,
                "One-time password": otp,
                "Favorite": favorite,
                "Archived": archived,
                "Tags": tag_value,
                "Notes": notes,
            }, common_report
        common_report["downgrade_reason"] = "login missing website, username, or password"
    else:
        common_report["downgrade_reason"] = "category is not natively supported by 1Password CSV"

    notes = build_notes(item, fields, set(), tags, attachment_paths)
    return "secure_notes", {"Title": title, "Notes": notes, "Tags": tag_value}, common_report


def write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def ensure_output_directory(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise ConversionError(f"Output directory is not empty: {path} (choose a new empty directory)")
    path.mkdir(parents=True, exist_ok=True)


def convert(input_path: Path, output_dir: Path) -> dict[str, Any]:
    data = load_export(input_path)
    ensure_output_directory(output_dir)
    folders = folder_map(data)
    rows: dict[str, list[dict[str, str]]] = {
        "logins": [],
        "credit_cards": [],
        "secure_notes": [],
    }
    item_reports: list[dict[str, Any]] = []
    categories: Counter[str] = Counter()

    for source_index, item in enumerate(data["items"], 1):
        categories[text(item.get("category")).strip().casefold() or "unknown"] += 1
        destination, row, report = convert_item(item, folders, output_dir, source_index)
        rows[destination].append(row)
        report["destination"] = destination
        item_reports.append(report)

    write_csv(output_dir / "logins.csv", LOGIN_HEADERS, rows["logins"])
    write_csv(output_dir / "credit_cards.csv", CREDIT_CARD_HEADERS, rows["credit_cards"])
    write_csv(output_dir / "secure_notes.csv", SECURE_NOTE_HEADERS, rows["secure_notes"])

    report = {
        "format": "enpass-to-1password-2026-report-v1",
        "source_items": len(data["items"]),
        "source_categories": dict(sorted(categories.items())),
        "output_items": {name: len(value) for name, value in rows.items()},
        "downgraded_to_secure_note": sum(
            1 for item in item_reports if "downgrade_reason" in item
        ),
        "attachments_extracted": sum(
            1
            for item in item_reports
            for event in item["attachments"]
            if event.get("status") == "extracted"
        ),
        "items": item_reports,
    }
    with (output_dir / "conversion-report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert an Enpass JSON export into 1Password web-import CSV files."
    )
    parser.add_argument("input", type=Path, help="Enpass JSON export")
    parser.add_argument("output", type=Path, help="Output directory")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = convert(args.input, args.output)
    except (ConversionError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Converted {report['source_items']} Enpass items into:")
    for name, count in report["output_items"].items():
        print(f"  {name}.csv: {count}")
    print(f"Downgraded to secure notes: {report['downgraded_to_secure_note']}")
    print(f"Attachments extracted: {report['attachments_extracted']}")
    print(f"Report: {args.output / 'conversion-report.json'}")
    print("WARNING: The output contains unencrypted secrets. Import, verify, then delete it securely.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

