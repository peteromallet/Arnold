-- Drop disabled generation-to-variant trigger/function.
--
-- 20260118000000_disable_auto_variant_trigger.sql dropped the trigger but left
-- the function in place. The frontend stale callers have now been changed to
-- fail closed instead of relying on this disabled legacy path.

DROP TRIGGER IF EXISTS trg_auto_create_variant_after_generation ON generations;

DROP FUNCTION IF EXISTS auto_create_variant_after_generation_insert();
