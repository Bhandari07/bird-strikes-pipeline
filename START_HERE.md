# Start here

1. Read README.md for Snowflake account setup and the exact commands.
2. Open Submission_Report.docx for the assessment answers and implementation boundaries.
3. Run the local checks with `python3 -m unittest discover -v` if you want to verify the domain logic before connecting.
4. Run `python snowflake_pipeline.py --bootstrap` after setting your account variables and installing requirements-snowflake.txt.
5. Run `python scripts/build_snowflake.py --publish`, then `python scripts/verify_snowflake.py`.

The uploaded package has passed local tests. It has not been executed against a live Snowflake account. Live verification creates a new evidence file containing actual query IDs.
