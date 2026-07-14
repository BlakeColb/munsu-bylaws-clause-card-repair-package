# Fixed MUNSU Bylaws Corpus: GBrain Upload Guide

Date prepared: 2026-07-14

## Use These Files

Use this repaired corpus root:

```text
fixed-generated/compiled/
```

The repaired Clause Cards are under:

```text
fixed-generated/compiled/legal/clauses/bylaws/
```

Do not import from:

```text
current-generated/compiled/
```

That folder is the superseded review baseline. It is retained only so old findings and the repair diff remain auditable.

## Verification Status

Local verification passed on the repaired corpus:

- Clause Cards: 346
- Definitions: 4
- Unresolved-reference warning pages: 8
- Compiler validation: passed
- Blocking errors: 0
- P0 findings: 0
- P1 findings: 0
- Remaining review rows: 8 P2 warning-only unresolved references
- `fixed-generated/compiled/import-manifest.yaml` SHA-256:
  `de842a5abd971e6548aab5e23e22e82a248b5777bf6495b4056960631bcef272`

Verification commands used:

```powershell
cd compiler
$env:PYTHONPATH="src"
python -m legal_corpus.cli validate ..\fixed-generated\compiled
python -m legal_corpus.cli report ..\fixed-generated\compiled
cd ..
python tools\analyze_clause_cards.py --fail-on-findings
```

## Important Import Boundary

`fixed-generated/compiled/` is source-aware and validated, but it is not the final production-import bundle by itself.

The compiled corpus still carries safe local defaults such as:

- `sync_eligible: false` in `import-manifest.yaml`
- `sync_eligibility: blocked`
- `target_namespace: null`
- per-card `validation_status: pending`

Those defaults are intentional. The production bundle step must add approval-bound production metadata, target namespace, canonical page IDs, and receipt-bound rollback data.

Also, the existing Mycroft/GBrain full-document release importer was allowlisted for the old 323-card release. This fixed corpus has 346 Clause Cards. The old release bundles and approval hashes must not be reused.

## Safe Upload Path

1. Keep the old release bundles out of the next import.

   Do not use `review/full-release-summary.json` or any old `full-production-bundles/` from the 323-card run. Their hashes and batch totals describe the superseded corpus.

2. Regenerate the production release manifest and production bundles from `fixed-generated/compiled/`.

   The regenerated bundle set must use:

   - `fullReleaseTotalCount: 346`
   - a new fixed-corpus card-set hash
   - a new aggregate release manifest hash
   - batch manifests and approval payload hashes derived from the fixed files

3. Update the Mycroft-side allowlist before importing.

   The current Mycroft scripts contain old 323-card constants. Update both the local validator/generator and the live gateway release route before attempting a full import:

   - `scripts/legal_corpus_production_pilot.py`
   - `scripts/phase10_generate_munsu_bylaws_production_bundle.py`
   - `scripts/deploy_phase10_live_routes.py`

   The values that must change are the full-release total cap, fixed card-set hash, and aggregate release manifest hash. The live route currently rejects any full Bylaws release that does not match the old 323-card allowlist.

4. Use an isolated staging namespace or a clean replacement plan.

   Recommended: import the repaired corpus into a new staging namespace first, verify metadata-only retrieval, then promote/swap. Do not blindly append the fixed 346-card set into `munsu-bylaws-public-v1` if old partial cards still exist there.

5. Copy the approved production bundles to the server allowed import root.

   The live importer accepts bundles only under the server-side allowed roots, including:

   ```text
   /var/lib/hermes-agent/legal-corpus-production/imports/
   ```

6. Import each batch through the approval-wrapped local admin route.

   Use the route:

   ```text
   POST /v1/admin/gbrain/legal-corpus/production/import
   ```

   The payload shape is:

   ```json
   {
     "bundle_root": "/var/lib/hermes-agent/legal-corpus-production/imports/<release-id>/batch-001",
     "operator_approval_id": "phase10-<approved-batch-id>",
     "manifest_sha256": "<batch import-manifest.yaml sha256>",
     "approval_payload_sha256": "<approval binding sha256>",
     "mode": "bylaws_full_document_release"
   }
   ```

   The route is local-admin only and writes through the GBrain MCP `put_page` path. It also writes a receipt and supports receipt-bound rollback planning.

7. Verify after import.

   Minimum checks:

   - Confirm the import receipt reports `status: pass`.
   - Confirm imported page count equals the batch plan.
   - Run metadata-only exact reads for several known clause IDs.
   - Run bounded search through `gbrain_context_lookup` for public Bylaws queries.
   - Confirm no old unsafe page IDs remain active if replacing an earlier partial import.
   - Run `gbrain embed --stale` only after the sync/import state is accepted and embedding provider config is ready.

## Bottom Line

The repaired corpus is ready for production-bundle preparation. It is not safe to use the old 323-card production bundle or to direct-import the raw compiled folder into live GBrain as the final production release.
