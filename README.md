# Enpass to 1Password 2026

[简体中文说明](README.zh-CN.md)

A dependency-free Python 3 command-line converter for moving an Enpass JSON
export into CSV files accepted by 1Password's web importer.

The converter is intentionally conservative: it does not invent missing values
or silently discard unsupported item types. Enpass data that cannot be represented
as a native 1Password CSV login or credit card becomes a secure note with its
original category and fields preserved.

## What it creates

- `logins.csv` for items that contain the username, password, and website fields
  currently required by 1Password.
- `credit_cards.csv` for cards that contain both a card number and expiry date.
- `secure_notes.csv` for every other Enpass category and incomplete login/card.
- `attachments/` with files extracted from Enpass JSON. CSV cannot import them;
  attach them manually after import.
- `conversion-report.json` with counts, downgrade reasons, and attachment status.

Every source item is written to exactly one CSV. CSV files use UTF-8 with BOM and
RFC 4180-compatible quoting, including commas, quotes, and multiline values.

## Requirements

- Python 3.10 or newer
- An Enpass JSON export

No third-party Python packages are required.

## Usage

```shell
python enpass_to_1password.py Enpass.json output
```

If the output directory is non-empty, the converter stops to avoid overwriting
or mixing plaintext migration data. Choose a new empty directory.

Run the tests:

```shell
python -m unittest discover -s tests -v
```

## Import into 1Password

1. Sign in to 1Password.com in a browser.
2. Choose your name, then **Import data** > **CSV File**.
3. Import `logins.csv`; choose **Login** and map its columns.
4. Import `credit_cards.csv`; choose **Credit Card** and map its columns.
5. Import `secure_notes.csv`; choose **Secure Note** and map its columns.
6. Compare source and destination counts with `conversion-report.json`.
7. Verify important passwords, cards, and every TOTP code against a real login.
8. Add extracted attachments manually where required.
9. Delete the unencrypted JSON, CSV, report, and extracted attachments after
   verification, then empty the recycle bin or trash.

The importer interface allows columns to be labeled during import. If your
current 1Password account does not offer a native label for a column such as
tags, favorite status, archived status, or TOTP, map it to a new/custom label.
The same value is retained in the migration metadata where applicable.

## Mapping policy

1Password's current generic CSV importer documents only Login, Credit Card, and
Secure Note as item types. It requires username/password/website for Login,
card number/expiry for Credit Card, and title for Secure Note. This project uses
those conditions exactly.

Enpass' public help documents how to create a JSON export and that archived or
trashed items can be included, but it does not publish a complete JSON schema.
Field keys such as `items`, `category`, `fields`, `type`, and `value` are therefore
compatibility behavior inferred from real-world open-source converters. Unknown
field types are preserved as labeled text instead of being dropped.

See [docs/FORMAT_AND_SECURITY.md](docs/FORMAT_AND_SECURITY.md) for the evidence,
limitations, and security model.

## Project lineage

Inspired by the 2019 MIT-licensed
[`heroheman/enpass-to-1password`](https://github.com/heroheman/enpass-to-1password)
converter and informed by the 2026 field mapping documented in
[`unstko/enpass-to-1password`](https://github.com/unstko/enpass-to-1password).
This implementation is new, uses only the Python standard library, targets the
current 1Password web CSV importer, handles all categories by safe fallback, and
includes automated tests.

## License

MIT. See [LICENSE](LICENSE).

