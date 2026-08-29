"""Ingestion engine.

ENGINE_VERSION identifies the set of cleaning, validation, enrichment and
deduplication rules that produced a record. It is stamped on every row at write
time, which is what makes a corrected rule reachable: without it there is no way
to ask "which rows were produced by the broken version?", and every fix strands
the data already in the database.

Bump it whenever a change alters the OUTPUT of the pipeline for the same input:
a cleaning rule, a validation threshold, an enrichment source, a canonical
vocabulary. Do not bump it for performance work, refactors, or API changes,
which leave the derived values identical.

After a bump, existing rows are stale until reprocessed. GET
/api/maintenance/engine-status reports how many, and POST
/api/maintenance/reprocess re-derives them from the stored source files.

Changelog
---------
1  Original pipeline.
2  sq.m -> sq.ft conversion fixed (sizes were stored 10.76x too small when the
   unit was stated only in the column header); numbered districts no longer
   collapsed into their base (Al Barsha 1/2/3, DAMAC Hills 2); developer names
   canonicalised; development categories no longer written into Property Type;
   Dubai Hills developer fallback corrected; Property Type normalised to market
   vocabulary and filled from the property reference; deduplication matches
   across registers rather than within one file.
"""

ENGINE_VERSION = 2
