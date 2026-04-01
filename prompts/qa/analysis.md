You are running the qa-tracer skill and find-my-name skill. Analyze each diff file and write a JSON result.
Follow the rules in your qa-tracer skill and its references/ documents.

CRITICAL RULE FOR UI STRINGS:
If `[UI Context]` is provided, you MUST use the exact ENGLISH strings for button names, screen titles, and hints in `trigger_point` and `test_method`.
Do NOT translate these UI names. Wrap them in double quotes (e.g. Click the `"Save"` button).

CRITICAL RULE FOR YOLO MODE:
Under NO circumstances are you allowed to create or modify scripts or skills to skip or bypass the actual analysis. You MUST read the diffs and perform the analysis as requested.

## Task
Read each .diff file → analyze → write .json to {reports_dir}/.
Do NOT stop until all files are done.

## File List
{file_list}
