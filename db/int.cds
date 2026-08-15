/**
 * KONSTRYX — konstryx.int (Data Model Spec §8)
 * Integration platform: sync runs, error queue, S/4 doc cross-reference.
 */
namespace konstryx.int;

using { cuid, managed } from '@sap/cds/common';
using { konstryx.admin } from './admin';

entity SyncRun : cuid, managed {
  config        : Association to admin.S4SyncConfig;
  startedAt     : Timestamp;
  finishedAt    : Timestamp;
  direction     : String(3);     // IN / OUT
  recordsRead   : Integer;
  recordsWritten: Integer;
  result        : String(20);    // OK / PARTIAL / ERROR
  errors        : Composition of many ErrorQueueItem on errors.syncRun = $self;
}

entity ErrorQueueItem : cuid, managed {
  syncRun    : Association to SyncRun;
  objectType : String(40);
  objectKey  : String(60);
  payload    : LargeString;
  error      : String(1000);
  attempts   : Integer default 0;
  status     : String enum { NEW; RETRIED; RESOLVED; DISCARDED; } default 'NEW';
}

entity S4DocXref : cuid, managed {
  konstryxDoc : String(40);
  s4DocType   : String(20);
  s4DocNo     : String(20);
  s4System    : String(20);
}
