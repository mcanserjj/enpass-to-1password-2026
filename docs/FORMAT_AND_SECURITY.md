# Format basis, limitations, and security

Verified on 2026-08-24.

## Official sources

- [Enpass: Importing from Enpass](https://help.enpass.io/personal/latest/all/importing-from-enpass)
  documents desktop JSON export, vault selection, and optional inclusion of
  Trash and Archive items.
- [Enpass: Adding and customizing fields](https://help.enpass.io/personal/latest/all/customizing-fields)
  confirms that items can contain custom field names, types, sensitive values,
  ordering, and section headers.
- [1Password: Move your data into your account](https://support.1password.com/import-1password-com/)
  documents the supported generic CSV item types, their required fields,
  consistent column counts, and CSV quoting requirements.
- [1Password: Export your data](https://support.1password.com/export/)
  documents the limited CSV field set and warns that exports are unencrypted.

Neither vendor publishes a complete Enpass-JSON-to-1Password-CSV schema. The
converter consequently separates verified rules from compatibility inference.

## Compatibility inference

The Enpass JSON keys and field-type strings are based on public Enpass exports as
handled by the two open-source projects linked in the README. The converter only
promotes values to native CSV columns when the type is recognizable. Everything
else is retained in the Notes column with its label and source category.

## Known limitations

- CSV cannot carry attachments. Base64 attachments found in JSON are extracted
  into a local directory and referenced in Notes.
- Passkeys are not transferable through this format.
- Item types other than Login, Credit Card, and Secure Note cannot remain native
  categories through the generic 1Password CSV importer.
- Custom field structure, section semantics, creation/modification timestamps,
  archive/trash behavior, icons, and password history cannot be reproduced
  exactly through CSV. Available values are retained as text when recognized.
- TOTP URI/secret values are copied, but must be verified against a real login
  before Enpass is removed.

## Security rules

- Enpass JSON and generated CSV files contain plaintext secrets.
- Do not commit, email, synchronize, or back up conversion files.
- Do not open the CSV in spreadsheet software unless necessary; cells beginning
  with formula characters may be interpreted by such software. Altering those
  cells would corrupt passwords, so the converter preserves them verbatim.
- Import into a temporary or dedicated vault first when practical.
- Compare counts and inspect important items before deleting Enpass.
- Delete all plaintext migration artifacts after successful verification.

