-- Run after an authorized restore, BEFORE enabling personal strategy API.
-- Keeps quota receipts and active strategies. Does not touch ledger or notes.
BEGIN;
DELETE FROM private.personal_reports WHERE report_id IN (
 SELECT report_id FROM (
  SELECT report_id,row_number() OVER(PARTITION BY user_id,kind ORDER BY created_at DESC,report_id DESC) AS n
  FROM private.personal_reports
 ) ranked WHERE n>3
);
UPDATE private.personal_research_requests SET input_json='{}',checkpoint='{}'
 WHERE status IN ('READY','PARTIAL') OR
 (status='FAILED' AND period_start < (now() AT TIME ZONE 'Asia/Taipei')::date-7);
COMMIT;
