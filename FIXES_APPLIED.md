# Fixes applied in the final merged package

This file is a summary. See `MERGE_REPORT.md` for the merge policy and `FIXES_FROM_03_ONWARD.md` for the later frontend change record.

The merged source includes the earlier backend/migration fixes and the later frontend fixes. The merge deliberately preserves stronger first-archive backend implementations where the second archive regressed or reduced them; see `MERGE_REPORT.md` for those exact examples.

Validation status is recorded in `MERGE_VALIDATION.txt`. Do not interpret source compilation or static checks as proof that the whole application is production-ready. Back up the database and run the full test suite and deployment smoke tests before using this package with real orders or payments.
