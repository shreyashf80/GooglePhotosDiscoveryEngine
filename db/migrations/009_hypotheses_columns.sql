ALTER TABLE hypotheses ALTER COLUMN status DROP NOT NULL;
ALTER TABLE hypotheses ALTER COLUMN support_count DROP NOT NULL;
ALTER TABLE hypotheses ALTER COLUMN contradict_count DROP NOT NULL;
ALTER TABLE hypotheses ALTER COLUMN relevant_count DROP NOT NULL;
