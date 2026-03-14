Fixed IONOS Short Roster Publishing Regression
The recent report registry refactor introduced a regression where generating the short roster no longer triggered the automatic upload to IONOS. This was caused by the _publish_short_roster_to_ionos function using os.getenv to check for the ENABLE_IONOS_ROSTER_PUBLISH flag, which was not correctly picking up the value from the .env file during execution.
Changes Made:
1.
Corrected Flag Retrieval: Updated _publish_short_roster_to_ionos in backend/app/routers/reports.py to use settings.enable_ionos_roster_publish. Since the application's settings object (powered by Pydantic) correctly loads variables from the .env file, this ensures the publishing logic is enabled as intended.
2.
Explicit Side-Effect Trigger: Confirmed that _render_pdf_report explicitly calls the IONOS publishing helper only for the short-roster ID, preserving the original behavior without relying on implicit side effects.
3.
Code Cleanup: Removed the now-unused os import from backend/app/routers/reports.py.
Verification:
•
The code compiles successfully with python3 -m py_compile.
•
The short-roster route correctly delegates to _render_pdf_report, which in turn triggers _publish_short_roster_to_ionos.
•
The publishing logic now correctly reads the activation flag from the application configuration.