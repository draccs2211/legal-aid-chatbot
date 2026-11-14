# Troubleshooting

## "ChromaDB is empty" but you loaded the data before

Run the doctor first. It prints the effective database path, where that value
came from, every `.env` that could be loaded, and every Chroma store in the
repo with its chunk count. It never prints a secret, never creates a store and
never writes to one (counts come from a temporary copy of `chroma.sqlite3`).
An early version opened stores with the Chroma client, which modifies files;
that was fixed on 2026-11-06.

    python scripts\doctor.py

**Seen once (2026-11-05):** `.env` contained `CHROMADB_PATH=./chromadb_storecd backend`
(a `cd backend` command glued onto the value). The app silently created and used
a new empty store while the real one (174 chunks) sat untouched in
`chromadb_store/`. Fix: make the line read `CHROMADB_PATH=./chromadb_store`
(or delete it; that is the default), then run the doctor again.

## Editing `.env` on Windows

* Use an editor that saves plain UTF-8 **without BOM** (VS Code does). A BOM can
  corrupt the first key in the file.
* The process environment wins over `.env`. `Remove-Item Env:CHROMADB_PATH`
  clears a value set earlier in the same PowerShell session.
* `python-dotenv` also looks in parent folders, so a stray `.env` in `C:\dev\`
  would be loaded too; the doctor lists those.
* Check that secrets are ignored by git: `git check-ignore -v .env` must print a rule.

## Stray database folders

Folders named like `chromadb_storecd backend` are leftovers of the mistake above.
The real database is `chromadb_store/`. All `chromadb_store*/` folders are
git-ignored; two old ones that were committed by the original repository can be
removed with `git rm -r`.
