/**
 * KONSTRYX — konstryx.nr
 * Document number ranges, configurable per object.
 *
 * Scope is a setting, not a build-time choice: the same product serves a client
 * who wants one series across the group (RR-2026-0001) and a client whose legal
 * entities each need their own (RR-INFC-2026-0001). Two things are configured
 * independently, because they answer different questions:
 *
 *   scope   — what the counter is partitioned by. GLOBAL means one series;
 *             COMPANY means a separate series per legal entity.
 *   pattern — how the number renders. Changing this never changes which
 *             counter a document draws from.
 *
 * Keeping them separate matters: a client can show the company code in the
 * number while still running one group-wide sequence, or run per-company
 * sequences without showing the code. Collapsing the two into one flag would
 * force those to move together.
 */
namespace konstryx.nr;

using { cuid, managed } from '@sap/cds/common';
using { konstryx.admin } from './admin';

/** One per document type — RR, AVC, RES, BUD, and so on. */
entity NumberRangeObject : cuid, managed {
  code        : String(20);       // RR · AVC · RES · BUD
  name        : String(80);
  /** CDS entity whose documents draw from this range. */
  entityName  : String(120);

  /** What the counter is partitioned by. */
  scope       : String enum { GLOBAL; COMPANY; } default 'GLOBAL';

  /**
   * Tokens: {OBJ} object code · {CC} company code · {YYYY} four-digit year
   * · {YY} two-digit year · {SEQ} zero-padded sequence.
   * GLOBAL  e.g. {OBJ}-{YYYY}-{SEQ}      -> RR-2026-0001
   * COMPANY e.g. {OBJ}-{CC}-{YYYY}-{SEQ} -> RR-INFC-2026-0001
   */
  pattern     : String(60) default '{OBJ}-{YYYY}-{SEQ}';

  /** YEARLY restarts each calendar year; NEVER runs continuously. */
  resetPolicy : String enum { NEVER; YEARLY; } default 'YEARLY';
  seqLength   : Integer default 4;
  startAt     : Integer default 1;
  isActive    : Boolean default true;

  counters    : Composition of many NumberRangeCounter on counters.rangeObject = $self;
}

/**
 * Runtime state. One row per live series: a GLOBAL yearly object has one row
 * per year, a COMPANY yearly object one per company per year.
 *
 * companyCode and fiscalYear are stored flat rather than as an association and
 * a derived value so the row can be located and locked with a single indexed
 * read on the hot path, and so a counter survives its company being renamed.
 */
entity NumberRangeCounter : cuid, managed {
  rangeObject : Association to NumberRangeObject;
  companyCode : String(10) default '';   // '' when scope = GLOBAL
  fiscalYear  : Integer;                 // 0 when resetPolicy = NEVER
  lastNumber  : Integer default 0;
}
